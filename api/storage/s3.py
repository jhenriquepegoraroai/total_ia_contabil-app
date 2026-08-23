"""
S3Storage — implementação para AWS S3 (Fase 6.2 ATIVA).

Usa aioboto3 (async). Em produção, IAM role do ECS/Fargate. Em DEV/local,
chaves AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY no env.

Convenção de keys: idem LocalStorage (`<tenant>/sources/<source_id>/<filename>`).
"""

import io
from datetime import UTC, datetime
from typing import BinaryIO

from loguru import logger

from .base import Storage, StorageError, StorageObject


class S3Storage(Storage):
    """Implementação S3 via aioboto3."""

    def __init__(self, bucket: str, region: str = "sa-east-1"):
        self._bucket = bucket
        self._region = region
        # Lazy import para evitar carregar aioboto3 quando provider != s3.
        try:
            import aioboto3  # noqa: F401
        except ImportError as exc:
            raise StorageError(
                "aioboto3 não instalado. Adicione `aioboto3` ao requirements "
                "para usar STORAGE_PROVIDER=s3."
            ) from exc

        self._session_factory = self._build_session_factory()
        logger.info(f"S3Storage iniciado bucket={bucket} region={region}")

    def _build_session_factory(self):
        import aioboto3
        return lambda: aioboto3.Session()

    async def save(
        self,
        key: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> StorageObject:
        body = data.read() if hasattr(data, "read") else data
        size = len(body) if isinstance(body, (bytes, bytearray)) else 0

        session = self._session_factory()
        async with session.client("s3", region_name=self._region) as s3:
            extra: dict = {}
            if content_type:
                extra["ContentType"] = content_type
            await s3.put_object(Bucket=self._bucket, Key=key, Body=body, **extra)

        return StorageObject(
            key=key,
            size_bytes=size,
            content_type=content_type,
            last_modified=datetime.now(UTC),
        )

    async def open(self, key: str) -> BinaryIO:
        """Baixa o objeto inteiro para BytesIO. Para arquivos enormes, refatorar."""
        session = self._session_factory()
        async with session.client("s3", region_name=self._region) as s3:
            try:
                resp = await s3.get_object(Bucket=self._bucket, Key=key)
            except Exception as exc:
                raise StorageError(f"S3 get_object falhou ({key}): {exc}") from exc
            body = await resp["Body"].read()
        return io.BytesIO(body)

    async def delete(self, key: str) -> None:
        session = self._session_factory()
        async with session.client("s3", region_name=self._region) as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

    async def list_prefix(self, prefix: str) -> list[StorageObject]:
        session = self._session_factory()
        out: list[StorageObject] = []
        async with session.client("s3", region_name=self._region) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    out.append(
                        StorageObject(
                            key=obj["Key"],
                            size_bytes=obj["Size"],
                            content_type=None,
                            last_modified=obj.get("LastModified"),
                        )
                    )
        return out

    async def signed_url(self, key: str, *, expires_in_seconds: int = 600) -> str:
        session = self._session_factory()
        async with session.client("s3", region_name=self._region) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in_seconds,
            )
        return url

    async def signed_url_upload(
        self,
        key: str,
        *,
        expires_in_seconds: int = 1800,
        content_type: str | None = None,
    ) -> str:
        """
        Gera presigned URL de UPLOAD (PUT direto pelo cliente).

        Equivalente ao SAS de write+create do Azure Blob: o áudio da
        assembleia vai do browser para o bucket sem passar pelo backend —
        arquivo de reunião de duas horas facilmente ultrapassa 100 MB.

        Se `content_type` for informado, ele entra na assinatura e o cliente
        precisa enviar exatamente o mesmo `Content-Type` no PUT; qualquer
        divergência faz a S3 recusar com 403.
        """
        from botocore.config import Config

        params: dict[str, str] = {"Bucket": self._bucket, "Key": key}
        if content_type:
            params["ContentType"] = content_type

        # SigV4 explícito: sem isso o botocore assina em SigV2 contra o
        # endpoint global (s3.amazonaws.com), que regiões criadas depois de
        # 2014 recusam — o PUT do cliente voltaria 400 sem explicação óbvia.
        config = Config(signature_version="s3v4", s3={"addressing_style": "virtual"})

        session = self._session_factory()
        async with session.client(
            "s3", region_name=self._region, config=config
        ) as s3:
            url = await s3.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=expires_in_seconds,
            )
        logger.debug(f"[s3] presigned upload gerado key={key} ttl={expires_in_seconds}s")
        return url

    async def exists(self, key: str) -> bool:
        session = self._session_factory()
        async with session.client("s3", region_name=self._region) as s3:
            try:
                await s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except Exception:
                return False

    @property
    def bucket(self) -> str:
        return self._bucket

    @property
    def region(self) -> str:
        return self._region
