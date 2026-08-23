"""Endpoint /health — usado por load balancers, runbooks e operação."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api import config
from api.db import is_db_healthy

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str
    tenants_enabled: list[str]
    # SHA do commit implantado, não versão semântica: o que a operação precisa
    # saber é qual código está no ar. Vem de GIT_SHA/RAILWAY_GIT_COMMIT_SHA.
    version: str


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """
    Status agregado:
      - status: ok | degraded | down
      - db: ok | down
      - tenants_enabled: lista de IDs de tenants ativos
    """
    db_status = "ok" if await is_db_healthy() else "down"

    registry = request.app.state.tenant_registry
    tenants = registry.listar(only_enabled=True)

    overall = "ok" if db_status == "ok" and tenants else "degraded"

    return HealthResponse(
        status=overall,
        db=db_status,
        tenants_enabled=tenants,
        version=config.GIT_SHA,
    )
