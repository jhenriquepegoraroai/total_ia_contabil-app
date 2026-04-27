"""
Endpoints de autenticação.

POST /auth/login          email + senha → JWT (uso em produção)
POST /auth/dev-token      DEV only — sem credencial; 404 em prod
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from api import auth, config
from api.db import superadmin_session


router = APIRouter(prefix="/auth", tags=["auth"])


# =============================================================================
# Schemas
# =============================================================================
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str
    is_superadmin: bool = False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: str | None = None  # opcional para superadmin (que está em _system)


class DevTokenRequest(BaseModel):
    tenant_id: str
    user_id: str = "dev_user"
    role: str = "admin"


# =============================================================================
# Login email + senha
# =============================================================================
@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request) -> TokenResponse:
    """
    Login por email + senha. Se `tenant_id` não vier no body, busca usuário
    por email entre todos os tenants — caso de uso típico do superadmin.

    Por segurança, mensagens de erro são genéricas (não distinguem
    "email não existe" de "senha errada") para evitar enumeração de contas.
    """
    async with superadmin_session() as session:
        if payload.tenant_id:
            sql = text(
                "SELECT id, tenant_id, password_hash, role, is_superadmin, enabled "
                "FROM users WHERE tenant_id = :tid AND email = :em LIMIT 1"
            )
            params = {"tid": payload.tenant_id, "em": payload.email}
        else:
            sql = text(
                "SELECT id, tenant_id, password_hash, role, is_superadmin, enabled "
                "FROM users WHERE email = :em ORDER BY is_superadmin DESC LIMIT 1"
            )
            params = {"em": payload.email}

        row = (await session.execute(sql, params)).first()

    if row is None or not row.password_hash:
        logger.info(f"Login falhou (email não encontrado ou sem senha): {payload.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    if not row.enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário desabilitado.",
        )

    if not auth.verify_password(payload.password, row.password_hash):
        logger.info(f"Login falhou (senha errada): {payload.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
        )

    token = auth.criar_token(
        sub=str(row.id),
        tenant_id=row.tenant_id,
        role=row.role,
        is_superadmin=row.is_superadmin,
    )
    logger.info(
        f"Login OK email={payload.email} tenant={row.tenant_id} "
        f"superadmin={row.is_superadmin}"
    )
    return TokenResponse(
        access_token=token,
        tenant_id=row.tenant_id,
        user_id=str(row.id),
        is_superadmin=row.is_superadmin,
    )


# =============================================================================
# Dev token (sem credencial, só DEV)
# =============================================================================
@router.post("/dev-token", response_model=TokenResponse)
async def dev_token(payload: DevTokenRequest, request: Request) -> TokenResponse:
    """Gera um JWT para desenvolvimento. INDISPONÍVEL em produção."""
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
