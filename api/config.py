"""
Configuração da API — lê secrets exclusivamente de variáveis de ambiente.

REGRA CRÍTICA (RULES.md #11): nenhum fallback de string hardcoded. Se faltar
variável obrigatória, a aplicação derruba o boot com mensagem clara em vez
de seguir com valor de dev "só pra funcionar".
"""

import os
from typing import Final


class ConfigError(RuntimeError):
    """Erro de configuração — variável obrigatória ausente ou inválida."""


def _required(nome: str) -> str:
    """Lê variável obrigatória do ambiente. Sem fallback de string."""
    valor = os.getenv(nome)
    if not valor:
        raise ConfigError(
            f"Variável de ambiente obrigatória '{nome}' não está definida. "
            f"Veja .env.example para a lista completa."
        )
    return valor


def _optional(nome: str, default: str) -> str:
    """Lê variável opcional. Default é literal de configuração, não secret."""
    return os.getenv(nome, default)


def _int(nome: str, default: int) -> int:
    valor = os.getenv(nome)
    if valor is None:
        return default
    try:
        return int(valor)
    except ValueError as exc:
        raise ConfigError(f"Variável '{nome}' deve ser um inteiro, recebi: {valor!r}") from exc


# -----------------------------------------------------------------------------
# Aplicação
# -----------------------------------------------------------------------------
APP_ENV: Final[str] = _optional("APP_ENV", "development")
LOG_LEVEL: Final[str] = _optional("LOG_LEVEL", "INFO")
IS_PRODUCTION: Final[bool] = APP_ENV == "production"

# -----------------------------------------------------------------------------
# Banco de dados
# -----------------------------------------------------------------------------
DATABASE_URL: Final[str] = _required("DATABASE_URL")

# -----------------------------------------------------------------------------
# Redis
# -----------------------------------------------------------------------------
REDIS_URL: Final[str] = _optional("REDIS_URL", "redis://localhost:6379/0")

# -----------------------------------------------------------------------------
# OpenAI
# -----------------------------------------------------------------------------
OPEN_AI_KEY: Final[str] = _required("OPEN_AI_KEY")
EMBEDDING_MODEL: Final[str] = _optional("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIMENSIONS: Final[int] = _int("EMBEDDING_DIMENSIONS", 3072)
COMPLETION_MODEL: Final[str] = _optional("COMPLETION_MODEL", "gpt-5.2")

# -----------------------------------------------------------------------------
# JWT
# -----------------------------------------------------------------------------
SECRET_KEY_JWT: Final[str] = _required("SECRET_KEY_JWT")
JWT_ALGORITHM: Final[str] = _optional("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES: Final[int] = _int("JWT_EXPIRES_MINUTES", 480)

# -----------------------------------------------------------------------------
# Pipeline de ingestão (defaults espelhando script Spark da Lello)
# -----------------------------------------------------------------------------
INGESTION_BATCH_SIZE: Final[int] = _int("INGESTION_BATCH_SIZE", 100)
INGESTION_MAX_WORKERS: Final[int] = _int("INGESTION_MAX_WORKERS", 10)
INGESTION_OPENAI_TIMEOUT: Final[int] = _int("INGESTION_OPENAI_TIMEOUT", 30)
INGESTION_OPENAI_MAX_RETRIES: Final[int] = _int("INGESTION_OPENAI_MAX_RETRIES", 3)

# Limite do modelo text-embedding-3-large — não vem do env, é spec do modelo.
EMBEDDING_MAX_TOKENS: Final[int] = 8191

# -----------------------------------------------------------------------------
# RAG / Busca
# -----------------------------------------------------------------------------
DEFAULT_TOP_K: Final[int] = _int("DEFAULT_TOP_K", 8)
DEFAULT_SIMILARITY_THRESHOLD: Final[float] = float(
    _optional("DEFAULT_SIMILARITY_THRESHOLD", "0.30")
)

# -----------------------------------------------------------------------------
# Storage
# -----------------------------------------------------------------------------
STORAGE_PROVIDER: Final[str] = _optional("STORAGE_PROVIDER", "local")
STORAGE_LOCAL_PATH: Final[str] = _optional("STORAGE_LOCAL_PATH", "/app/data/storage")

# -----------------------------------------------------------------------------
# Tenants
# -----------------------------------------------------------------------------
TENANTS_CONFIG_DIR: Final[str] = _optional("TENANTS_CONFIG_DIR", "tenants/configs")
