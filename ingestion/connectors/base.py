"""
Connector — interface para leitura de documentos de origens variadas.

Cada connector lê uma origem (PDFs em pasta, tabela Postgres, bucket S3, ...)
e produz uma sequência de `RawChunk` — parágrafos prontos para o pipeline
de embeddings.

A chave de identidade `(file_name, record_id)` é definida pelo connector,
e tem que ser estável entre execuções (idempotência via content_hash depende
disso).
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class RawChunk:
    """
    Um parágrafo extraído do connector, pronto para embedding.

    Quando `referencia` vem preenchido (ex: `PostgresConnector` sabe a qual
    condomínio cada linha pertence), o pipeline usa esse valor. Se vier
    `None` (caso típico do `PdfFolderConnector`), o pipeline usa a referência
    default passada na execução.
    """

    file_name: str
    record_id: str
    paragraph: str
    data_valida: date | None = None
    referencia: str | None = None

    def __post_init__(self) -> None:
        if not self.file_name:
            raise ValueError("RawChunk.file_name não pode ser vazio")
        if not self.record_id:
            raise ValueError("RawChunk.record_id não pode ser vazio")
        if not self.paragraph or not self.paragraph.strip():
            raise ValueError(
                f"RawChunk.paragraph vazio em {self.file_name}/{self.record_id}"
            )


class Connector(ABC):
    """Lê documentos de uma origem e produz `RawChunk`s."""

    @abstractmethod
    def read(self) -> Iterator[RawChunk]:
        """
        Itera sobre os chunks da origem.

        Implementações devem ser preguiçosas (yield) quando possível para
        suportar origens grandes sem carregar tudo em memória.
        """
        ...

    @abstractmethod
    def describe(self) -> str:
        """Descrição curta para logs (ex: 'pdf_folder:./data/lello/12345')."""
        ...
