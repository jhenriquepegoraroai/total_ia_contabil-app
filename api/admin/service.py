"""
Service layer do admin — CRUD de tenants no DB.

Toda mutação registra entrada em `admin_audit_log` (RULES.md regra de auditoria).
Espera ser chamado dentro de `superadmin_session` (sem RLS).
"""

import json
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.tenants.models import TenantConfig


# =============================================================================
# Listagem
# =============================================================================
async def listar_tenants(session: AsyncSession) -> list[dict[str, Any]]:
    """
    Lista todos os tenants com métricas básicas.

    Inclui contagem de documents, embeddings e usuários por tenant.
    Exclui o tenant `_system` (interno).
    """
    sql = text(
        """
        SELECT
            t.id,
            t.nome_empresa,
            t.enabled,
            t.created_at,
            t.updated_at,
            tc.config_json,
            COALESCE(d.qtd, 0) AS qtde_documents,
            COALESCE(e.qtd, 0) AS qtde_embeddings,
            COALESCE(u.qtd, 0) AS qtde_users
        FROM tenants t
        LEFT JOIN tenant_configs tc ON tc.tenant_id = t.id
        LEFT JOIN (
            SELECT tenant_id, COUNT(*) AS qtd FROM documents GROUP BY tenant_id
        ) d ON d.tenant_id = t.id
        LEFT JOIN (
            SELECT tenant_id, COUNT(*) AS qtd FROM documents_embeddings GROUP BY tenant_id
        ) e ON e.tenant_id = t.id
        LEFT JOIN (
            SELECT tenant_id, COUNT(*) AS qtd FROM users GROUP BY tenant_id
        ) u ON u.tenant_id = t.id
        WHERE t.id <> '_system'
        ORDER BY t.created_at DESC
        """
    )
    rows = (await session.execute(sql)).mappings().all()
    return [dict(r) for r in rows]


async def buscar_tenant(session: AsyncSession, tenant_id: str) -> dict[str, Any] | None:
    """Detalhe completo de um tenant. None se não existe."""
    sql = text(
        """
        SELECT t.id, t.nome_empresa, t.enabled, t.created_at, t.updated_at,
               tc.config_json, tc.schema_version
        FROM tenants t
        LEFT JOIN tenant_configs tc ON tc.tenant_id = t.id
        WHERE t.id = :tid
        """
    )
    row = (await session.execute(sql, {"tid": tenant_id})).mappings().first()
    return dict(row) if row else None


