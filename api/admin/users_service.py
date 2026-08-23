"""
Service layer de usuários — CRUD por tenant.

Tudo via `superadmin_session` (sem RLS): superadmin gerencia usuários de
qualquer tenant. Filtros explícitos por `tenant_id` em toda query (defesa
em profundidade).

Operações:
  - listar_users(tenant_id)
  - buscar_user(tenant_id, user_id)
  - criar_user(tenant_id, email, nome, role, password)
  - atualizar_user(tenant_id, user_id, nome, role, enabled)
  - resetar_senha(tenant_id, user_id, nova_senha)
  - deletar_user(tenant_id, user_id)

Proteções:
  - Não permite criar/editar `is_superadmin` por essa rota (use CLI)
  - Bloqueia mexer em users com is_superadmin=true
  - Bloqueia tenant '_system' (reservado para superadmins)
"""

from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api import auth

_VALID_ROLES = {"admin", "sindico", "atendente", "morador"}


# =============================================================================
# CRUD
# =============================================================================
async def listar_users(
    session: AsyncSession, tenant_id: str
) -> list[dict[str, Any]]:
    sql = text(
        """
        SELECT id, tenant_id, email, nome, role, referencia, enabled, is_superadmin,
               (password_hash IS NOT NULL) AS tem_senha,
               created_at
        FROM users
        WHERE tenant_id = :tid
        ORDER BY created_at DESC
        """
    )
    rows = (await session.execute(sql, {"tid": tenant_id})).mappings().all()
    return [dict(r) for r in rows]


