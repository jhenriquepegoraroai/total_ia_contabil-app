"""Endpoint /health — usado por load balancers, runbooks e operação."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.db import is_db_healthy


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str
    tenants_enabled: list[str]
    version: str = "0.3.0"


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
    )
