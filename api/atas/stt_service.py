"""
Pipeline de Speech-to-Text para áudio da assembleia (Fase 6).

Estratégia em 3 etapas:

  1. **gerar_sas_upload**: backend cria linha `atas_audios(status='uploaded')`
     com chave única e devolve SAS URL de WRITE pro frontend. O frontend faz
     `PUT` direto no Azure Blob — backend não vira proxy de áudios de até
     ~700MB (WAV de 2h).

  2. **confirmar_upload**: depois do PUT, frontend chama backend pra
     confirmar. Backend valida que o blob existe, atualiza
     `atas_audios.status='transcribing'` e dispara `transcrever_em_background`.

  3. **transcrever_em_background**: baixa do storage, chunking via pydub
     em pedaços de ~10min (MP3 64kbps), transcreve cada chunk via Whisper
     API com concorrência limitada, junta o texto, persiste em
     `atas_audios.transcricao_text` e `atas.insumos_json.resumo`.

Custo Whisper API: $0.006/minuto. Cada job estima e grava em
`atas_audios.custo_estimado_usd`.

Limite de 25MB por upload do Whisper — chunking de ~10min em 64kbps mp3
fica em ~5MB por chunk, com folga.
"""

from __future__ import annotations

import asyncio
import io
import json
import re
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from loguru import logger
from sqlalchemy import text

from api.atas import jobs_service
from api.db import tenant_session
from api.llm.openai_client import get_llm_client_for_tenant
from api.storage import get_storage
from api.storage.base import StorageError
from api.tenants.models import TenantConfig


# Tamanho de cada chunk de áudio enviado ao Whisper (em milissegundos).
# 10 min × 64kbps mono ≈ 4.8MB → bem abaixo do limite 25MB.
CHUNK_DURATION_MS = 10 * 60 * 1000

# Bitrate do export pra MP3. Mantemos baixo (64kbps mono) — Whisper aceita
# bem e reduz upload por chunk significativamente.
EXPORT_BITRATE = "64k"

# Limite de chunks transcritos em paralelo. Whisper rate limit: ~50 RPM.
CONCORRENCIA_TRANSCRICAO = 3

# Custo Whisper API em USD por minuto (referência out/2025; revisar quando mudar).
WHISPER_USD_POR_MINUTO = 0.006

