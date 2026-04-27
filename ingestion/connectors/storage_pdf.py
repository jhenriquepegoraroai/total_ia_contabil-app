"""
StoragePdfConnector — lê PDFs do storage backend (LocalStorage, S3, etc.)
filtrando por prefixo de tenant + source.

Diferente do `pdf_folder` (que lê do filesystem direto), este connector
funciona com qualquer Storage. Ideal para uploads via UI: arquivos vão pro
storage configurado e o pipeline lê de lá.
"""

import io
import re
from datetime import date, datetime
from typing import Iterator

from loguru import logger

from api.storage import Storage, tenant_source_prefix
from .base import Connector, RawChunk


_DATE_PATTERNS = [
    (re.compile(r"(\d{4})[-_](\d{2})[-_](\d{2})"), "%Y-%m-%d"),
    (re.compile(r"(\d{2})[-_](\d{2})[-_](\d{4})"), "%d-%m-%Y"),
]
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_MIN_PARAGRAPH_CHARS = 20


class StoragePdfConnector(Connector):
    """
    Lê PDFs do storage de uma fonte específica.

    Por padrão, escaneia `<tenant_id>/sources/<source_id>/`. Caller pode
    sobrescrever o prefixo via `prefix_override` (ex: para reprocessar
    apenas uma sub-pasta).
    """

    def __init__(
        self,
        storage: Storage,
        tenant_id: str,
        source_id: str,
        *,
        prefix_override: str | None = None,
    ):
        self._storage = storage
        self._tenant_id = tenant_id
        self._source_id = source_id
        self._prefix = prefix_override or tenant_source_prefix(tenant_id, source_id)

    def describe(self) -> str:
        return f"storage_pdf:{self._prefix}"

    def read(self) -> Iterator[RawChunk]:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf não instalado.") from exc

        # storage.list_prefix é async — mas Connector.read() é síncrono por design.
        # Resolvemos com um event loop curto, isolado.
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Estamos dentro de um loop async (typical: pipeline.executar).
                # Não dá pra usar asyncio.run; usamos um helper síncrono via thread.
                raise RuntimeError("StoragePdfConnector.read() chamado dentro de event loop.")
        except RuntimeError:
            pass

        objects = asyncio.run(self._storage.list_prefix(self._prefix))
        pdfs = [o for o in objects if o.key.lower().endswith(".pdf")]
        if not pdfs:
            logger.warning(f"Nenhum PDF em {self._prefix}")
            return

        logger.info(f"[{self.describe()}] {len(pdfs)} PDFs encontrados")

        for obj in pdfs:
            try:
                yield from self._ler_pdf_do_storage(obj.key, PdfReader)
            except Exception as exc:
                logger.exception(f"Erro lendo {obj.key}: {exc}")
                continue

    def _ler_pdf_do_storage(self, key: str, PdfReader) -> Iterator[RawChunk]:
        import asyncio

        # Lê para memória — PDF inteiro em RAM. OK pra arquivos típicos
        # (atas, regulamentos < 50MB). Para arquivos enormes, refatorar
        # para streaming.
        async def _read() -> bytes:
            stream = await self._storage.open(key)
            try:
                return stream.read()
            finally:
                stream.close()

        content = asyncio.run(_read())
        file_name = key.rsplit("/", 1)[-1]
        data_valida = _extrair_data_do_nome(file_name)

        try:
            reader = PdfReader(io.BytesIO(content))
        except Exception as exc:
            logger.error(f"Falha abrindo PDF {file_name}: {exc}")
            return

        n_chunks = 0
        for n_pagina, pagina in enumerate(reader.pages, start=1):
            try:
                texto = pagina.extract_text() or ""
            except Exception as exc:
                logger.warning(f"Página {n_pagina} de {file_name}: {exc}")
                continue
            if not texto.strip():
                continue

            paragrafos = _PARAGRAPH_SPLIT.split(texto)
            for n_bloco, p in enumerate(paragrafos, start=1):
                p_clean = p.strip()
                if len(p_clean) < _MIN_PARAGRAPH_CHARS:
                    continue
                yield RawChunk(
                    file_name=file_name,
                    record_id=f"p{n_pagina}_b{n_bloco}",
                    paragraph=p_clean,
                    data_valida=data_valida,
                )
                n_chunks += 1

        logger.debug(f"[{file_name}] {n_chunks} chunks extraídos")


def _extrair_data_do_nome(file_name: str) -> date | None:
    nome_sem_ext = file_name.rsplit(".", 1)[0]
    for regex, fmt in _DATE_PATTERNS:
        m = regex.search(nome_sem_ext)
        if not m:
            continue
        try:
            return datetime.strptime(m.group(0).replace("_", "-"), fmt).date()
        except ValueError:
            continue
    return None
