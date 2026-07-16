-- =============================================================================
-- Migration 014 — Tabela de controle de migrations
-- =============================================================================
-- Até aqui o controle de migrations era manual, só por convenção de nome de
-- arquivo (ver instrucao/INVENTARIO_BACKEND.md). Isso é frágil: não há registro
-- de o que já foi aplicado num banco. Criamos uma tabela simples de controle.
--
-- `schema_migrations` é infraestrutura global (não tem `tenant_id`), então não
-- leva RLS. Cada aplicação futura de migration deve registrar o próprio filename
-- aqui (INSERT ... ON CONFLICT DO NOTHING no fim do arquivo da migration).
--
-- Semeamos as migrations já aplicadas até esta (007-009 e 011 nunca existiram —
-- foram reservadas e não usadas).
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Registro retroativo das migrations já aplicadas neste ponto da história.
INSERT INTO schema_migrations (filename) VALUES
    ('001_init.sql'),
    ('002_admin.sql'),
    ('003_sources.sql'),
    ('004_user_referencia.sql'),
    ('005_modulos_contratados.sql'),
    ('006_cobrancas_jobs.sql'),
    ('010_atas.sql'),
    ('012_atas_workflow.sql'),
    ('013_embedding_versioning.sql'),
    ('014_schema_migrations.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
