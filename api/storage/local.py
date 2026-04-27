"""
LocalStorage — guarda arquivos em filesystem local. Para DEV.

Em produção, usar S3Storage (AWS) ou AzureBlobStorage. A interface é a
mesma — basta trocar STORAGE_PROVIDER no env.
"""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from loguru import logger

from .base import Storage, StorageError, StorageObject


class LocalStorage(Storage):
    """Salva sob `<root>/` no filesystem. `root` vem do env STORAGE_LOCAL_PATH."""

    def __init__(self, root: str):
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorage iniciado em {self._root}")

    def _path(self, key: str) -> Path:
        # Defesa anti-traversal — mesmo que key venha de input externo.
        clean = key.replace("\\", "/").lstrip("/")
        if ".." in clean.split("/"):
            raise StorageError(f"Key inválida (path traversal): {key!r}")
        return self._root / clean

    async def save(
        self,
        key: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> StorageObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with open(path, "wb") as f:
            while True:
                chunk = data.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                size += len(chunk)
        return StorageObject(
            key=key,
            size_bytes=size,
            content_type=content_type,
            last_modified=datetime.now(timezone.utc),
        )

    async def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        if not path.exists():
            raise StorageError(f"Arquivo não existe: {key}")
        return open(path, "rb")

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    async def list_prefix(self, prefix: str) -> list[StorageObject]:
        prefix_clean = prefix.replace("\\", "/").lstrip("/")
        if ".." in prefix_clean.split("/"):
            raise StorageError(f"Prefix inválido: {prefix!r}")

        results: list[StorageObject] = []
        # Resolve o prefix como pasta (se termina em /) ou arquivo + glob.
        search_dir = self._root / prefix_clean
        if not search_dir.exists():
            return []
        if search_dir.is_file():
            stat = search_dir.stat()
            return [
                StorageObject(
                    key=str(search_dir.relative_to(self._root)).replace("\\", "/"),
                    size_bytes=stat.st_size,
                    content_type=None,
                    last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
                )
            ]

        for entry in sorted(search_dir.rglob("*")):
            if entry.is_file():
                stat = entry.stat()
                results.append(
                    StorageObject(
                        key=str(entry.relative_to(self._root)).replace("\\", "/"),
                        size_bytes=stat.st_size,
                        content_type=None,
                        last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
                    )
                )
        return results

    async def signed_url(self, key: str, *, expires_in_seconds: int = 600) -> str:
        # LocalStorage não tem URL real — caller usa /admin/files endpoint que
        # serve via FastAPI. Retornamos um path indicativo.
        return f"/admin/files?key={key}"

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    @property
    def root(self) -> Path:
        return self._root
