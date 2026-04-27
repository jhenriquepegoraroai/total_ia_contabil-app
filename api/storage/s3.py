"""
S3Storage — implementação para AWS S3.

Stub funcional: a estrutura está pronta, faltam credenciais reais para
testar contra um bucket. Quando ligar, basta:
    STORAGE_PROVIDER=s3
    S3_BUCKET=...
    AWS_REGION=...
    AWS_ACCESS_KEY_ID=... (ou usar IAM role no ECS/Fargate)

Lib: aioboto3 (assíncrona, baseada em boto3). Não está em requirements ainda
para não inflar o build em DEV; instalada sob demanda na primeira vez que
S3Storage for chamado em produção.
"""

from datetime import datetime, timezone
from typing import BinaryIO

from loguru import logger

from .base import Storage, StorageError, StorageObject


class S3Storage(Storage):
    """
    Implementação S3 ainda não habilitada — é stub para a Fase 6.2.

    Quando habilitar:
      pip install aioboto3
      e descomentar a importação dentro de _client().
    """

    def __init__(self, bucket: str, region: str = "sa-east-1"):
        self._bucket = bucket
        self._region = region
        logger.warning(
            "S3Storage instanciado em modo stub — operações vão levantar StorageError. "
            "Ativar na Fase 6.2 (instalar aioboto3 e popular credenciais)."
        )

    def _not_ready(self) -> StorageError:
        return StorageError(
            "S3Storage não está habilitado nesta fase. "
            "Veja docstring de api/storage/s3.py para ativar."
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
