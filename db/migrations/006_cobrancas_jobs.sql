-- =============================================================================
-- Migration 006 — Jobs de extração do Bella Cobranças
-- =============================================================================
-- Substitui o `jobs_status: dict[str, Dict]` em memória do Decob original.
-- Cada job é uma corrida do pipeline Document AI + GPT-4o sobre um PDF.
--
-- Estados:
--   queued    → recebido, aguardando processamento
--   running   → pipeline em execução
--   done      → JSON estruturado disponível em result_url
--   failed    → erro registrado em error_detail
--
-- RLS: tenant_id sempre filtrado — admin de petropolis nunca vê job de lello.
-- =============================================================================

BEGIN;

CREATE TABLE cobrancas_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued','running','done','failed')),

    -- Arquivo de entrada
    file_name       TEXT NOT NULL,
    file_size       BIGINT NOT NULL,
    file_storage_key TEXT NOT NULL,        -- chave no storage (api/storage)
    content_hash    TEXT NOT NULL,         -- sha256 do PDF (idempotência)

    -- Resultado
    result_storage_key TEXT,               -- chave do JSON no storage
    qtde_paginas    INT,
    qtde_registros  INT,
    valor_total     NUMERIC(14,2),

    -- Auditoria
    actor_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    duracao_segundos NUMERIC(10,2),
    error_detail    TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Idempotência: mesmo PDF subido 2x devolve o mesmo job (latest done).
    -- Não é UNIQUE pra permitir reprocessar deliberadamente; o service
    -- checa antes de criar e devolve o existente.
    UNIQUE (tenant_id, content_hash, status) DEFERRABLE INITIALLY DEFERRED
);

ALTER TABLE cobrancas_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE cobrancas_jobs FORCE ROW LEVEL SECURITY;

CREATE POLICY cobrancas_jobs_tenant_isolation ON cobrancas_jobs
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_cobrancas_jobs_tenant_status
    ON cobrancas_jobs(tenant_id, status, created_at DESC);

CREATE INDEX idx_cobrancas_jobs_tenant_hash
    ON cobrancas_jobs(tenant_id, content_hash);

COMMIT;
