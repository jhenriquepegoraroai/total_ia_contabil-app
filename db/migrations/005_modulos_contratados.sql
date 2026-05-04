-- =============================================================================
-- Migration 005 — Módulos contratados por tenant
-- =============================================================================
-- Contexto:
--   O SaaS Bella é vendido por módulos (Bella Chat, Bella Cobranças, Bella
--   Atas, ...). Cada tenant contrata um subconjunto. O super admin marca
--   quais via UI.
--
-- Onde mora a contratação:
--   Dentro do JSONB `tenant_configs.config_json`, chave `modulos_contratados`
--   (mapa slug → bool). Validado pelo Pydantic `TenantConfig`.
--
-- Esta migration apenas faz BACKFILL idempotente nos tenants já existentes:
--   - Tenants reais que ainda não têm a chave ganham `{"chat": true}`
--     (preservam o comportamento "all-in" anterior, onde todos tinham chat).
--   - Tenant `_system` (super admin) ganha `{}` — ele opera fora dos módulos.
--
-- Sem ALTER TABLE: a coluna `config_json JSONB` já aceita o campo novo.
-- =============================================================================

BEGIN;

-- Tenants reais sem o campo → recebem chat=true
UPDATE tenant_configs
SET config_json = jsonb_set(
        config_json,
        '{modulos_contratados}',
        '{"chat": true}'::jsonb,
        true  -- create if missing
    ),
    updated_at = NOW()
WHERE tenant_id <> '_system'
  AND NOT (config_json ? 'modulos_contratados');

-- Tenant _system sem o campo → recebe {}
UPDATE tenant_configs
SET config_json = jsonb_set(
        config_json,
        '{modulos_contratados}',
        '{}'::jsonb,
        true
    ),
    updated_at = NOW()
WHERE tenant_id = '_system'
  AND NOT (config_json ? 'modulos_contratados');

COMMIT;
