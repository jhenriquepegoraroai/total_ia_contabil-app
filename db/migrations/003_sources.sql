-- =============================================================================
-- Migration 003 — Fontes de dados por tenant + jobs de ingestão
-- =============================================================================
--   • tenant_data_sources — cada tenant pode ter N fontes configuradas
--     (PDF upload local, S3 do cliente, Postgres do cliente, etc.)
--   • ingestion_jobs — rastreia execuções do pipeline disparadas pela UI
--
-- Nota: já existe `embeddings_audit` (migration 001), que registra cada
-- batch persistido. `ingestion_jobs` é a visão de mais alto nível: 1 job
-- = 1 ação iniciada pela UI, pode gerar múltiplos batches em audit.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- tenant_data_sources
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenant_data_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN (
                        'pdf_upload',
                        'excel_upload',
                        'csv_upload',
                        's3',
                        'azure_blob',
                        'postgres',
                        'sqlserver',
                        'databricks'
                    )),
    -- Config específica do tipo (campos por tipo definidos no código).
    -- Para tipos sensíveis (s3, postgres, etc), o config_json contém
    -- só metadata; credenciais ficam em `secret_name` no Secrets Manager.
    config_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    secret_name     TEXT,
    -- Estado da fonte
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    -- Estatísticas (atualizadas após cada job)
    last_run_at     TIMESTAMPTZ,
    last_run_status TEXT CHECK (last_run_status IN ('queued','running','done','failed') OR last_run_status IS NULL),
    qtde_files      INT NOT NULL DEFAULT 0,
    -- Auditoria
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, name)
);

ALTER TABLE tenant_data_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_data_sources FORCE ROW LEVEL SECURITY;

CREATE POLICY sources_tenant_isolation ON tenant_data_sources
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX IF NOT EXISTS idx_sources_tenant ON tenant_data_sources(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sources_tenant_type ON tenant_data_sources(tenant_id, type);

-- -----------------------------------------------------------------------------
-- ingestion_jobs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_id       UUID REFERENCES tenant_data_sources(id) ON DELETE SET NULL,
    referencia      TEXT,                          -- condomínio (opcional)
    status          TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
                        'queued', 'running', 'done', 'failed', 'cancelled'
                    )),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    qtde_chunks_origem INT NOT NULL DEFAULT 0,
    qtde_processada    INT NOT NULL DEFAULT 0,
    qtde_skipped       INT NOT NULL DEFAULT 0,
    qtde_erros         INT NOT NULL DEFAULT 0,
    duracao_segundos   NUMERIC(10,2),
    erro_detalhe       TEXT,
    -- Quem disparou (snapshot — sobrevive ao delete do user).
    actor_user_id   UUID,
    actor_email     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE ingestion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_jobs FORCE ROW LEVEL SECURITY;

CREATE POLICY jobs_tenant_isolation ON ingestion_jobs
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON ingestion_jobs(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON ingestion_jobs(source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON ingestion_jobs(status, created_at DESC);

COMMIT;

ANALYZE;