async def buscar_user(
    session: AsyncSession, tenant_id: str, user_id: UUID
) -> dict[str, Any] | None:
    sql = text(
        """
        SELECT id, tenant_id, email, nome, role, referencia, enabled, is_superadmin,
               (password_hash IS NOT NULL) AS tem_senha,
               created_at
        FROM users
        WHERE tenant_id = :tid AND id = :uid
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id, "uid": str(user_id)})).mappings().first()
    return dict(row) if row else None


async def criar_user(
    session: AsyncSession,
    *,
    tenant_id: str,
    email: str,
    nome: str,
    role: str,
    password: str,
    referencia: str | None = None,
) -> UUID:
    """Cria usuário comum num tenant. Levanta ValueError em problemas."""
    _validar_tenant_e_role(tenant_id, role)
    if not password or len(password) < 8:
        raise ValueError("Senha precisa ter pelo menos 8 caracteres.")
    referencia = (referencia or "").strip() or None

    # Email único GLOBALMENTE (entre todos os tenants + superadmins).
    # O login no /auth/login resolve usuário por email só (sem tenant_id),
    # então duas contas com mesmo email em tenants diferentes criariam
    # ambiguidade — quem entra é a que aparecer primeiro no ORDER BY.
    # Constraint do DB é UNIQUE(tenant_id, email); a checagem global
    # é feita aqui na camada de serviço.
    existing = (await session.execute(
        text("SELECT tenant_id, is_superadmin FROM users WHERE email = :em"),
        {"em": email},
    )).first()
    if existing:
        if existing.is_superadmin:
            raise ValueError(
                f"Email '{email}' já está em uso por um superadmin."
            )
        raise ValueError(
            f"Email '{email}' já está em uso pelo tenant '{existing.tenant_id}'."
        )

    password_hash = auth.hash_password(password)

    try:
        row = (await session.execute(
            text(
                "INSERT INTO users "
                "(tenant_id, email, nome, role, password_hash, referencia, is_superadmin) "
                "VALUES (:tid, :em, :nm, :rl, :ph, :ref, false) RETURNING id"
            ),
            {
                "tid": tenant_id, "em": email, "nm": nome, "rl": role,
                "ph": password_hash, "ref": referencia,
            },
        )).first()
    except Exception as exc:
        if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
            raise ValueError(f"Já existe usuário com email '{email}' neste tenant.") from exc
        raise

    assert row is not None
    logger.info(f"[users] criado user {row.id} ({email}, role={role}) no tenant {tenant_id}")
    return row.id


async def atualizar_user(
    session: AsyncSession,
    *,
    tenant_id: str,
    user_id: UUID,
    nome: str | None = None,
    role: str | None = None,
    enabled: bool | None = None,
    referencia: str | None = None,
    referencia_set: bool = False,
) -> bool:
    """Edita campos não-sensíveis de um usuário comum. Retorna False se não existe ou é superadmin.

    Para limpar `referencia`, passe `referencia=None` E `referencia_set=True`.
    Sem `referencia_set`, o campo é ignorado (preserva o valor atual).
    """
    _validar_tenant(tenant_id)
    if role is not None and role not in _VALID_ROLES:
        raise ValueError(f"Role inválida '{role}'. Use {sorted(_VALID_ROLES)}.")

    # Bloqueia edição de superadmins via UI — só CLI gerencia.
    target = await buscar_user(session, tenant_id, user_id)
    if target is None:
        return False
    if target["is_superadmin"]:
        raise ValueError("Superadmins não podem ser editados via UI. Use a CLI.")

    sets, params = [], {"tid": tenant_id, "uid": str(user_id)}
    if nome is not None:
        sets.append("nome = :nm")
        params["nm"] = nome
    if role is not None:
        sets.append("role = :rl")
        params["rl"] = role
    if enabled is not None:
        sets.append("enabled = :en")
        params["en"] = enabled
    if referencia_set:
        sets.append("referencia = :ref")
        params["ref"] = (referencia or "").strip() or None

    if not sets:
        return True  # nada a mudar — não-erro

    sql = text(
        f"UPDATE users SET {', '.join(sets)} "
        "WHERE tenant_id = :tid AND id = :uid AND is_superadmin = false"
    )
    res = await session.execute(sql, params)
    return res.rowcount > 0


async def resetar_senha(
    session: AsyncSession,
    *,
    tenant_id: str,
    user_id: UUID,
    nova_senha: str,
) -> bool:
    if not nova_senha or len(nova_senha) < 8:
        raise ValueError("Senha precisa ter pelo menos 8 caracteres.")

    target = await buscar_user(session, tenant_id, user_id)
    if target is None:
        return False
    if target["is_superadmin"]:
        raise ValueError("Senha de superadmin só pode ser resetada via CLI.")

    new_hash = auth.hash_password(nova_senha)
    res = await session.execute(
        text(
            "UPDATE users SET password_hash = :ph "
            "WHERE tenant_id = :tid AND id = :uid AND is_superadmin = false"
        ),
        {"ph": new_hash, "tid": tenant_id, "uid": str(user_id)},
    )
    if res.rowcount > 0:
        logger.info(f"[users] senha resetada user={user_id} tenant={tenant_id}")
        return True
    return False


async def deletar_user(
    session: AsyncSession, *, tenant_id: str, user_id: UUID
) -> bool:
    _validar_tenant(tenant_id)
    target = await buscar_user(session, tenant_id, user_id)
    if target is None:
        return False
    if target["is_superadmin"]:
        raise ValueError("Superadmins não podem ser removidos via UI. Use a CLI.")

    res = await session.execute(
        text(
            "DELETE FROM users WHERE tenant_id = :tid AND id = :uid AND is_superadmin = false"
        ),
        {"tid": tenant_id, "uid": str(user_id)},
    )
    return res.rowcount > 0


# =============================================================================
# Validações
# =============================================================================
def _validar_tenant(tenant_id: str) -> None:
    if tenant_id == "_system":
        raise ValueError("Tenant '_system' é reservado — gerenciar via CLI.")


def _validar_tenant_e_role(tenant_id: str, role: str) -> None:
    _validar_tenant(tenant_id)
    if role not in _VALID_ROLES:
        raise ValueError(f"Role inválida '{role}'. Use {sorted(_VALID_ROLES)}.")
