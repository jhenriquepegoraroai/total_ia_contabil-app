"""Connectors — leem documentos de origens diferentes (PDF, Postgres, S3, ...)."""

from typing import Any

from .base import Connector, RawChunk
from .pdf_folder import PdfFolderConnector


def criar_connector(tipo: str, **kwargs: Any) -> Connector:
    """
    Factory de conector pelo nome (vem do CLI `--connector`).

    Para adicionar um novo connector:
      1. Crie a classe concreta neste pacote (herdando `Connector`).
      2. Adicione o branch aqui.
    """
    if tipo == "pdf_folder":
        return PdfFolderConnector(**kwargs)

    if tipo == "postgres":
        from .postgres import PostgresConnector
        return PostgresConnector(**kwargs)

    if tipo == "s3":
        from .s3 import S3PdfConnector
        return S3PdfConnector(**kwargs)

    raise ValueError(f"Connector desconhecido: {tipo!r}. Disponíveis: pdf_folder")


__all__ = ["Connector", "RawChunk", "PdfFolderConnector", "criar_connector"]
