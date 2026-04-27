"""
AzureBlobStorage — Azure Blob Storage (Fase 6.2 ATIVA).

Usa a versão asyncio do azure-storage-blob. Em produção, autenticação via
Managed Identity (recomendado) ou connection string. Em DEV/local, account
key ou SAS token.
"""

import io
from datetime import datetime, timedelta, timezone
from typing import BinaryIO

from loguru import logger

from .base import Storage, StorageError, StorageObject


class AzureBlobStorage(Storage):
    """
    Implementação de Storage com Azure Blob.

    Args:
        account: nome da storage account.
        container: nome do container.
        sas_token: SAS token (DEV). Em prod, preferir Managed Identity.
        account_key: account key (DEV).
        connection_string: alternativa única que carrega tudo.
    """

    def __init__(
        self,
        account: str,
        container: str,
        *,
        sas_token: str | None = None,
        account_key: str | None = None,
        connection_string: str | None = None,
    ):
        try:
            from azure.storage.blob.aio import BlobServiceClient  # noqa: F401
        except ImportError as exc:
            raise StorageError(
                "azure-storage-blob não instalado. Adicione `azure-storage-blob` "
                "aos requirements para usar STORAGE_PROVIDER=azure_blob."
            ) from exc

        self._account = account
        self._container = container
        self._sas_token = sas_token
        self._account_key = account_key
        self._connection_string = connection_string

        if not (sas_token or account_key or connection_string):
            logger.info(
                "AzureBlobStorage sem credencial explícita — usando "
                "Managed Identity (recomendado em prod)."
            )

        logger.info(f"AzureBlobStorage iniciado account={account} container={container}")

    def _service_client(self):
        """Cria BlobServiceClient para uma operação. Caller fecha com `async with`."""
        from azure.storage.blob.aio import BlobServiceClient
        from azure.identity.aio import DefaultAzureCredential

        if self._connection_string:
            return BlobServiceClient.from_connection_string(self._connection_string)

        url = f"https://{self._account}.blob.core.windows.net"
        if self._sas_token:
            return BlobServiceClient(account_url=f"{url}?{self._sas_token}")
        if self._account_key:
            return BlobServiceClient(account_url=url, credential=self._account_key)
        # Managed Identity
        return BlobServiceClient(account_url=url, credential=DefaultAzureCredential())

    async def save(
        self,
        key: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> StorageObject:
        body = data.read() if hasattr(data, "read") else data
        size = len(body) if isinstance(body, (bytes, bytearray)) else 0

        async with self._service_client() as svc:
            blob = svc.get_blob_client(container=self._container, blob=key)
            content_settings = None
            if content_type:
                from azure.storage.blob import ContentSettings
                content_settings = ContentSettings(content_type=content_type)
            await blob.upload_blob(body, overwrite=True, content_settings=content_settings)

        return StorageObject(
            key=key,
            size_bytes=size,
            content_type=content_type,
            last_modified=datetime.now(timezone.utc),
        )

    async def open(self, key: str) -> BinaryIO:
        async with self._service_client() as svc:
            blob = svc.get_blob_client(container=self._container, blob=key)
            try:
                downloader = await blob.download_blob()
                body = await downloader.readall()
            except Exception as exc:
                raise StorageError(f"Azure Blob download falhou ({key}): {exc}") from exc
        return io.BytesIO(body)

    async def delete(self, key: str) -> None:
        async with self._service_client() as svc:
            blob = svc.get_blob_client(container=self._container, blob=key)
            try:
                await blob.delete_blob()
            except Exception:
                pass  # idempotente — não levanta se já não existe

    async def list_prefix(self, prefix: str) -> list[StorageObject]:
        out: list[StorageObject] = []
        async with self._service_client() as svc:
            container = svc.get_container_client(self._container)
            async for b in container.list_blobs(name_starts_with=prefix):
                out.append(
                    StorageObject(
                        key=b.name,
                        size_bytes=b.size or 0,
                        content_type=(b.content_settings.content_type if b.content_settings else None),
                        last_modified=b.last_modified,
                    )
                )
        return out

    async def signed_url(self, key: str, *, expires_in_seconds: int = 600) -> str:
        """Gera SAS URL (precisa account_key ou User Delegation Key)."""
        from azure.storage.blob import generate_blob_sas, BlobSasPermissions

        if not self._account_key:
            # Sem account_key, geração de SAS exige User Delegation Key (Managed
            # Identity). Por simplicidade do MVP, levantamos — em prod, ativar.
            raise StorageError(
                "signed_url do Azure Blob requer account_key ou User Delegation Key. "
                "Implementar Managed Identity + UDK em prod."
            )

        sas = generate_blob_sas(
            account_name=self._account,
            container_name=self._container,
            blob_name=key,
            account_key=self._account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
        )
        return f"https://{self._account}.blob.core.windows.net/{self._container}/{key}?{sas}"

    async def exists(self, key: str) -> bool:
        async with self._service_client() as svc:
            blob = svc.get_blob_client(container=self._container, blob=key)
            try:
                await blob.get_blob_properties()
                return True
            except Exception:
                return False

    @property
    def account(self) -> str:
        return self._account

    @property
    def container(self) -> str:
        return self._container
