"""
Conexão e sessão do Postgres.

A função `tenant_session` é o ponto central de defesa contra cross-tenant leak:
toda transação inicia com `SET LOCAL app.current_tenant = '<id>'`, que é o GUC
que as policies de RLS leem (ver db/migrations/001_init.sql, função
`current_tenant()`).

REGRA CRÍTICA (RULES.md #1, #2): nunca abrir uma sessão sem setar o tenant.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api import config


# Engine global. `pool_pre_ping` evita conexões mortas após restart do RDS.
_engine = create_async_engine(
    config.DATABASE_URL,
    echo=config.APP_ENV == "development" and config.LOG_LEVEL == "DEBUG",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine,
    expire_on_commit=False,
    autoflush=False,
)


@asynccontextmanager
async def tenant_session(tenant_id: str) -> AsyncIterator[AsyncSession]:
    """
    Abre uma sessão Postgres com o tenant atual setado para RLS.

    Uso:
        async with tenant_session("lello") as session:
            result = await session.execute(text("SELECT ..."))

    Ao sair do bloco, a transação faz commit (em sucesso) ou rollback (em erro).
    A configuração `app.current_tenant` é LOCAL à transação — não vaza para
    outras conexões do pool.
    """
    if not tenant_id or not isinstance(tenant_id, str):
        raise ValueError(f"tenant_id inválido: {tenant_id!r}")

    async with _session_factory() as session:
        try:
            await session.begin()
            # set_config('app.current_tenant', :tid, true) — `true` = LOCAL à transação.
            # Usar set_config (e não SET LOCAL) permite passar valor parametrizado
            # com segurança contra SQL injection.
            await session.execute(
                text("SELECT set_config('app.current_tenant', :tid, true)"),
                {"tid": tenant_id},
            )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(f"Erro em tenant_session(tenant_id={tenant_id!r}); rollback executado.")
            raise


async def dispose_engine() -> None:
    """Fecha o pool de conexões. Chamar no shutdown da aplicação."""
    await _engine.dispose()


async def is_db_healthy() -> bool:
    """Health check leve — `SELECT 1` numa conexão pool. True = OK."""
    try:
        async with _engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar_one() == 1
    except Exception:
        logger.exception("Health check do DB falhou")
        return False
