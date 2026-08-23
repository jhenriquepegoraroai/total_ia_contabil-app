"""Testes do módulo de autenticação JWT."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from jose import jwt
from pydantic import ValidationError

from api import auth, config


def test_criar_e_decodificar_token():
    token = auth.criar_token(sub="user_123", tenant_id="lello", role="admin")
    payload = auth.decodificar_token(token)

    assert payload.sub == "user_123"
    assert payload.tenant_id == "lello"
    assert payload.role == "admin"


def test_token_invalido_levanta_401():
    with pytest.raises(HTTPException) as exc:
        auth.decodificar_token("token-falso")
    assert exc.value.status_code == 401


def test_token_assinado_com_secret_diferente_levanta():
    payload = {
        "sub": "u",
        "tenant_id": "lello",
        "role": "admin",
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
    }
    token_falso = jwt.encode(payload, "secret-errado", algorithm=config.JWT_ALGORITHM)
    with pytest.raises(HTTPException):
        auth.decodificar_token(token_falso)


def test_token_expirado_levanta():
    payload = {
        "sub": "u",
        "tenant_id": "lello",
        "role": "admin",
        "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, config.SECRET_KEY_JWT, algorithm=config.JWT_ALGORITHM)
    with pytest.raises(HTTPException):
        auth.decodificar_token(token)


def test_payload_minimo_obrigatorio():
    """Sem `tenant_id` no payload, decodificar deve falhar (Pydantic valida)."""
    payload = {
        "sub": "u",
        "role": "admin",
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(payload, config.SECRET_KEY_JWT, algorithm=config.JWT_ALGORITHM)
    # Falha por validação do TokenPayload (Pydantic) ou pelo guard HTTP —
    # o que importa é que não passa. `Exception` cru esconderia até TypeError.
    with pytest.raises((ValidationError, HTTPException)):
        auth.decodificar_token(token)
