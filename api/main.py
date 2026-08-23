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
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api import config
from api.db import dispose_engine, superadmin_session
from api.middleware.trace_middleware import TraceIdMiddleware
from api.routers import admin as admin_router
from api.routers import admin_data as admin_data_router
from api.routers import atas as atas_router
from api.routers import auth as auth_router
from api.routers import chat as chat_router
from api.routers import cobrancas as cobrancas_router
from api.routers import health as health_router
from api.routers import public_catalog as public_catalog_router
from api.routers import scores as scores_router
from api.routers import tenant_public as tenant_public_router
from api.routers import tenant_users as tenant_users_router
from api.tenants.registry import TenantRegistry
from api.utils.logging import configurar_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown unificados (FastAPI 0.93+)."""
    configurar_logging()
    logger.info(f"Iniciando API em APP_ENV={config.APP_ENV}")

    # Resolve diretório de configs (relativo ao módulo `api`) — usado como
    # seed inicial. A partir da Fase 5, a fonte de verdade é o DB.
    configs_dir = Path(__file__).resolve().parent / "tenants" / "configs"
    registry = TenantRegistry(configs_dir)

    async with superadmin_session() as session:
        await registry.carregar_todos(session)

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
    version="0.6.0",
    lifespan=lifespan,
)

# CORS — permite requisições do frontend Next.js em dev (localhost:3000/3001)
# Em produção, substituir pela URL real do app.
_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,  # necessário para enviar cookies httpOnly (JWT)
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middlewares
app.add_middleware(TraceIdMiddleware)

# Routers
app.include_router(health_router.router)
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(admin_router.router)
app.include_router(admin_data_router.router)
app.include_router(atas_router.router)
app.include_router(cobrancas_router.router)
app.include_router(scores_router.router)
app.include_router(tenant_public_router.router)
app.include_router(tenant_users_router.router)
app.include_router(public_catalog_router.router)
