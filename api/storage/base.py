"""
Interface Storage. Cada implementação (local, S3, Azure Blob) cumpre o mesmo
contrato. Toda chave de objeto é prefixada por tenant_id e ID da fonte —
isolamento mantido mesmo quando o storage é compartilhado.

Convenção de keys:
    <tenant_id>/sources/<source_id>/<filename>

Ex: lello/sources/3f2a.../ata-2024-03-15.pdf
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO


class StorageError(RuntimeError):
    """Erro genérico de storage — wrap de erros das libs subjacentes."""


@dataclass(frozen=True, slots=True)
class StorageObject:
    """Metadados de um objeto guardado."""

    key: str
    size_bytes: int
    content_type: str | None
    last_modified: datetime | None = None


class Storage(ABC):
    """Interface mínima. Implementações: LocalStorage, S3Storage, AzureBlobStorage."""

    @abstractmethod
    async def save(
        self,
        key: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> StorageObject:
        """Persiste um arquivo. `key` é o caminho relativo (com tenant_id prefixado)."""
        ...

    @abstractmethod
    async def open(self, key: str) -> BinaryIO:
        """
        Abre um arquivo para leitura (binary stream). Caller é responsável
        por fechar o stream.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove um arquivo. Idempotente (não levanta se não existe)."""
        ...

    @abstractmethod
    async def list_prefix(self, prefix: str) -> list[StorageObject]:
        """Lista objetos com `key` começando com `prefix`."""
        ...

    @abstractmethod
    async def signed_url(self, key: str, *, expires_in_seconds: int = 600) -> str:
        """
        Gera URL temporária de leitura. Em LocalStorage, retorna URL servida
        pela própria API; em S3/Azure, presigned URL nativo.
        """
        ...

    async def signed_url_upload(
        self,
        key: str,
        *,
        expires_in_seconds: int = 1800,
        content_type: str | None = None,
    ) -> str:
        """
        Gera URL temporária para UPLOAD direto (PUT) pelo cliente. Em prod
        com Azure Blob/S3, evita que o backend seja proxy de arquivos
        grandes (áudios de 2h podem passar de 100MB).

        Implementação opcional — providers que não suportam levantam
        NotImplementedError. Hoje só Azure Blob implementa (Fase 6 STT).
        """
        raise NotImplementedError(
            f"{type(self).__name__} não suporta signed_url_upload. "
            "Use STORAGE_PROVIDER=azure_blob."
        )

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """True se o objeto existe."""
        ...


def tenant_source_prefix(tenant_id: str, source_id: str) -> str:
    """Convenção de key. Centralizada aqui para auditoria e validação."""
    if not tenant_id or "/" in tenant_id:
        raise ValueError(f"tenant_id inválido: {tenant_id!r}")
    if not source_id or "/" in source_id:
        raise ValueError(f"source_id inválido: {source_id!r}")
    return f"{tenant_id}/sources/{source_id}/"
