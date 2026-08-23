"""
S3PdfConnector — lê PDFs de um bucket S3 do cliente, baixa para uma pasta
temporária, e usa o `PdfFolderConnector` para parsing/chunking. Após uso,
limpa o tempdir.

Estratégia de download-then-parse, em vez de stream, porque:
  - PDFs típicos < 50 MB (atas, regulamentos);
  - pypdf precisa de seek aleatório, mais simples ler do filesystem;
  - permite reaproveitar 100% do PdfFolderConnector existente.

Para volumes grandes (> 1000 PDFs), refatorar para baixar em batches.
"""

import asyncio
import re
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

from loguru import logger

from .base import Connector, RawChunk
from .pdf_folder import PdfFolderConnector

_PDF_RE = re.compile(r"\.pdf$", re.IGNORECASE)


class S3PdfConnector(Connector):
    """
    Lê PDFs de `s3://<bucket>/<prefix>` e produz `RawChunk`s via PdfFolder.

    O parsing é o mesmo do upload local — só muda a origem dos arquivos.
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str = "sa-east-1",
        prefix: str = "",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ):
        try:
            import aioboto3  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "aioboto3 não instalado — não é possível usar S3PdfConnector."
            ) from exc

        self._bucket = bucket
        self._region = region
        self._prefix = prefix
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._tempdir: Path | None = None

    def describe(self) -> str:
        return f"s3:s3://{self._bucket}/{self._prefix}"

    def read(self) -> Iterator[RawChunk]:
        # 1. Baixar PDFs do bucket pra tempdir.
        # 2. Reusar PdfFolderConnector apontando pro tempdir.
        # 3. Limpar tempdir ao final.
        downloaded = asyncio.run(self._baixar_pdfs())
        if not downloaded:
            logger.warning(f"[s3] nenhum PDF em s3://{self._bucket}/{self._prefix}")
            return

        try:
            sub_connector = PdfFolderConnector(path=str(downloaded), recursive=True)
            yield from sub_connector.read()
        finally:
            self._limpar_tempdir()

    async def _baixar_pdfs(self) -> Path:
        """Baixa todos os .pdf do prefix para um tempdir e retorna o path."""
        import aioboto3

        self._tempdir = Path(tempfile.mkdtemp(prefix="avc_s3_"))

        kwargs: dict = {"region_name": self._region}
        # Em DEV podemos passar credenciais explicitas; em prod usa IAM role.
        session_kwargs: dict = {}
        if self._access_key_id and self._secret_access_key:
            session_kwargs["aws_access_key_id"] = self._access_key_id
            session_kwargs["aws_secret_access_key"] = self._secret_access_key

        session = aioboto3.Session(**session_kwargs)
        baixados = 0
        async with session.client("s3", **kwargs) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not _PDF_RE.search(key):
                        continue
                    nome = Path(key).name
                    destino = self._tempdir / nome
                    try:
                        resp = await s3.get_object(Bucket=self._bucket, Key=key)
                        body = await resp["Body"].read()
                        destino.write_bytes(body)
                        baixados += 1
                    except Exception as exc:
                        logger.warning(f"[s3] falha baixando {key}: {exc}")

        logger.info(f"[s3] {baixados} PDFs baixados em {self._tempdir}")
        return self._tempdir

    def _limpar_tempdir(self) -> None:
        if self._tempdir and self._tempdir.exists():
            try:
                shutil.rmtree(self._tempdir)
                logger.debug(f"[s3] tempdir removido: {self._tempdir}")
            except Exception as exc:
                logger.warning(f"falha removendo tempdir {self._tempdir}: {exc}")
            self._tempdir = None
