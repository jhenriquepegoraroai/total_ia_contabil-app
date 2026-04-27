"""Storage abstraction — local, S3 (stub), Azure Blob (stub)."""

from .base import Storage, StorageError, StorageObject, tenant_source_prefix
from .factory import get_storage

__all__ = ["Storage", "StorageError", "StorageObject", "tenant_source_prefix", "get_storage"]