# =============================================================================
# Criação
# =============================================================================
async def criar_tenant(
    session: AsyncSession,
    config: TenantConfig,
    *,
    actor_user_id: str,
    actor_email: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    Cria tenant + tenant_config dentro de uma transação.
    Levanta ValueError se tenant_id já existe.
    """
    if config.tenant_id == "_system":
        raise ValueError("'_system' é um tenant reservado e não pode ser criado.")

    # 1. Tenants (chave primária)
    try:
        await session.execute(
            text(
                "INSERT INTO tenants (id, nome_empresa, enabled) "
                "VALUES (:tid, :nome, :en)"
            ),
            {"tid": config.tenant_id, "nome": config.nome_empresa, "en": config.enabled},
        )
    except Exception as exc:
        # asyncpg.UniqueViolationError vem como sqlalchemy IntegrityError.
        if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
            raise ValueError(f"Tenant '{config.tenant_id}' já existe.") from exc
        raise

    # 2. Config
    await session.execute(
        text(
            "INSERT INTO tenant_configs (tenant_id, config_json, schema_version) "
            "VALUES (:tid, CAST(:cj AS jsonb), :sv)"
        ),
        {
            "tid": config.tenant_id,
            "cj": config.model_dump_json(),
            "sv": config.schema_version,
        },
    )

    # 3. Audit
    await _registrar_audit(
        session,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="tenant_create",
        target_tenant_id=config.tenant_id,
        payload={"nome_empresa": config.nome_empresa, "enabled": config.enabled},
        ip=ip,
        user_agent=user_agent,
    )

    logger.info(f"[admin] Tenant criado: {config.tenant_id} por {actor_email}")


# =============================================================================
# Update
# =============================================================================
async def atualizar_tenant(
    session: AsyncSession,
    tenant_id: str,
    config: TenantConfig,
    *,
    actor_user_id: str,
    actor_email: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Atualiza config + linha de tenants. Mantém o tenant_id imutável."""
    if tenant_id == "_system":
        raise ValueError("'_system' é reservado e não pode ser editado.")
    if config.tenant_id != tenant_id:
        raise ValueError("tenant_id no path e no body divergem.")

    res = await session.execute(
        text(
            "UPDATE tenants SET nome_empresa = :nome, enabled = :en, updated_at = NOW() "
            "WHERE id = :tid"
        ),
        {"nome": config.nome_empresa, "en": config.enabled, "tid": tenant_id},
    )
    if res.rowcount == 0:
        raise ValueError(f"Tenant '{tenant_id}' não existe.")

    await session.execute(
        text(
            "UPDATE tenant_configs SET config_json = CAST(:cj AS jsonb), "
            "schema_version = :sv, updated_at = NOW() WHERE tenant_id = :tid"
        ),
        {
            "cj": config.model_dump_json(),
            "sv": config.schema_version,
            "tid": tenant_id,
        },
    )

    await _registrar_audit(
        session,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="tenant_update",
        target_tenant_id=tenant_id,
        payload={"nome_empresa": config.nome_empresa, "enabled": config.enabled},
        ip=ip,
        user_agent=user_agent,
    )

    logger.info(f"[admin] Tenant atualizado: {tenant_id} por {actor_email}")


async def setar_enabled(
    session: AsyncSession,
    tenant_id: str,
    enabled: bool,
    *,
    actor_user_id: str,
    actor_email: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Toggle de enable/disable — não rebuild do config."""
    if tenant_id == "_system":
        raise ValueError("'_system' é reservado.")

    res = await session.execute(
        text(
            "UPDATE tenants SET enabled = :en, updated_at = NOW() WHERE id = :tid"
        ),
        {"en": enabled, "tid": tenant_id},
    )
    if res.rowcount == 0:
        raise ValueError(f"Tenant '{tenant_id}' não existe.")

    # Espelha no config_json para o registry refletir.
    # Usar CAST(:en AS boolean) — `:en::boolean` tropeça no parser de bind do SQLAlchemy.
    await session.execute(
        text(
            "UPDATE tenant_configs SET "
            "config_json = jsonb_set(config_json, '{enabled}', to_jsonb(CAST(:en AS boolean))), "
            "updated_at = NOW() "
            "WHERE tenant_id = :tid"
        ),
        {"en": enabled, "tid": tenant_id},
    )

    await _registrar_audit(
        session,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action="tenant_enable" if enabled else "tenant_disable",
        target_tenant_id=tenant_id,
        payload={"enabled": enabled},
        ip=ip,
        user_agent=user_agent,
    )

    logger.info(
        f"[admin] Tenant {tenant_id} {'habilitado' if enabled else 'desabilitado'} "
        f"por {actor_email}"
    )


# =============================================================================
# Auditoria (helper interno)
# =============================================================================
async def _registrar_audit(
    session: AsyncSession,
    *,
    actor_user_id: str,
    actor_email: str,
    action: str,
    target_tenant_id: str | None,
    payload: dict[str, Any] | None,
    ip: str | None,
    user_agent: str | None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO admin_audit_log "
            "(actor_user_id, actor_email, action, target_tenant_id, payload, ip_address, user_agent) "
            "VALUES (:uid, :em, :act, :tgt, CAST(:pl AS jsonb), :ip, :ua)"
        ),
        {
            "uid": actor_user_id,
            "em": actor_email,
            "act": action,
            "tgt": target_tenant_id,
            "pl": json.dumps(payload) if payload else None,
            "ip": ip,
            "ua": user_agent,
        },
    )


async def listar_audit(
    session: AsyncSession,
    *,
    limit: int = 100,
    target_tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    """Lista entradas recentes do audit log. Mais recentes primeiro."""
    if target_tenant_id:
        sql = text(
            "SELECT * FROM admin_audit_log WHERE target_tenant_id = :tid "
            "ORDER BY created_at DESC LIMIT :lim"
        )
        params = {"tid": target_tenant_id, "lim": limit}
    else:
        sql = text("SELECT * FROM admin_audit_log ORDER BY created_at DESC LIMIT :lim")
        params = {"lim": limit}

    rows = (await session.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]
