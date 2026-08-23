"""
CsvFolderConnector — lê arquivos .csv de uma pasta e produz `RawChunk`s.

Sem dependência externa — usa `csv` da stdlib. Padrão de mapeamento de
colunas é o mesmo do `ExcelFolderConnector`.
"""

import csv
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

from loguru import logger

from .base import Connector, RawChunk


class CsvFolderConnector(Connector):
    def __init__(
        self,
        path: str,
        *,
        coluna_texto: str,
        coluna_referencia: str | None = None,
        coluna_data: str | None = None,
        referencia_default: str | None = None,
        delimiter: str = ",",
        encoding: str = "utf-8",
        recursive: bool = False,
    ):
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(f"Pasta não existe: {self._path}")
        if not self._path.is_dir():
            raise NotADirectoryError(f"Path não é diretório: {self._path}")

        if not coluna_texto:
            raise ValueError("CsvFolderConnector exige `coluna_texto`.")

        self._coluna_texto = coluna_texto
        self._coluna_ref = coluna_referencia
        self._coluna_data = coluna_data
        self._referencia_default = referencia_default
        self._delimiter = delimiter
        self._encoding = encoding
        self._recursive = recursive

    def describe(self) -> str:
        return f"csv_folder:{self._path}"

    def read(self) -> Iterator[RawChunk]:
        pattern = "**/*.csv" if self._recursive else "*.csv"
        arquivos = sorted(p for p in self._path.glob(pattern))
        if not arquivos:
            logger.warning(f"Nenhum CSV em {self._path}")
            return

        for arquivo in arquivos:
            try:
                yield from self._ler_arquivo(arquivo)
            except Exception as exc:
                logger.exception(f"Erro lendo {arquivo.name}: {exc}")

    def _ler_arquivo(self, arquivo: Path) -> Iterator[RawChunk]:
        with open(arquivo, encoding=self._encoding, newline="") as f:
            reader = csv.DictReader(f, delimiter=self._delimiter)
            if self._coluna_texto not in (reader.fieldnames or []):
                logger.error(
                    f"{arquivo.name}: coluna_texto '{self._coluna_texto}' não encontrada. "
                    f"Colunas: {reader.fieldnames}"
                )
                return

            for n_row, row in enumerate(reader, start=2):
                texto = (row.get(self._coluna_texto) or "").strip()
                if not texto:
                    continue

                referencia = None
                if self._coluna_ref:
                    v = row.get(self._coluna_ref)
                    referencia = (v or "").strip() or None
                if not referencia:
                    referencia = self._referencia_default

                data_valida: date | None = None
                if self._coluna_data:
                    v = row.get(self._coluna_data)
                    if v:
                        v = v.strip()
                        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                            try:
                                data_valida = datetime.strptime(v, fmt).date()
                                break
                            except ValueError:
                                continue

                try:
                    yield RawChunk(
                        file_name=arquivo.name,
                        record_id=f"row{n_row}",
                        paragraph=texto,
                        data_valida=data_valida,
                        referencia=referencia,
                    )
                except Exception as exc:
                    logger.warning(f"{arquivo.name} linha {n_row}: {exc}")
                    continue
