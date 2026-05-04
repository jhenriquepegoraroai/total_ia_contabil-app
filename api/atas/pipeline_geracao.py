"""
Pipeline de geração de ata via LLM (3 passos sequenciais).

Portado de `01_gera_atas/llm_services.py` (versão de produção da Lello).

Fluxo:
    1. PROMPT_PRINCIPAL: cabeçalho/edital + resumo + complemento → ata HTML inicial
    2. PROMPT_REVISAO: corrige inconsistências, datas, placeholders, duplicações
    3. PROMPT_QUORUM_ESPECIAL: detecta falhas de quórum e insere parágrafo

Saída: HTML da ata em 8 blocos. Persistido como nova linha em
`atas_versoes` (tipo='gerada'); `atas.versao_atual_id` aponta pra ela e
status muda pra 'gerada'.

NÃO portado nesta fase (ficaram pra fase 7 ou ata-stage avançado):
  - max_retries (mantemos 1 try por chamada — 2 tentativas internas no
    PROMPT_PRINCIPAL pra resposta vazia, igual ao original)
  - extrair_tabela_deliberacoes (estruturado JSON pós-ata) — assets que
    não são essenciais pro fluxo de revisão; fica de fora do MVP

Os helpers de limpeza HTML (limpar_markdown, destacar_placeholders,
limpar_prompt_vazado) foram portados verbatim — são pós-processamento
crítico pra desinfetar saída do LLM.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from loguru import logger
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.atas import jobs_service
from api.atas.prompts import PROMPT_PRINCIPAL, PROMPT_QUORUM_ESPECIAL, PROMPT_REVISAO
from api.llm.openai_client import _modelo_moderno, get_llm_client_for_tenant
from api.tenants.models import TenantConfig


# =============================================================================
# Helpers de limpeza HTML (portados verbatim)
# =============================================================================
def limpar_markdown(texto: str) -> str:
    """Remove cercas de código e markdown da saída do LLM."""
    texto = re.sub(r"^```html\s*", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"^```\s*", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"\s*```$", "", texto, flags=re.MULTILINE)
    texto = texto.replace("<p>```html</p>", "")
    texto = texto.replace("<p>```</p>", "")
    texto = texto.replace("`", "")
    return texto.strip()


def destacar_placeholders(texto: str) -> str:
    """Envolve `[...]` em <span> verde — chama atenção pro consultor preencher."""

    def substituir(match):
        placeholder = match.group(0)
        return f'<span style="background-color:#00FF00;">{placeholder}</span>'

    texto = re.sub(
        r"\s*Nessa cor de fundo:\s*[\"']?#00FF00[\"']?",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    pattern = r'(?<!background-color:#00FF00;">)\[(?:\.{3,}|…+|[^\]]+)\]'
    return re.sub(pattern, substituir, texto)


def limpar_prompt_vazado(texto: str) -> str:
    """
    Remove conteúdo de prompt/instruções que vazaram para a saída do LLM.
    Cobre 8 padrões observados em produção (ex: "[DADOS ADICIONAIS...]",
    "REGRA CRÍTICA...", linhas órfãs com "Nome do Presidente:", blocos <p>
    vazios). Deve rodar DEPOIS de limpar_markdown e destacar_placeholders.
    """
    # Padrão 1: [DADOS ADICIONAIS...] até final
    texto = re.sub(
        r"<p>\s*<span[^>]*>\s*\[DADOS ADICIONAIS[^\]]*\].*$",
        "",
        texto,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Padrão 2: blocos com "DADOS ADICIONAIS" ou "REGRA CRÍTICA"
    texto = re.sub(
        r"<p[^>]*>\s*\[?DADOS ADICIONAIS.*?</p>.*$",
        "",
        texto,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Padrão 3: corta texto após </table> com instruções
    texto = re.sub(
        r"(</table>\s*</p>).*$",
        r"\1",
        texto,
        flags=re.DOTALL,
    )
    # Padrão 4 e 5: "Nome do Presidente:" / "Nome do Secretário:" fora de contexto
    texto = re.sub(
        r"<p>\s*Nome do Presidente:.*?</p>",
        "",
        texto,
        flags=re.DOTALL | re.IGNORECASE,
    )
    texto = re.sub(
        r"<p>\s*Nome do Secretário:.*?</p>",
        "",
        texto,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Padrão 6: "REGRA CRÍTICA"
    texto = re.sub(
        r"<p>\s*\*?\*?REGRA CR[ÍI]TICA.*?</p>",
        "",
        texto,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Padrão 7: "NUNCA substitua" ou "MANTENHA-O"
    texto = re.sub(
        r"<p>.*?(?:NUNCA substitua|MANTENHA-O).*?</p>",
        "",
        texto,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Padrão 8: linhas órfãs com "Nome do..."
    texto = re.sub(
        r"Nome do (?:Presidente|Secretário):[^<]*(?:<br\s*/?>)?",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    # Padrão 9: blocos <p> vazios
    texto = re.sub(r"<p>\s*</p>", "", texto)
    texto = re.sub(
        r"<p>&nbsp;</p>\s*<p>&nbsp;</p>\s*<p>&nbsp;</p>",
        "<p>&nbsp;</p>",
        texto,
    )
    return texto.strip()


def _pos_processar(texto: str) -> str:
    """Pipeline padrão de pós-processamento da saída do LLM."""
    texto = limpar_markdown(texto)
    texto = destacar_placeholders(texto)
    texto = limpar_prompt_vazado(texto)
    return texto


# =============================================================================
# Insumos do pipeline (entrada do payload)
# =============================================================================
@dataclass
class InsumosGeracao:
    """Insumos da geração — espelha o JSON salvo em `atas.insumos_json`."""

    cabecalho: str                                # HTML, obrigatório
    resumo: str                                   # texto, obrigatório
    edital: str = ""                              # HTML, opcional
    complemento: str = ""                         # texto, opcional
    assinatura_eletronica: bool = False
    nome_presidente: str = ""
    nome_secretario: str = ""
    cnpj_condominio: str = ""

    def validar(self) -> list[str]:
        """Retorna lista de erros (vazia = OK)."""
        erros: list[str] = []
        if not self.cabecalho.strip():
            erros.append("cabecalho (dados oficiais do condomínio) é obrigatório")
        if not self.resumo.strip():
            erros.append("resumo da assembleia é obrigatório")
        return erros

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "InsumosGeracao":
        return cls(
            cabecalho=d.get("cabecalho", ""),
            resumo=d.get("resumo", ""),
            edital=d.get("edital", ""),
            complemento=d.get("complemento", ""),
            assinatura_eletronica=bool(d.get("assinatura_eletronica", False)),
            nome_presidente=d.get("nome_presidente", "") or d.get("nomePresidente", ""),
            nome_secretario=d.get("nome_secretario", "") or d.get("nomeSecretario", ""),
            cnpj_condominio=d.get("cnpj_condominio", "") or d.get("cnpjCondominio", ""),
        )


@dataclass
class ResultadoGeracao:
    """Saída do pipeline — pra persistência + debugging."""

    sucesso: bool
    ata_html: str | None = None
    erro: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Chamada LLM genérica
# =============================================================================
async def _completion(
    *,
    client: AsyncOpenAI,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
) -> tuple[str, dict[str, Any]]:
    """
    Chat completion. Ajusta os params conforme o modelo:
      - moderno (gpt-5.x, o-series, gpt-4.1+): max_completion_tokens, sem temperature
      - antigo (gpt-4o, gpt-4-turbo, ...): max_tokens + temperature + top_p
    """
    kwargs: dict[str, Any] = {"model": model}
    if _modelo_moderno(model):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature
        kwargs["top_p"] = 1.0

    resp = await client.chat.completions.create(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **kwargs,
    )
    choice = resp.choices[0]
    content = (choice.message.content or "").strip()

    metadata: dict[str, Any] = {
        "model": model,
        "finish_reason": getattr(choice, "finish_reason", None),
    }
    if hasattr(resp, "usage") and resp.usage is not None:
        metadata["usage"] = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
            "completion_tokens": getattr(resp.usage, "completion_tokens", None),
            "total_tokens": getattr(resp.usage, "total_tokens", None),
        }
    return content, metadata


# =============================================================================
# Etapas do pipeline
# =============================================================================
async def _etapa_principal(
    *,
    client: AsyncOpenAI,
    model: str,
    insumos: InsumosGeracao,
    max_tokens: int,
    temperature: float,
) -> tuple[str, dict[str, Any]]:
    """Etapa 1 — geração inicial via PROMPT_PRINCIPAL."""
    if insumos.edital:
        editais_texto = f"{insumos.cabecalho}\n\n{insumos.edital}"
    else:
        editais_texto = insumos.cabecalho

    user_prompt = PROMPT_PRINCIPAL.format(
        editais=editais_texto,
        resumo_assembleia=insumos.resumo,
        complemento=insumos.complemento or "(Nenhum dado complementar fornecido)",
        assinatura_eletronica=str(insumos.assinatura_eletronica).lower(),
        nome_presidente=insumos.nome_presidente,
        nome_secretario=insumos.nome_secretario,
        cnpj_condominio=insumos.cnpj_condominio,
    )

    # 2 tentativas internas pra saída vazia (igual ao original).
    ata = ""
    metadata: dict[str, Any] = {}
    for tentativa in (1, 2):
        ata, metadata = await _completion(
            client=client,
            model=model,
            system=(
                "Você é um assistente jurídico especializado em atas condominiais "
                "que segue rigorosamente o estilo e formato solicitados."
            ),
            user=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if ata:
            metadata["tentativas"] = tentativa
            break
        logger.warning(f"[atas/geracao] etapa principal vazia, tentativa {tentativa}/2")

    if not ata:
        raise RuntimeError("Modelo retornou ata vazia em ambas as tentativas")

    return _pos_processar(ata), metadata


async def _etapa_revisao(
    *,
    client: AsyncOpenAI,
    model: str,
    ata_gerada: str,
    nome_presidente: str,
    nome_secretario: str,
    max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    """Etapa 2 — revisão técnica via PROMPT_REVISAO. Temperature fixa em 0."""
    user_prompt = PROMPT_REVISAO.format(
        ata_gerada=ata_gerada,
        nome_presidente=nome_presidente or "[...]",
        nome_secretario=nome_secretario or "[...]",
    )
    ata, metadata = await _completion(
        client=client,
        model=model,
        system=(
            "Você é um revisor técnico especializado que corrige erros em "
            "documentos HTML seguindo regras específicas. Você retorna APENAS "
            "o HTML corrigido, sem cercas de código (```), sem crases (`), "
            "sem explicações."
        ),
        user=user_prompt,
        max_tokens=max_tokens,
        temperature=0.0,
    )
    if not ata:
        raise RuntimeError("Revisor retornou conteúdo vazio")
    return _pos_processar(ata), metadata


async def _etapa_quorum(
    *,
    client: AsyncOpenAI,
    model: str,
    ata_revisada: str,
    insumos: InsumosGeracao,
    max_tokens: int,
    temperature: float,
) -> tuple[str, dict[str, Any]]:
    """Etapa 3 — detecção de quórum especial via PROMPT_QUORUM_ESPECIAL."""
    if insumos.edital:
        editais_texto = f"{insumos.cabecalho}\n\n{insumos.edital}"
    else:
        editais_texto = insumos.cabecalho

    user_prompt = PROMPT_QUORUM_ESPECIAL.format(
        editais=editais_texto,
        resumo_assembleia=insumos.resumo,
        ata_revisada=ata_revisada,
    )
    ata, metadata = await _completion(
        client=client,
        model=model,
        system=(
            "Você é um especialista em análise de atas condominiais que "
            "detecta falhas de quórum especial e insere parágrafos específicos "
            "quando necessário. Você retorna APENAS o HTML final, sem cercas "
            "de código (```), sem crases (`), sem explicações."
        ),
        user=user_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if not ata:
        raise RuntimeError("Etapa de quórum retornou conteúdo vazio")

    quorum_detectado = (
        "sessão permanente" in ata.lower()
        and "sessão permanente" not in ata_revisada.lower()
    )
    metadata["quorum_detectado"] = quorum_detectado
    return _pos_processar(ata), metadata


# =============================================================================
# Orquestrador
# =============================================================================
async def executar_geracao(
    *,
    tenant_config: TenantConfig,
    insumos: InsumosGeracao,
    max_tokens: int = 16000,
) -> ResultadoGeracao:
    """
    Roda os 3 passos em sequência. Cada erro de etapa interrompe o fluxo
    e devolve `ResultadoGeracao(sucesso=False)`. NÃO faz persistência —
    quem chama (background task) lê o resultado e grava.
    """
    erros = insumos.validar()
    if erros:
        return ResultadoGeracao(sucesso=False, erro=f"insumos inválidos: {', '.join(erros)}")

    atas_cfg = tenant_config.atas
    if atas_cfg is None:
        return ResultadoGeracao(
            sucesso=False,
            erro=(
                "Tenant não tem TenantAtasConfig configurado — "
                "super admin precisa cadastrar modelo OpenAI pro módulo atas."
            ),
        )
    model = atas_cfg.openai_model
    temp_geracao = atas_cfg.temperature_geracao

    llm = get_llm_client_for_tenant(tenant_config)
    client = llm.async_client

    t0 = time.monotonic()
    metadata_full: dict[str, Any] = {"modelo": model, "etapas": {}}

    try:
        logger.info(f"[atas/geracao] etapa 1 — geração principal (modelo={model})")
        ata, meta1 = await _etapa_principal(
            client=client, model=model, insumos=insumos,
            max_tokens=max_tokens, temperature=temp_geracao,
        )
        metadata_full["etapas"]["principal"] = meta1

        logger.info("[atas/geracao] etapa 2 — revisão técnica")
        ata, meta2 = await _etapa_revisao(
            client=client, model=model, ata_gerada=ata,
            nome_presidente=insumos.nome_presidente,
            nome_secretario=insumos.nome_secretario,
            max_tokens=max_tokens,
        )
        metadata_full["etapas"]["revisao"] = meta2

        logger.info("[atas/geracao] etapa 3 — quórum especial")
        ata, meta3 = await _etapa_quorum(
            client=client, model=model, ata_revisada=ata, insumos=insumos,
            max_tokens=max_tokens, temperature=temp_geracao,
        )
        metadata_full["etapas"]["quorum"] = meta3
        metadata_full["quorum_detectado"] = meta3.get("quorum_detectado", False)

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[atas/geracao] falhou: {exc}")
        return ResultadoGeracao(
            sucesso=False,
            erro=str(exc),
            metadata=metadata_full,
        )

    duracao = round(time.monotonic() - t0, 2)
    metadata_full["duracao_segundos"] = duracao
    logger.info(f"[atas/geracao] concluído em {duracao}s")
    return ResultadoGeracao(sucesso=True, ata_html=ata, metadata=metadata_full)


# =============================================================================
# Background task — chamada pelo router em POST /atas/{id}/gerar
# =============================================================================
async def processar_em_background(
    *,
    tenant_config: TenantConfig,
    ata_id: UUID,
) -> None:
    """
    Lê insumos da ata, roda o pipeline, persiste a versão e atualiza status.

    Engole exceções (já registra em erro_detalhe da ata) — caller é
    BackgroundTasks da FastAPI, não tem onde reportar.
    """
    from api.db import tenant_session

    tenant_id = tenant_config.tenant_id

    # Marcar como aguardando_geracao (vai virar 'gerada' ou 'falhou' no fim).
    async with tenant_session(tenant_id) as session:
        await session.execute(
            text("UPDATE atas SET status='aguardando_geracao', updated_at=NOW() WHERE id=:aid"),
            {"aid": str(ata_id)},
        )
        ata = await jobs_service.buscar_ata(session, tenant_id, ata_id)

    if not ata:
        logger.error(f"[atas/geracao] ata {ata_id} sumiu antes do processamento")
        return

    insumos = InsumosGeracao.from_dict(ata.get("insumos_json") or {})

    resultado = await executar_geracao(tenant_config=tenant_config, insumos=insumos)

    async with tenant_session(tenant_id) as session:
        if not resultado.sucesso:
            await session.execute(
                text(
                    "UPDATE atas SET status='falhou', erro_detalhe=:err, updated_at=NOW() "
                    "WHERE id=:aid"
                ),
                {"err": (resultado.erro or "")[:1000], "aid": str(ata_id)},
            )
            await jobs_service.registrar_acao(
                session,
                tenant_id=tenant_id,
                ata_id=ata_id,
                ator_user_id=None,
                acao="geracao_falhou",
                detalhe={"erro": resultado.erro, "metadata": resultado.metadata},
            )
            return

        # Cria nova versão imutável e aponta atas.versao_atual_id pra ela.
        row = (await session.execute(
            text(
                """
                INSERT INTO atas_versoes
                    (ata_id, tenant_id, tipo, conteudo_html, metadata_json,
                     criada_por_user_id)
                VALUES (:aid, :tid, 'gerada', :html, CAST(:meta AS JSONB), NULL)
                RETURNING id
                """
            ),
            {
                "aid": str(ata_id),
                "tid": tenant_id,
                "html": resultado.ata_html,
                "meta": json.dumps(resultado.metadata),
            },
        )).first()
        assert row is not None
        versao_id: UUID = row.id

        await session.execute(
            text(
                "UPDATE atas SET versao_atual_id=:vid, status='gerada', "
                "erro_detalhe=NULL, updated_at=NOW() WHERE id=:aid"
            ),
            {"vid": str(versao_id), "aid": str(ata_id)},
        )

        await jobs_service.registrar_acao(
            session,
            tenant_id=tenant_id,
            ata_id=ata_id,
            ator_user_id=None,
            acao="geracao_concluida",
            detalhe={"versao_id": str(versao_id), "metadata": resultado.metadata},
        )

    logger.info(f"[atas/geracao] ata {ata_id} done — versao={versao_id}")
