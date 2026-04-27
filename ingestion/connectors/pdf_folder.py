"""
PdfFolderConnector — lê PDFs de uma pasta local e quebra em parágrafos.

Estratégia de chunking:
  - Cada PDF gera N chunks
  - 1 chunk = 1 "parágrafo" (split por quebras de linha duplas / parágrafos de layout)
  - record_id = "p<página>_b<bloco>" (estável entre execuções para idempotência)
  - data_valida = tentativa de extrair do nome do arquivo (ex: "ATA_2024-03-15.pdf");
    None se não conseguir parsear

Para extração mais sofisticada (OCR de PDF escaneado, layout análise),
substituir por outro connector dedicado no futuro.
"""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from loguru import logger

from .base import Connector, RawChunk


# Padrão de data no nome do arquivo. Aceita: 2024-03-15, 2024_03_15, 15-03-2024, 15_03_2024.
_DATE_PATTERNS = [
    (re.compile(r"(\d{4})[-_](\d{2})[-_](\d{2})"), "%Y-%m-%d"),
    (re.compile(r"(\d{2})[-_](\d{2})[-_](\d{4})"), "%d-%m-%Y"),
]

# Quebra de parágrafo: 2+ newlines (com espaços/tabs entre eles)
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")

# Mínimo de caracteres para um parágrafo entrar — descarta cabeçalhos/rodapés curtos.
_MIN_PARAGRAPH_CHARS = 20


class PdfFolderConnector(Connector):
    """Lê todos os PDFs de uma pasta (não-recursivo) e produz chunks."""

    def __init__(self, path: str, *, recursive: bool = False):
        self._path = Path(path)
        self._recursive = recursive
        if not self._path.exists():
            raise FileNotFoundError(f"Pasta não existe: {self._path}")
        if not self._path.is_dir():
            raise NotADirectoryError(f"Path não é diretório: {self._path}")

    def describe(self) -> str:
        return f"pdf_folder:{self._path}"

    def read(self) -> Iterator[RawChunk]:
        # Import lazy: pypdf é dependência opcional do pipeline (não da API).
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "pypdf não instalado. Instale com: pip install pypdf"
            ) from exc

        pattern = "**/*.pdf" if self._recursive else "*.pdf"
        pdfs = sorted(self._path.glob(pattern))
        if not pdfs:
            logger.warning(f"Nenhum PDF encontrado em {self._path}")
            return

        logger.info(f"[{self.describe()}] {len(pdfs)} PDFs encontrados")

        for pdf_path in pdfs:
            try:
                yield from self._ler_pdf(pdf_path)
            except Exception as exc:
                logger.exception(f"Erro lendo PDF {pdf_path.name}: {exc}")
                continue

    def _ler_pdf(self, pdf_path: Path) -> Iterator[RawChunk]:
        from pypdf import PdfReader  # type: ignore

        file_name = pdf_path.name
        data_valida = _extrair_data_do_nome(file_name)

        try:
            reader = PdfReader(str(pdf_path))
        except Exception as exc:
            logger.error(f"Falha abrindo PDF {file_name}: {exc}")
            return

        n_chunks = 0
        for n_pagina, pagina in enumerate(reader.pages, start=1):
            try:
                texto = pagina.extract_text() or ""
            except Exception as exc:
                logger.warning(f"Falha extraindo texto da página {n_pagina} de {file_name}: {exc}")
                continue

            if not texto.strip():
                continue

            paragrafos = _PARAGRAPH_SPLIT.split(texto)
            for n_bloco, paragrafo in enumerate(paragrafos, start=1):
                paragrafo_clean = paragrafo.strip()
                if len(paragrafo_clean) < _MIN_PARAGRAPH_CHARS:
                    continue

                yield RawChunk(
                    file_name=file_name,
                    record_id=f"p{n_pagina}_b{n_bloco}",
                    paragraph=paragrafo_clean,
                    data_valida=data_valida,
                )
                n_chunks += 1

        logger.debug(f"[{file_name}] {n_chunks} chunks extraídos")


def _extrair_data_do_nome(file_name: str) -> date | None:
    """Tenta inferir data do nome do arquivo. Retorna None se não conseguir."""
    nome_sem_ext = file_name.rsplit(".", 1)[0]
    for regex, fmt in _DATE_PATTERNS:
        match = regex.search(nome_sem_ext)
        if not match:
            continue
        try:
            return datetime.strptime(match.group(0).replace("_", "-"), fmt).date()
        except ValueError:
            continue
    return None
