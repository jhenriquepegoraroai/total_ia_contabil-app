"""
Entry point FastAPI — Assistente Virtual de Condomínios.

Bootstrap:
  - configura logging (loguru estruturado)
  - carrega registry de tenants no startup (fail-fast se houver erro)
  - dispõe engine SQLAlchemy no shutdown
  - registra middleware de trace_id
  - registra routers (auth, health, chat)

Em DEV, expõe `/docs` (Swagger) e `/auth/dev-token`. Em PROD, ambos seguem
acessíveis para Swagger; `/auth/dev-token` é desabilitado dentro do handler.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from api import config
from api.db import dispose_engine
from api.middleware.trace_middleware import TraceIdMiddleware
from api.routers import auth as auth_router
from api.routers import chat as chat_router
from api.routers import health as health_router
from api.tenants.registry import TenantRegistry
from api.utils.logging import configurar_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown unificados (FastAPI 0.93+)."""
    configurar_logging()
    logger.info(f"Iniciando API em APP_ENV={config.APP_ENV}")

    # Resolve diretório de configs (relativo ao módulo `api`)
    configs_dir = Path(__file__).resolve().parent / "tenants" / "configs"
    registry = TenantRegistry(configs_dir)
    registry.carregar_todos()

    # Tenants são imutáveis durante o lifecycle. Um restart é requerido para
    # alterações de config (RULES.md sobre fail-fast).
    app.state.tenant_registry = registry

    logger.info("API pronta para receber requests.")

    try:
        yield
    finally:
        logger.info("Encerrando API — disposição de recursos.")
        await dispose_engine()


app = FastAPI(
    title="Assistente Virtual de Condomínios",
    description="API multi-tenant de RAG sobre documentos de condomínios.",
    version="0.3.0",
    lifespan=lifespan,
)

# Middlewares
app.add_middleware(TraceIdMiddleware)

# Routers
app.include_router(health_router.router)
app.include_router(auth_router.router)
app.include_router(chat_router.router)
