"""
Autenticação JWT.

REGRA CRÍTICA (RULES.md #4): `tenant_id` é extraído SEMPRE do JWT —
nunca do body/query. Cliente não pode escolher tenant arbitrário.

Fluxos:
  - POST /auth/login        — email + senha (bcrypt) → JWT (prod)
  - POST /auth/dev-token    — sem credencial, só DEV (não vai pro prod)

Superadmin: o token carrega `is_superadmin=true` quando o usuário tem essa flag
no DB. Rotas protegidas por `superadmin_required` rejeitam tokens normais.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from api import config


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Nome do cookie HttpOnly que carrega o JWT no fluxo browser. Mantemos
# também o header `Authorization: Bearer ...` para compatibilidade com
# ferramentas de teste (curl, Postman, scripts).
AUTH_COOKIE_NAME = "avc_token"


# =============================================================================
# Senhas
# =============================================================================
def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# =============================================================================
# Modelos do token
# =============================================================================
class TokenPayload(BaseModel):
    sub: str          # user_id ou e-mail (subject)
    tenant_id: str
    role: str = "morador"
    is_superadmin: bool = False
    exp: int


class CurrentUser(BaseModel):
    user_id: str
    tenant_id: str
    role: str
    is_superadmin: bool = False


# =============================================================================
# Geração / decodificação
# =============================================================================
def criar_token(
    *,
    sub: str,
    tenant_id: str,
    role: str = "morador",
    is_superadmin: bool = False,
) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRES_MINUTES)
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "role": role,
        "is_superadmin": is_superadmin,
        "exp": int(expira.timestamp()),
    }
    return jwt.encode(payload, config.SECRET_KEY_JWT, algorithm=config.JWT_ALGORITHM)


def decodificar_token(token: str) -> TokenPayload:
    try:
        data = jwt.decode(token, config.SECRET_KEY_JWT, algorithms=[config.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return TokenPayload(**data)


# =============================================================================
# Dependencies
# =============================================================================
async def usuario_atual(
    request: Request,
    token: Annotated[str | None, Depends(_oauth2_scheme)] = None,
) -> CurrentUser:
    """
    Extrai o usuário do JWT, na ordem:
      1. Header `Authorization: Bearer <token>` (curl/postman/scripts)
      2. Cookie HttpOnly `avc_token` (browser, fluxo padrão)
    """
    if not token:
        token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decodificar_token(token)
    return CurrentUser(
        user_id=payload.sub,
        tenant_id=payload.tenant_id,
        role=payload.role,
        is_superadmin=payload.is_superadmin,
    )


async def superadmin_required(
    user: Annotated[CurrentUser, Depends(usuario_atual)],
) -> CurrentUser:
    """Guard para rotas /admin/*. Rejeita usuários sem `is_superadmin`."""
    if not user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a superadmin.",
        )
    return user
