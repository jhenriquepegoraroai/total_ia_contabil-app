"""
AzureBlobStorage — stub para Azure Blob Storage.

Mesma situação do S3Storage: estrutura pronta, ativação na Fase 6.2.

Lib alvo: azure-storage-blob (com versão asyncio).
"""

from typing import BinaryIO

from loguru import logger

from .base import Storage, StorageError, StorageObject


class AzureBlobStorage(Storage):
    def __init__(self, account: str, container: str):
        self._account = account
        self._container = container
        logger.warning(
            "AzureBlobStorage em modo stub — ativar na Fase 6.2 (instalar "
            "azure-storage-blob e popular credenciais)."
        )

    def _not_ready(self) -> StorageError:
        return StorageError(
            "AzureBlobStorage não está habilitado nesta fase. "
            "Veja docstring de api/storage/azure_blob.py."
        )

    async def save(
        self,
        key: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> StorageObject:
        raise self._not_ready()

    async def open(self, key: str) -> BinaryIO:
        raise self._not_ready()

    async def delete(self, key: str) -> None:
        raise self._not_ready()

    async def list_prefix(self, prefix: str) -> list[StorageObject]:
        raise self._not_ready()

    async def signed_url(self, key: str, *, expires_in_seconds: int = 600) -> str:
        raise self._not_ready()

    async def exists(self, key: str) -> bool:
        raise self._not_ready()
