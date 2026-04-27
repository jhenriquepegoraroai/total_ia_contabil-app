-- =============================================================================
-- Migration 001 — Schema inicial multi-tenant
-- Assistente Virtual de Condomínios
-- =============================================================================
-- Cria:
--   • Extensão pgvector
--   • Tabelas multi-tenant (tenants, tenant_configs, condominios, areas,
--     documents, documents_embeddings, embeddings_audit, chat_sessions,
--     chat_messages, users)
--   • Row Level Security (RLS) em todas as tabelas com tenant_id
--   • Índice ivfflat para busca vetorial
--   • Função set_tenant() para uso pela aplicação
--
-- Execute como super-user (CREATE EXTENSION exige privilégio).
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Extensões
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid

-- -----------------------------------------------------------------------------
-- Função utilitária: tenant atual
-- A aplicação chama SET LOCAL app.current_tenant = '<tenant_id>' no início
-- de cada transação (middleware FastAPI). RLS lê este GUC.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION current_tenant() RETURNS TEXT AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true);
END;
$$ LANGUAGE plpgsql STABLE;

-- =============================================================================
-- TENANTS (sem RLS — leitura controlada por permission da role)
-- =============================================================================
CREATE TABLE tenants (
    id              TEXT PRIMARY KEY,                   -- ex: 'lello', 'apsa'
    nome_empresa    TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE tenant_configs (
    tenant_id       TEXT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    config_json     JSONB NOT NULL,
    schema_version  TEXT NOT NULL DEFAULT '1.0',
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- USUÁRIOS DA PLATAFORMA
-- =============================================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    nome            TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('admin','sindico','atendente','morador')),
    password_hash   TEXT,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, email)
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;

CREATE POLICY users_tenant_isolation ON users
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_users_tenant_email ON users(tenant_id, email);

-- =============================================================================
-- CONDOMÍNIOS (dados cadastrais)
-- =============================================================================
CREATE TABLE condominios (
    tenant_id                                TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    referencia                               TEXT NOT NULL,
    nome                                     TEXT,
    endereco                                 TEXT,
    cep                                      TEXT,
    cnpj                                     TEXT,
    numero_blocos                            INT,
    quantidade_apartamentos                  INT,
    telefone_portaria                        TEXT,
    nome_sindico                             TEXT,
    nome_zelador                             TEXT,
    apartamento_sindico                      TEXT,
    final_mandato_sindico                    DATE,
    vencimento_cota                          INT,
    areas_resumo                             TEXT,
    data_ultima_assembleia_ordinaria         DATE,
    data_ultima_assembleia_extraordinaria    DATE,
    data_proxima_assembleia_ordinaria        DATE,
    data_proxima_assembleia_extraordinaria   DATE,
    updated_at                               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, referencia)
);

ALTER TABLE condominios ENABLE ROW LEVEL SECURITY;
ALTER TABLE condominios FORCE ROW LEVEL SECURITY;

CREATE POLICY condominios_tenant_isolation ON condominios
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

-- =============================================================================
-- ÁREAS COMUNS DOS CONDOMÍNIOS
-- =============================================================================
CREATE TABLE condominio_areas (
    id                                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                                TEXT NOT NULL,
    referencia                               TEXT NOT NULL,
    nome                                     TEXT NOT NULL,
    taxa_utilizacao                          NUMERIC(10,2),
    restricoes                               TEXT,
    capacidade_pessoas                       INT,
    area_compartilhada                       BOOLEAN,
    bloqueia_reserva_acordistas              BOOLEAN,
    bloqueia_reserva_inadimplentes           BOOLEAN,
    horario_permitido                        TEXT,
    periodo_padrao                           TEXT,
    intervalo_entre_reservas                 TEXT,
    dias_semana_permitidos                   TEXT,
    limite_reservas                          INT,
    limite_semanal                           INT,
    quantidade_limite_reservas               INT,
    limite_dias_disponiveis                  INT,
    limite_minimo_dias_disponiveis           INT,
    disparo_email_reservas_sindico           BOOLEAN,
    disparo_email_reservas_destinatarios     TEXT,
    area_paga                                BOOLEAN,
    forma_cobranca                           TEXT,
    dias_prazo_cancelamento                  INT,
    dias_para_vencimento                     INT,
    numero_conta_cobranca                    TEXT,
    nome_conta_cobranca                      TEXT,
    datas_bloqueadas                         TEXT,
    datas_sorteio                            TEXT,
    updated_at                               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (tenant_id, referencia) REFERENCES condominios(tenant_id, referencia) ON DELETE CASCADE
);

ALTER TABLE condominio_areas ENABLE ROW LEVEL SECURITY;
ALTER TABLE condominio_areas FORCE ROW LEVEL SECURITY;

CREATE POLICY areas_tenant_isolation ON condominio_areas
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_areas_tenant_ref ON condominio_areas(tenant_id, referencia);

