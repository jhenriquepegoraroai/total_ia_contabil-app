-- =============================================================================
-- Migration 002 — Superadmin + Auditoria de admin
-- =============================================================================
--   • Coluna `is_superadmin` em users (papel global, ignora tenant_id no acesso)
--   • Tabela `admin_audit_log` (registra ações de superadmin)
--   • Tenant `_system` reservado para superadmins que não pertencem a uma
--     administradora específica
--   • Senha de usuário (password_hash) usa bcrypt — preenchida via CLI
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Tenant `_system` — reservado, não vende serviço, só hospeda superadmins
-- -----------------------------------------------------------------------------
INSERT INTO tenants (id, nome_empresa, enabled)
VALUES ('_system', 'System (reservado)', false)
ON CONFLICT (id) DO NOTHING;

-- -----------------------------------------------------------------------------
-- users: flag de superadmin
-- -----------------------------------------------------------------------------
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN NOT NULL DEFAULT FALSE;

-- Constraint: só users do tenant `_system` podem ser is_superadmin.
-- Defesa em profundidade — evita que um admin de tenant comum vire superadmin
-- por mistake/bug.
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_superadmin_in_system;
ALTER TABLE users ADD CONSTRAINT users_superadmin_in_system
    CHECK (NOT is_superadmin OR tenant_id = '_system');

-- Índice para login rápido por email (já existe idx_users_tenant_email).
-- Para login de superadmin, geralmente sabe-se só o email — adicionar:
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- -----------------------------------------------------------------------------
-- admin_audit_log
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    actor_user_id   UUID NOT NULL REFERENCES users(id),
    actor_email     TEXT NOT NULL,            -- snapshot pra auditoria mesmo se user for deletado
    action          TEXT NOT NULL CHECK (action IN (
                        'tenant_create',
                        'tenant_update',
                        'tenant_enable',
                        'tenant_disable',
                        'tenant_delete',
                        'superadmin_login'
                    )),
    target_tenant_id TEXT REFERENCES tenants(id) ON DELETE SET NULL,
    payload         JSONB,                     -- diff ou contexto da ação
    ip_address      TEXT,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_actor ON admin_audit_log(actor_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_target ON admin_audit_log(target_tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON admin_audit_log(action, created_at DESC);

-- admin_audit_log NÃO tem RLS — superadmin vê tudo, ninguém mais acessa.
-- (O acesso é controlado via guard da rota /admin/audit, não via RLS.)

COMMIT;

ANALYZE;