# Extensões aceitas (validação básica — Whisper aceita: mp3, mp4, mpeg, mpga,
# m4a, wav, webm, ogg, flac).
EXTENSOES_ACEITAS: frozenset[str] = frozenset(
    {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac"}
)


# =============================================================================
# Schemas de retorno
# =============================================================================
@dataclass
class SasUploadInfo:
    """Devolvido pro frontend pra fazer PUT direto no Blob."""

    audio_id: str
    upload_url: str                       # SAS URL com permissão write+create
    storage_key: str                      # chave do blob (caller pode mostrar)
    expires_in_seconds: int


@dataclass
class ResultadoTranscricao:
    sucesso: bool
    transcricao: str | None = None
    duracao_segundos: float | None = None
    qtde_chunks: int | None = None
    custo_estimado_usd: float | None = None
    erro: str | None = None


# =============================================================================
# Etapa 1 — gerar SAS URL pro frontend fazer upload
# =============================================================================
async def gerar_sas_upload(
    *,
    tenant_id: str,
    ata_id: UUID,
    uploaded_by_user_id: UUID,
    file_name: str,
    file_size_bytes: int,
    content_type: str | None,
) -> SasUploadInfo:
    """
    Cria linha `atas_audios(status='uploaded')` (placeholder) e devolve SAS
    URL pro frontend. O `audio_id` é gerado aqui — frontend usa ele depois
    pra confirmar.

    Levanta `ValueError` se a ata não existe no tenant ou nome de arquivo é
    inválido. Levanta `StorageError` se o storage não suporta SAS upload
    (ex: STORAGE_PROVIDER=local).
    """
    file_name = (file_name or "audio").strip()[:255]
    if not _extensao_valida(file_name):
        raise ValueError(
            f"Extensão do arquivo não suportada. Aceitas: {sorted(EXTENSOES_ACEITAS)}"
        )

    storage = get_storage()
    audio_id = uuid4()
    storage_key = f"{tenant_id}/atas/{ata_id}/audios/{audio_id}/{_sanitizar_nome(file_name)}"

    upload_url = await storage.signed_url_upload(
        storage_key,
        expires_in_seconds=1800,        # 30min, com folga pra upload de até ~700MB
        content_type=content_type,
    )

    async with tenant_session(tenant_id) as session:
        # Confirma que a ata existe (se não, FK explode)
        ata = await jobs_service.buscar_ata(session, tenant_id, ata_id)
        if not ata:
            raise ValueError(f"Ata {ata_id} não encontrada no tenant {tenant_id}.")

        await session.execute(
            text(
                """
                INSERT INTO atas_audios
                    (id, ata_id, tenant_id, file_storage_key, file_name,
                     file_size_bytes, status, uploaded_by_user_id)
                VALUES (:aid, :ata, :tid, :key, :fn, :fs, 'uploaded', :uid)
                """
            ),
            {
                "aid": str(audio_id),
                "ata": str(ata_id),
                "tid": tenant_id,
                "key": storage_key,
                "fn": file_name,
                "fs": file_size_bytes,
                "uid": str(uploaded_by_user_id),
            },
        )
        await jobs_service.registrar_acao(
            session,
            tenant_id=tenant_id,
            ata_id=ata_id,
            ator_user_id=uploaded_by_user_id,
            acao="audio_uploaded",
            detalhe={
                "audio_id": str(audio_id),
                "file_name": file_name,
                "file_size_bytes": file_size_bytes,
            },
        )

    logger.info(f"[atas/stt] SAS gerada audio={audio_id} ata={ata_id} key={storage_key}")
    return SasUploadInfo(
        audio_id=str(audio_id),
        upload_url=upload_url,
        storage_key=storage_key,
        expires_in_seconds=1800,
    )


# =============================================================================
# Etapa 2 — confirmar upload e disparar transcrição
# =============================================================================
async def confirmar_upload(
    *,
    tenant_config: TenantConfig,
    ata_id: UUID,
    audio_id: UUID,
) -> dict[str, Any]:
    """
    Valida que o blob existe no storage e marca `atas_audios.status='transcribing'`.

    Retorna o registro atualizado. Levanta `ValueError` se a entrada não bate
    ou o blob ainda não foi enviado ao storage.

    Caller é o router; ele agenda `transcrever_em_background` separadamente
    via FastAPI BackgroundTasks após esta função retornar com sucesso.
    """
    tenant_id = tenant_config.tenant_id
    storage = get_storage()

    async with tenant_session(tenant_id) as session:
        row = (await session.execute(
            text(
                """
                SELECT id, ata_id, file_storage_key, status
                FROM atas_audios
                WHERE id = :aid AND tenant_id = :tid AND ata_id = :ata
                """
            ),
            {"aid": str(audio_id), "tid": tenant_id, "ata": str(ata_id)},
        )).mappings().first()

    if not row:
        raise ValueError(f"Áudio {audio_id} não encontrado pra ata {ata_id}.")
    if row["status"] != "uploaded":
        raise ValueError(
            f"Áudio {audio_id} já está em status '{row['status']}', não pode (re)transcrever."
        )

    if not await storage.exists(row["file_storage_key"]):
        raise ValueError(
            "Áudio não foi encontrado no storage. Confirme que o PUT direto foi concluído."
        )

    async with tenant_session(tenant_id) as session:
        await session.execute(
            text(
                "UPDATE atas_audios SET status='transcribing', "
                "error_detail=NULL WHERE id=:aid AND tenant_id=:tid"
            ),
            {"aid": str(audio_id), "tid": tenant_id},
        )
        await session.execute(
            text(
                "UPDATE atas SET status='aguardando_transcricao', "
                "updated_at=NOW() WHERE id=:ata AND tenant_id=:tid"
            ),
            {"ata": str(ata_id), "tid": tenant_id},
        )
        await jobs_service.registrar_acao(
            session,
            tenant_id=tenant_id,
            ata_id=ata_id,
            ator_user_id=None,
            acao="transcricao_iniciada",
            detalhe={"audio_id": str(audio_id)},
        )

    return {
        "audio_id": str(audio_id),
        "ata_id": str(ata_id),
        "status": "transcribing",
        "file_storage_key": row["file_storage_key"],
    }


# =============================================================================
# Etapa 3 — background task que transcreve
# =============================================================================
async def transcrever_em_background(
    *,
    tenant_config: TenantConfig,
    ata_id: UUID,
    audio_id: UUID,
) -> None:
    """
    Baixa o áudio do storage, faz chunking via pydub, transcreve cada chunk
    via Whisper API com concorrência limitada, junta o resultado e persiste.

    Engole exceções — registra erro em `atas_audios.error_detail` e
    `atas_acoes(acao='transcricao_falhou')`.
    """
    tenant_id = tenant_config.tenant_id
    t0 = time.monotonic()

    try:
        # 1. Baixa o blob completo. (Em prod com áudios > 1GB, considerar
        #    streaming download em chunks. Pra MVP, in-memory.)
        storage = get_storage()
        async with tenant_session(tenant_id) as session:
            row = (await session.execute(
                text(
                    "SELECT file_storage_key, file_name FROM atas_audios "
                    "WHERE id=:aid AND tenant_id=:tid"
                ),
                {"aid": str(audio_id), "tid": tenant_id},
            )).mappings().first()
        if not row:
            raise RuntimeError(f"atas_audios {audio_id} sumiu antes da transcrição")

        stream = await storage.open(row["file_storage_key"])
        try:
            audio_bytes = stream.read()
        finally:
            stream.close()

        # 2. Chunking via pydub (precisa ffmpeg no container).
        from pydub import AudioSegment

        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        duracao_segundos = len(audio) / 1000.0

        chunks_bytes = _split_em_chunks(audio)
        logger.info(
            f"[atas/stt] audio={audio_id} duração={duracao_segundos:.1f}s "
            f"chunks={len(chunks_bytes)}"
        )

        # 3. Transcreve com concorrência limitada (3 chunks em paralelo).
        atas_cfg = tenant_config.atas
        whisper_model = atas_cfg.whisper_model if atas_cfg else "whisper-1"
        llm = get_llm_client_for_tenant(tenant_config)
        client = llm.async_client

        sem = asyncio.Semaphore(CONCORRENCIA_TRANSCRICAO)

        async def transcrever_chunk(idx: int, blob: bytes) -> tuple[int, str]:
            async with sem:
                resp = await client.audio.transcriptions.create(
                    model=whisper_model,
                    file=(f"chunk_{idx:03d}.mp3", blob, "audio/mpeg"),
                    language="pt",
                    response_format="text",
                )
                # SDK retorna string direta com response_format="text".
                return idx, str(resp).strip()

        tasks = [transcrever_chunk(i, b) for i, b in enumerate(chunks_bytes)]
        partes = await asyncio.gather(*tasks)
        partes_ord = [p for _, p in sorted(partes, key=lambda x: x[0])]
        transcricao = "\n\n".join(filter(None, partes_ord))

        custo = (duracao_segundos / 60.0) * WHISPER_USD_POR_MINUTO
        duracao_proc = round(time.monotonic() - t0, 2)

        # 4. Persiste — atas_audios + insumos_json.resumo
        async with tenant_session(tenant_id) as session:
            await session.execute(
                text(
                    """
                    UPDATE atas_audios SET
                        status='done',
                        transcricao_text=:txt,
                        duracao_segundos=:dur,
                        qtde_chunks=:qc,
                        custo_estimado_usd=:custo,
                        transcribed_at=NOW(),
                        error_detail=NULL
                    WHERE id=:aid AND tenant_id=:tid
                    """
                ),
                {
                    "aid": str(audio_id),
                    "tid": tenant_id,
                    "txt": transcricao,
                    "dur": duracao_segundos,
                    "qc": len(chunks_bytes),
                    "custo": custo,
                },
            )

            # Mescla a transcrição em insumos_json.resumo.
            try:
                await jobs_service.atualizar_insumos(
                    session,
                    tenant_id=tenant_id,
                    ata_id=ata_id,
                    patch={"resumo": transcricao},
                    ator_user_id=None,
                )
            except ValueError:
                # Ata foi apagada entre o início e o fim — apenas loga.
                logger.warning(
                    f"[atas/stt] ata {ata_id} sumiu durante transcrição; "
                    f"insumos não atualizados"
                )

            # Volta ata pra rascunho (pronta pra geração).
            await session.execute(
                text(
                    "UPDATE atas SET status='rascunho', updated_at=NOW() "
                    "WHERE id=:ata AND tenant_id=:tid"
                ),
                {"ata": str(ata_id), "tid": tenant_id},
            )
            await jobs_service.registrar_acao(
                session,
                tenant_id=tenant_id,
                ata_id=ata_id,
                ator_user_id=None,
                acao="transcricao_concluida",
                detalhe={
                    "audio_id": str(audio_id),
                    "duracao_segundos": duracao_segundos,
                    "qtde_chunks": len(chunks_bytes),
                    "custo_estimado_usd": round(custo, 4),
                    "duracao_processamento_segundos": duracao_proc,
                },
            )

        logger.info(
            f"[atas/stt] audio={audio_id} done — {len(chunks_bytes)} chunks, "
            f"{duracao_segundos:.1f}s áudio, ${custo:.3f}"
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[atas/stt] audio={audio_id} falhou: {exc}")
        try:
            async with tenant_session(tenant_id) as session:
                await session.execute(
                    text(
                        "UPDATE atas_audios SET status='failed', "
                        "error_detail=:err WHERE id=:aid AND tenant_id=:tid"
                    ),
                    {"err": str(exc)[:1000], "aid": str(audio_id), "tid": tenant_id},
                )
                # Não muda status da ata: ela volta pro estado anterior
                # (rascunho/aguardando_transcricao). Caller decide retentar.
                await jobs_service.registrar_acao(
                    session,
                    tenant_id=tenant_id,
                    ata_id=ata_id,
                    ator_user_id=None,
                    acao="transcricao_falhou",
                    detalhe={"audio_id": str(audio_id), "erro": str(exc)[:500]},
                )
        except Exception as inner:  # noqa: BLE001
            logger.exception(
                f"[atas/stt] falha registrando error_detail audio={audio_id}: {inner}"
            )


# =============================================================================
# Helpers
# =============================================================================
def _split_em_chunks(audio) -> list[bytes]:
    """
    Quebra o áudio em pedaços de CHUNK_DURATION_MS e exporta cada um pra MP3
    em-memória. Retorna lista de bytes (cada item ≤ ~5MB).
    """
    chunks: list[bytes] = []
    duracao_total = len(audio)
    pos = 0
    while pos < duracao_total:
        segmento = audio[pos : pos + CHUNK_DURATION_MS]
        buf = io.BytesIO()
        segmento.export(buf, format="mp3", bitrate=EXPORT_BITRATE, parameters=["-ac", "1"])
        chunks.append(buf.getvalue())
        pos += CHUNK_DURATION_MS
    return chunks


def _extensao_valida(file_name: str) -> bool:
    nome = file_name.lower()
    return any(nome.endswith(ext) for ext in EXTENSOES_ACEITAS)


def _sanitizar_nome(file_name: str) -> str:
    """Normaliza nome de arquivo pra evitar caracteres problemáticos no key."""
    nome = re.sub(r"[^A-Za-z0-9._\-]", "_", file_name)
    return nome[:200] or "audio"
