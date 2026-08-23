"""
AzureBlobStorage — Azure Blob Storage (Fase 6.2 ATIVA).

Usa a versão asyncio do azure-storage-blob. Em produção, autenticação via
Managed Identity (recomendado) ou connection string. Em DEV/local, account
key ou SAS token.
"""

import io
from datetime import UTC, datetime, timedelta
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
        public_endpoint: str | None = None,
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
        # Endpoint público que aparece nas SAS URLs (usado pelo browser).
        # Em DEV, aponta pro Azurite via localhost; em prod, blob.core.windows.net.
        # Se não vier, deriva de account_name ou da conn string.
        self._public_endpoint = public_endpoint or self._derivar_public_endpoint()

        # Quando só conn string vem, extrai o account_key dela pra poder
        # gerar SAS (`generate_blob_sas` precisa da key).
        if connection_string and not account_key:
            self._account_key = self._extrair_account_key(connection_string)

        if not (sas_token or self._account_key or connection_string):
            logger.info(
                "AzureBlobStorage sem credencial explícita — usando "
                "Managed Identity (recomendado em prod). signed_url_upload "
                "exige account_key ou User Delegation Key."
            )

        logger.info(
            f"AzureBlobStorage iniciado account={account} container={container} "
            f"public_endpoint={self._public_endpoint}"
        )

    def _derivar_public_endpoint(self) -> str:
        """Deriva endpoint público se não foi informado explicitamente."""
        if self._connection_string:
            for parte in self._connection_string.split(";"):
                if parte.startswith("BlobEndpoint="):
                    return parte.split("=", 1)[1].rstrip("/")
        # Default: Azure real
        return f"https://{self._account}.blob.core.windows.net"

    @staticmethod
    def _extrair_account_key(conn_str: str) -> str | None:
        for parte in conn_str.split(";"):
            if parte.startswith("AccountKey="):
                return parte.split("=", 1)[1]
        return None

    def _service_client(self):
        """Cria BlobServiceClient para uma operação. Caller fecha com `async with`."""
        from azure.identity.aio import DefaultAzureCredential
        from azure.storage.blob.aio import BlobServiceClient

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
            last_modified=datetime.now(UTC),
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
            # Import lazy, como no resto do módulo: o SDK do Azure só é
            # exigido quando este provider está em uso.
            from azure.core.exceptions import ResourceNotFoundError

            try:
                await blob.delete_blob()
            except ResourceNotFoundError:
                # Delete é idempotente: blob que já não existe não é erro.
                # Só esse caso é engolido — falha de credencial ou de rede
                # continua propagando (RULES: `except: pass` é proibido).
                logger.debug(f"delete no-op, blob inexistente: {key}")

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
        """Gera SAS URL de LEITURA (precisa account_key ou User Delegation Key)."""
        return self._gerar_sas(
            key=key,
            expires_in_seconds=expires_in_seconds,
            permission_kwargs={"read": True},
        )

    async def signed_url_upload(
        self,
        key: str,
        *,
        expires_in_seconds: int = 1800,
        content_type: str | None = None,
    ) -> str:
        """
        Gera SAS URL de UPLOAD (PUT direto pelo browser/cliente).

        Permissões: write + create. Cliente precisa enviar o header
        `x-ms-blob-type: BlockBlob` no PUT. Se `content_type` for passado,
        deve coincidir com o `Content-Type` do PUT do cliente.
        """
        kwargs: dict[str, object] = {"write": True, "create": True}
        return self._gerar_sas(
            key=key,
            expires_in_seconds=expires_in_seconds,
            permission_kwargs=kwargs,
        )

    def _gerar_sas(
        self,
        *,
        key: str,
        expires_in_seconds: int,
        permission_kwargs: dict,
    ) -> str:
        """Helper interno — monta SAS URL completa usando o public_endpoint."""
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        if not self._account_key:
            raise StorageError(
                "signed_url do Azure Blob requer account_key ou User Delegation Key. "
                "Implementar Managed Identity + UDK em prod."
            )

        sas = generate_blob_sas(
            account_name=self._account,
            container_name=self._container,
            blob_name=key,
            account_key=self._account_key,
            permission=BlobSasPermissions(**permission_kwargs),
            expiry=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )
        # Usa endpoint público (em DEV aponta pro localhost do Azurite, em
        # prod pro blob.core.windows.net). O endpoint já vem sem `/`-final.
        return f"{self._public_endpoint}/{self._container}/{key}?{sas}"

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
