"""
AzureBlobPdfConnector — lê PDFs de um container Azure Blob para tempdir
e usa o `PdfFolderConnector` para parsing.

Mesma estratégia do `S3PdfConnector` — download-then-parse (PDFs típicos
< 50 MB, simplifica reuso de pypdf).
"""

import asyncio
import re
import shutil
import tempfile
from pathlib import Path
from typing import Iterator

from loguru import logger

from .base import Connector, RawChunk
from .pdf_folder import PdfFolderConnector


_PDF_RE = re.compile(r"\.pdf$", re.IGNORECASE)


class AzureBlobPdfConnector(Connector):
    """Lê PDFs de `<account>/<container>/<prefix>/*.pdf` via azure-storage-blob async."""

    def __init__(
        self,
        *,
        account: str,
        container: str,
        prefix: str = "",
        sas_token: str | None = None,
        account_key: str | None = None,
        connection_string: str | None = None,
    ):
        try:
            from azure.storage.blob.aio import BlobServiceClient  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "azure-storage-blob não instalado — não é possível usar AzureBlobPdfConnector."
            ) from exc

        self._account = account
        self._container = container
        self._prefix = prefix
        self._sas_token = sas_token
        self._account_key = account_key
        self._connection_string = connection_string
        self._tempdir: Path | None = None

    def describe(self) -> str:
        return f"azure_blob:{self._account}/{self._container}/{self._prefix}"

    def read(self) -> Iterator[RawChunk]:
        downloaded = asyncio.run(self._baixar_pdfs())
        if not downloaded:
            logger.warning(f"[azure_blob] nenhum PDF em {self.describe()}")
            return

        try:
            sub_connector = PdfFolderConnector(path=str(downloaded), recursive=True)
            yield from sub_connector.read()
        finally:
            self._limpar_tempdir()

    async def _baixar_pdfs(self) -> Path:
        from azure.storage.blob.aio import BlobServiceClient
        from azure.identity.aio import DefaultAzureCredential

        self._tempdir = Path(tempfile.mkdtemp(prefix="avc_azblob_"))

        if self._connection_string:
            client = BlobServiceClient.from_connection_string(self._connection_string)
        else:
            url = f"https://{self._account}.blob.core.windows.net"
            if self._sas_token:
                client = BlobServiceClient(account_url=f"{url}?{self._sas_token}")
            elif self._account_key:
                client = BlobServiceClient(account_url=url, credential=self._account_key)
            else:
                client = BlobServiceClient(account_url=url, credential=DefaultAzureCredential())

        baixados = 0
        async with client:
            container_client = client.get_container_client(self._container)
            async for blob in container_client.list_blobs(name_starts_with=self._prefix):
                if not _PDF_RE.search(blob.name):
                    continue
                nome = Path(blob.name).name
                destino = self._tempdir / nome
                try:
                    blob_client = container_client.get_blob_client(blob.name)
                    downloader = await blob_client.download_blob()
                    body = await downloader.readall()
                    destino.write_bytes(body)
                    baixados += 1
                except Exception as exc:
                    logger.warning(f"[azure_blob] falha baixando {blob.name}: {exc}")

        logger.info(f"[azure_blob] {baixados} PDFs baixados em {self._tempdir}")
        return self._tempdir

    def _limpar_tempdir(self) -> None:
        if self._tempdir and self._tempdir.exists():
            try:
                shutil.rmtree(self._tempdir)
                logger.debug(f"[azure_blob] tempdir removido: {self._tempdir}")
            except Exception as exc:
                logger.warning(f"falha removendo tempdir {self._tempdir}: {exc}")
            self._tempdir = None
