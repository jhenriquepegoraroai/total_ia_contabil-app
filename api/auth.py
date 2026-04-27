"""
Autenticação JWT.

REGRA CRÍTICA (RULES.md #4): `tenant_id` é extraído SEMPRE do JWT —
nunca do body/query. Cliente não pode escolher tenant arbitrário.

Endpoints de auth:
  - POST /auth/login            (produção — recebe email+senha+tenant_id)
  - POST /auth/dev-token        (DESENVOLVIMENTO — gera token sem credencial)

O endpoint de dev-token só funciona se `APP_ENV=development`. Em produção
ele é registrado como 404.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from api import config


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


class TokenPayload(BaseModel):
    """Claims do JWT — tudo que precisamos saber sobre o portador."""

    sub: str          # user_id ou e-mail (subject)
    tenant_id: str
    role: str = "morador"
    exp: int


class CurrentUser(BaseModel):
    """Usuário autenticado da request atual."""

    user_id: str
    tenant_id: str
    role: str


# =============================================================================
# Geração de token
# =============================================================================
def criar_token(*, sub: str, tenant_id: str, role: str = "morador") -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRES_MINUTES)
    payload = {
        "sub": sub,
        "tenant_id": tenant_id,
        "role": role,
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
# Dependency injection — usar com `Depends(usuario_atual)` nos handlers
# =============================================================================
async def usuario_atual(
    request: Request,
    token: Annotated[str | None, Depends(_oauth2_scheme)] = None,
) -> CurrentUser:
    """
    Extrai o usuário do JWT do header `Authorization: Bearer <token>`.
    Falha com 401 se faltar ou for inválido.
    """
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
    )
