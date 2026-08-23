-- =============================================================================
-- Migration 015 — Zona de dados tabular por tenant (trilho de ML)
-- =============================================================================
-- Até aqui a plataforma tinha um caminho de dados só: todo connector produz
-- `RawChunk` (texto) e tudo pousa em `documents_embeddings` como vetor. Isso
-- serve capacidade de linguagem (Chat, Atas, Cobranças) e não serve modelo de
-- ML: churn, fraude, inadimplência e ISC precisam de feature numérica —
-- atraso médio, histórico de pagamento, tempo de contrato — e guardar número
-- como vetor de texto de 3072 dimensões é a forma mais lossy possível.
--
-- Esta migration abre o segundo caminho. São quatro tabelas:
--
--   feature_sets      → o CONTRATO. Declara, por tenant, quais colunas ele
--                       entrega, de que tipo e quais são obrigatórias. É o
--                       contrato que torna o modelo aplicável a um parceiro
--                       que não é a Lello.
--   feature_values    → os DADOS entregues, série temporal por entidade.
--   capability_scores → a SAÍDA do modelo. O worker de batch escreve, a API
--                       só lê — inferência sob demanda não é o desenho.
--   scoring_runs      → auditoria de cada execução do batch, no mesmo espírito
--                       de `ingestion_jobs` e `embeddings_audit`.
--
-- Isolamento: as quatro levam `tenant_id`, RLS e FORCE, igual ao resto. A
-- zona de features é o lugar onde um vazamento cross-tenant seria mais caro,
-- porque aqui o dado é financeiro e nominal, não documento público do
-- condomínio.
--
-- O que esta migration deliberadamente NÃO faz: fixar a lista de features de
-- cada modelo. Essa lista pertence ao dono do modelo dentro da Lello e entra
-- como linha em `feature_sets`, não como coluna em DDL — trocar de feature
-- não pode exigir migration.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- CONTRATO DE FEATURES
-- -----------------------------------------------------------------------------
CREATE TABLE feature_sets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Nome estável do conjunto, ex: 'churn_unidade', 'isc_condominio'.
    nome            TEXT NOT NULL,

    -- Granularidade da linha. 'condominio' → uma linha por referência;
    -- 'unidade' → uma linha por unidade dentro da referência.
    entidade        TEXT NOT NULL
                    CHECK (entidade IN ('condominio', 'unidade')),

    -- Versão do contrato. Mudou coluna obrigatória? Nova versão, para que
    -- dado antigo continue interpretável pelo modelo que o consumiu.
    versao          INT NOT NULL DEFAULT 1,

    -- Declaração das colunas:
    --   {"atraso_medio_dias": {"tipo": "number", "obrigatorio": true,
    --                          "descricao": "média de dias de atraso em 12m"}}
    -- O validador da ingestão compara `feature_values.valores` contra isto.
    schema_json     JSONB NOT NULL,

    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, nome, versao)
);

ALTER TABLE feature_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_sets FORCE ROW LEVEL SECURITY;

CREATE POLICY feature_sets_tenant_isolation ON feature_sets
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_feature_sets_tenant ON feature_sets(tenant_id, nome);

-- -----------------------------------------------------------------------------
-- DADOS DE FEATURE
-- -----------------------------------------------------------------------------
CREATE TABLE feature_values (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    feature_set_id  UUID NOT NULL REFERENCES feature_sets(id) ON DELETE CASCADE,

    -- Condomínio (mesma chave usada em documents_embeddings e condominios).
    referencia      TEXT NOT NULL,

    -- Identificador da entidade dentro da referência. Quando o feature_set é
    -- de granularidade 'condominio', repete a `referencia`.
    entidade_id     TEXT NOT NULL,

    -- Competência. Feature é série temporal: o mesmo condomínio tem valores
    -- diferentes a cada mês, e o modelo precisa saber de quando é a linha.
    data_referencia DATE NOT NULL,

    valores         JSONB NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Reingestão da mesma competência substitui, não duplica.
    UNIQUE (tenant_id, feature_set_id, referencia, entidade_id, data_referencia)
);

ALTER TABLE feature_values ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_values FORCE ROW LEVEL SECURITY;

