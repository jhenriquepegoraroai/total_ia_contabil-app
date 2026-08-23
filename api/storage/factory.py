"""
Factory de Storage — escolhe a impl baseado em config.STORAGE_PROVIDER.

Singleton process-wide (lru_cache). Trocar provider exige restart.
"""

from functools import lru_cache

from loguru import logger

from api import config

from .base import Storage
from .local import LocalStorage


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    provider = config.STORAGE_PROVIDER.lower()
    logger.info(f"Inicializando storage provider={provider}")

    if provider == "local":
        return LocalStorage(config.STORAGE_LOCAL_PATH)

    if provider == "s3":
        from .s3 import S3Storage
        return S3Storage(
            bucket=__getattr_or_raise("S3_BUCKET"),
            region=__getattr_or_raise("AWS_REGION"),
        )

    if provider == "azure_blob":
        from .azure_blob import AzureBlobStorage
        # Connection string tem prioridade — cobre o caso DEV (Azurite) e
        # PROD com conn string. Se ausente, cai no par account+container
        # (assume Managed Identity ou variantes setadas via env).
        conn = config.AZURE_STORAGE_CONNECTION_STRING or None
        return AzureBlobStorage(
            account=config.AZURE_STORAGE_ACCOUNT or __getattr_or_raise("AZURE_STORAGE_ACCOUNT"),
            container=config.AZURE_BLOB_CONTAINER or __getattr_or_raise("AZURE_BLOB_CONTAINER"),
            connection_string=conn,
            public_endpoint=config.AZURE_BLOB_PUBLIC_ENDPOINT or None,
        )

    raise ValueError(
        f"STORAGE_PROVIDER='{provider}' desconhecido. "
        f"Aceitáveis: local | s3 | azure_blob"
    )


def __getattr_or_raise(env_name: str) -> str:
    import os
    val = os.getenv(env_name)
    if not val:
        raise RuntimeError(
            f"STORAGE_PROVIDER requer variável de ambiente '{env_name}', mas não está definida."
        )
    return val