-- =============================================================================
-- DOCUMENTOS (metadados — sem o conteúdo)
-- =============================================================================
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    referencia      TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    data_valida     DATE,
    storage_url     TEXT,                     -- s3://... ou path local
    mime_type       TEXT,
    qtde_paragrafos INT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, referencia, file_name)
);

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;

CREATE POLICY documents_tenant_isolation ON documents
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_documents_tenant_ref ON documents(tenant_id, referencia);
CREATE INDEX idx_documents_tenant_filename ON documents(tenant_id, file_name);

-- =============================================================================
-- EMBEDDINGS DE PARÁGRAFOS
-- Equivalente da tabela Delta `lello_documents_base_final_embeddings` da Lello
-- =============================================================================
CREATE TABLE documents_embeddings (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    referencia      TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    record_id       TEXT NOT NULL,            -- id do parágrafo na origem (ex: recordId do Spark)
    paragraph       TEXT NOT NULL,
    data_valida     DATE,
    embedding       vector(3072) NOT NULL,    -- text-embedding-3-large = 3072 dimensões
    content_hash    TEXT NOT NULL,            -- sha256 para idempotência
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, referencia, file_name, record_id)
);

ALTER TABLE documents_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents_embeddings FORCE ROW LEVEL SECURITY;

CREATE POLICY embeddings_tenant_isolation ON documents_embeddings
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_embeddings_tenant_ref ON documents_embeddings(tenant_id, referencia);
CREATE INDEX idx_embeddings_tenant_filename ON documents_embeddings(tenant_id, file_name);
CREATE INDEX idx_embeddings_data_valida ON documents_embeddings(tenant_id, referencia, data_valida DESC);

-- Índice vetorial — ivfflat com cosine.
-- 'lists' deve ser ~ sqrt(qtde_linhas) — começamos com 100 e ajustamos quando crescer.
-- Para volumes muito grandes (>10M linhas) considerar HNSW (pgvector >= 0.5.0).
CREATE INDEX idx_embeddings_vector ON documents_embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- =============================================================================
-- AUDITORIA DE INGESTÃO DE EMBEDDINGS
-- Equivalente da `controle_quantidade_tabelas_projeto_bella` da Lello
-- =============================================================================
CREATE TABLE embeddings_audit (
    contador            BIGSERIAL PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    referencia          TEXT,                 -- NULL = full reindex (todas as refs do tenant)
    connector           TEXT NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ,
    qtde_chunks_origem  INT NOT NULL DEFAULT 0,
    qtde_processada     INT NOT NULL DEFAULT 0,
    qtde_skipped        INT NOT NULL DEFAULT 0,
    qtde_erros          INT NOT NULL DEFAULT 0,
    duracao_segundos    NUMERIC(10,2),
    erro_detalhe        TEXT
);

CREATE INDEX idx_audit_tenant_ref ON embeddings_audit(tenant_id, referencia);
CREATE INDEX idx_audit_finished_at ON embeddings_audit(finished_at DESC);

-- =============================================================================
-- CHAT (sessões e mensagens)
-- =============================================================================
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    referencia      TEXT,                     -- condomínio em foco (opcional)
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);

ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions FORCE ROW LEVEL SECURITY;

CREATE POLICY sessions_tenant_isolation ON chat_sessions
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content         TEXT NOT NULL,
    categoria       INT,                      -- preenchido para mensagens 'assistant'
    trace_id        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY;

CREATE POLICY messages_tenant_isolation ON chat_messages
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_messages_session ON chat_messages(session_id, created_at);

-- =============================================================================
-- CITAÇÕES (qual chunk gerou qual resposta)
-- =============================================================================
CREATE TABLE chat_citations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    message_id      UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    embedding_id    BIGINT NOT NULL REFERENCES documents_embeddings(id) ON DELETE CASCADE,
    similarity      NUMERIC(6,4),
    rank_position   INT NOT NULL
);

ALTER TABLE chat_citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_citations FORCE ROW LEVEL SECURITY;

CREATE POLICY citations_tenant_isolation ON chat_citations
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

-- =============================================================================
-- ROLES / GRANTS
-- =============================================================================
-- A aplicação se conecta com a role 'avc_app' (não super-user)
-- O super-user 'avc' (ou postgres) é usado apenas para migrations e ops.
-- Em ambiente local docker-compose ainda estamos com avc=super; em prod, dividir.
--
-- Quando dividir (depois):
--   CREATE ROLE avc_app WITH LOGIN PASSWORD '<secret>';
--   GRANT CONNECT ON DATABASE assistente_condominios TO avc_app;
--   GRANT USAGE ON SCHEMA public TO avc_app;
--   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO avc_app;
--   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO avc_app;

COMMIT;

-- =============================================================================
-- Pós-migração: estatísticas
-- =============================================================================
ANALYZE;