CREATE POLICY feature_values_tenant_isolation ON feature_values
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

-- Leitura do batch: varre um feature_set inteiro numa competência.
CREATE INDEX idx_feature_values_set_data
    ON feature_values(tenant_id, feature_set_id, data_referencia DESC);

-- Leitura pontual: histórico de uma entidade.
CREATE INDEX idx_feature_values_entidade
    ON feature_values(tenant_id, referencia, entidade_id, data_referencia DESC);

-- -----------------------------------------------------------------------------
-- SAÍDA DOS MODELOS
-- -----------------------------------------------------------------------------
CREATE TABLE capability_scores (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- Slug da capacidade: 'churn', 'fraude', 'inadimplencia', 'isc'.
    -- Não é FK para o catálogo de módulos porque o catálogo vive em código
    -- (api/tenants/modulos.py), não no banco.
    capability      TEXT NOT NULL,

    referencia      TEXT NOT NULL,
    entidade_id     TEXT NOT NULL,
    data_referencia DATE NOT NULL,

    -- A escala pertence à capacidade (churn 0..1, ISC 0..100). Não há CHECK
    -- de faixa aqui de propósito: constraint errada é pior que constraint
    -- nenhuma. `faixa` carrega a leitura humana.
    score           NUMERIC NOT NULL,
    faixa           TEXT CHECK (faixa IN ('baixo', 'medio', 'alto')),

    -- Rastreabilidade obrigatória: score sem versão de modelo é número solto.
    modelo_versao   TEXT NOT NULL,

    -- Calibração por tenant. O modelo é global e calibrado por carteira —
    -- sem isto não dá para explicar por que o mesmo modelo dá números
    -- diferentes em dois parceiros.
    calibracao_versao TEXT,

    -- Contribuição das features para o score, quando o modelo expõe.
    explicacao      JSONB,

    scoring_run_id  UUID,
    calculado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tenant_id, capability, referencia, entidade_id,
            data_referencia, modelo_versao)
);

ALTER TABLE capability_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE capability_scores FORCE ROW LEVEL SECURITY;

CREATE POLICY capability_scores_tenant_isolation ON capability_scores
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

-- Leitura da API: score mais recente de uma capacidade, por carteira.
CREATE INDEX idx_scores_capability_data
    ON capability_scores(tenant_id, capability, data_referencia DESC);

-- Leitura pontual: histórico de uma entidade numa capacidade.
CREATE INDEX idx_scores_entidade
    ON capability_scores(tenant_id, capability, referencia, entidade_id,
                         data_referencia DESC);

-- -----------------------------------------------------------------------------
-- AUDITORIA DO BATCH
-- -----------------------------------------------------------------------------
CREATE TABLE scoring_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    capability      TEXT NOT NULL,

    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued', 'running', 'done', 'failed')),

    feature_set_id  UUID REFERENCES feature_sets(id) ON DELETE SET NULL,
    data_referencia DATE,
    modelo_versao   TEXT,
    calibracao_versao TEXT,

    linhas_lidas    INT NOT NULL DEFAULT 0,
    scores_gravados INT NOT NULL DEFAULT 0,
    erro            TEXT,

    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE scoring_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE scoring_runs FORCE ROW LEVEL SECURITY;

CREATE POLICY scoring_runs_tenant_isolation ON scoring_runs
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_scoring_runs_tenant
    ON scoring_runs(tenant_id, capability, created_at DESC);

-- FK adicionada aqui porque `capability_scores` é criada antes de
-- `scoring_runs`; a ordem inversa deixaria a leitura pior (o contrato vem
-- antes do dado, o dado antes do resultado, o resultado antes da auditoria).
ALTER TABLE capability_scores
    ADD CONSTRAINT capability_scores_scoring_run_fk
    FOREIGN KEY (scoring_run_id) REFERENCES scoring_runs(id) ON DELETE SET NULL;

-- Registro no controle de migrations (convenção criada na 014).
INSERT INTO schema_migrations (filename) VALUES ('015_zona_features.sql')
ON CONFLICT (filename) DO NOTHING;

COMMIT;
