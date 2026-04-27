"""
Endpoints de autenticação.

POST /auth/login          email + senha → JWT (uso em produção)
POST /auth/logout         limpa o cookie httpOnly (fim de sessão browser)
POST /auth/dev-token      DEV only — sem credencial; 404 em prod
"""

from fastapi import APIRouter, HTTPException, Request, Response, status
from loguru import logger
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from api import auth, config
from api.db import superadmin_session


router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    """
    Seta o JWT em cookie HttpOnly para o browser. Defesa contra XSS:
    JS da página NÃO consegue ler o token, então mesmo se houver injeção
    no front, o atacante não rouba a sessão.
    """
    response.set_cookie(
        key=auth.AUTH_COOKIE_NAME,
        value=token,
        max_age=config.JWT_EXPIRES_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=config.IS_PRODUCTION,  # em DEV, http://localhost não envia se Secure=True
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=auth.AUTH_COOKIE_NAME,
        path="/",
        samesite="lax",
        secure=config.IS_PRODUCTION,
    )


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
async def login(
    payload: LoginRequest, request: Request, response: Response
) -> TokenResponse:
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
    _set_auth_cookie(response, token)
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
# Logout — limpa o cookie httpOnly
# =============================================================================
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    _clear_auth_cookie(response)


# =============================================================================
# Dev token (sem credencial, só DEV)
# =============================================================================
@router.post("/dev-token", response_model=TokenResponse)
async def dev_token(
    payload: DevTokenRequest, request: Request, response: Response
) -> TokenResponse:
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
    _set_auth_cookie(response, token)
    return TokenResponse(
        access_token=token,
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
    )
