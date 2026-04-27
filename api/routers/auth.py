"""
Endpoints de autenticação.

Em produção, `/auth/login` valida email+senha contra a tabela `users`
(implementação completa pendente — TODO da Fase 4 quando frontend chegar).
Por ora, expomos `/auth/dev-token` para gerar tokens em DEV sem credencial.
"""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from api import auth, config


router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str


class DevTokenRequest(BaseModel):
    tenant_id: str
    user_id: str = "dev_user"
    role: str = "admin"


@router.post("/dev-token", response_model=TokenResponse)
async def dev_token(payload: DevTokenRequest, request: Request) -> TokenResponse:
    """
    Gera um JWT para desenvolvimento. INDISPONÍVEL em produção.
    """
    if config.IS_PRODUCTION:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    registry = request.app.state.tenant_registry
    if payload.tenant_id not in registry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenant '{payload.tenant_id}' não existe",
        )

    token = auth.criar_token(
        sub=payload.user_id,
        tenant_id=payload.tenant_id,
        role=payload.role,
    )
    return TokenResponse(
        access_token=token,
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
    )
