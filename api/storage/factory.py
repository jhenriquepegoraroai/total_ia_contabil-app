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
        return AzureBlobStorage(
            account=__getattr_or_raise("AZURE_STORAGE_ACCOUNT"),
            container=__getattr_or_raise("AZURE_BLOB_CONTAINER"),
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
