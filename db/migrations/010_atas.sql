-- =============================================================================
-- Migration 010 — Bella Atas: ata mestre, versões imutáveis, ações, áudios
-- =============================================================================
-- Modelo do módulo `atas` (geração/comparação/correção de atas de assembleia).
--
-- Tabelas:
--   atas              — entidade mestre, uma linha por ata em andamento
--   atas_versoes      — IMUTÁVEL: cada operação que muda o conteúdo cria linha
--                       nova; nunca UPDATE em conteudo_html.
--   atas_acoes        — log de auditoria de quem fez o quê e quando
--   atas_audios       — uploads de áudio + estado da transcrição (Whisper)
--
-- RLS: todas as tabelas têm `tenant_id = current_tenant()` policy. Defesa em
-- profundidade: as queries da aplicação SEMPRE incluem `tenant_id` no WHERE.
--
-- O numbering pula 006-009 deliberadamente — esses números estão reservados
-- pro módulo cobrancas, que vive num branch paralelo. Quando os branches
-- mergearem, fica em ordem.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- atas — entidade mestre (estado da máquina)
-- -----------------------------------------------------------------------------
CREATE TABLE atas (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id             TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    titulo                TEXT NOT NULL,
    referencia            TEXT,                                 -- condomínio (igual ao users.referencia)

    status                TEXT NOT NULL DEFAULT 'rascunho'
                          CHECK (status IN (
                              'rascunho',                       -- criada, sem áudio nem texto
                              'aguardando_transcricao',         -- áudio em fila/processando STT
                              'aguardando_geracao',             -- texto pronto, na fila do gerador
                              'gerada',                         -- gerador devolveu, aguardando consultor
                              'revisao_consultor',              -- consultor está editando
                              'aguardando_sindico',             -- enviada ao síndico
                              'revisao_sindico',                -- síndico está editando
                              'comparando',                     -- comparador rodando
                              'revisao_consultor_diff',         -- consultor avaliando o diff
                              'aguardando_presidente',          -- enviada ao presidente
                              'revisao_presidente',             -- presidente está editando
                              'revisao_consultor_final',        -- consultor avaliando edição do presidente
                              'corrigindo',                     -- corretor ortográfico rodando
                              'registrada',                     -- versão final salva, ata fechada
                              'arquivada',                      -- arquivada por algum motivo
                              'falhou'                          -- pipeline falhou; consultor decide
                          )),

    versao_atual_id       UUID,                                 -- FK soft (preenchida após 1ª versão)
    consultor_user_id     UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    sindico_user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    presidente_user_id    UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Insumos da geração que vieram do consultor (cabeçalho HTML, edital, etc.).
    -- Persistimos pra reprocessar caso o consultor queira regenerar.
    insumos_json          JSONB NOT NULL DEFAULT '{}'::jsonb,

    erro_detalhe          TEXT,                                 -- motivo do status='falhou'
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE atas ENABLE ROW LEVEL SECURITY;
ALTER TABLE atas FORCE ROW LEVEL SECURITY;

CREATE POLICY atas_tenant_isolation ON atas
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_atas_tenant_status ON atas(tenant_id, status, created_at DESC);
CREATE INDEX idx_atas_tenant_consultor ON atas(tenant_id, consultor_user_id);
CREATE INDEX idx_atas_tenant_sindico ON atas(tenant_id, sindico_user_id) WHERE sindico_user_id IS NOT NULL;
CREATE INDEX idx_atas_tenant_presidente ON atas(tenant_id, presidente_user_id) WHERE presidente_user_id IS NOT NULL;


-- -----------------------------------------------------------------------------
-- atas_versoes — imutável; uma linha por ponto de mudança no conteúdo
-- -----------------------------------------------------------------------------
CREATE TABLE atas_versoes (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ata_id            UUID NOT NULL REFERENCES atas(id) ON DELETE CASCADE,
    tenant_id         TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    tipo              TEXT NOT NULL
                      CHECK (tipo IN (
                          'gerada',                -- saída do gerador (LLM)
                          'edicao_consultor',      -- consultor editou e salvou
                          'edicao_sindico',        -- síndico editou e devolveu
                          'edicao_presidente',     -- presidente editou e devolveu
                          'comparacao',            -- HTML diff produzido pelo comparador
                          'correcao_ortografica',  -- saída do corretor (LLM/regex)
                          'final'                  -- versão registrada
                      )),

    -- HTML estruturado conforme template do gerador (cabeçalho, deliberações,
    -- assinaturas, etc.). NUNCA fazemos UPDATE nesta coluna — é imutável.
    conteudo_html     TEXT NOT NULL,

    -- Metadados específicos da operação que produziu esta versão (modelo
    -- LLM, tokens, prompt usado, base de comparação, etc.).
    metadata_json     JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Quem produziu (NULL se foi sistema/pipeline).
    criada_por_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    criada_em         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE atas_versoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE atas_versoes FORCE ROW LEVEL SECURITY;

CREATE POLICY atas_versoes_tenant_isolation ON atas_versoes
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_atas_versoes_ata_criada ON atas_versoes(ata_id, criada_em DESC);

-- FK soft pra atas.versao_atual_id (não declarada como FK pra evitar ciclo
-- de criação; a aplicação garante consistência).


-- -----------------------------------------------------------------------------
-- atas_acoes — log de auditoria
-- -----------------------------------------------------------------------------
CREATE TABLE atas_acoes (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ata_id            UUID NOT NULL REFERENCES atas(id) ON DELETE CASCADE,
    tenant_id         TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- NULL = ação foi tomada pelo sistema (ex: pipeline finalizou)
    ator_user_id      UUID REFERENCES users(id) ON DELETE SET NULL,

    acao              TEXT NOT NULL
                      CHECK (acao IN (
                          'criada',
                          'audio_uploaded',
                          'transcricao_iniciada',
                          'transcricao_concluida',
                          'transcricao_falhou',
                          'geracao_iniciada',
                          'geracao_concluida',
                          'geracao_falhou',
                          'editada_consultor',
                          'enviada_sindico',
                          'editada_sindico',
                          'retornada_sindico',
                          'comparacao_iniciada',
                          'comparacao_concluida',
                          'aprovacao_consultor_diff',
                          'enviada_presidente',
                          'editada_presidente',
                          'retornada_presidente',
                          'correcao_iniciada',
                          'correcao_concluida',
                          'correcao_falhou',
                          'registrada',
                          'arquivada'
                      )),

    -- Detalhe livre da ação (ex: versao_id, motivo, diff, ator externo).
    detalhe_json      JSONB NOT NULL DEFAULT '{}'::jsonb,

    timestamp         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE atas_acoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE atas_acoes FORCE ROW LEVEL SECURITY;

CREATE POLICY atas_acoes_tenant_isolation ON atas_acoes
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_atas_acoes_ata_ts ON atas_acoes(ata_id, timestamp DESC);


-- -----------------------------------------------------------------------------
-- atas_audios — uploads de áudio + estado da transcrição (Whisper)
-- -----------------------------------------------------------------------------
CREATE TABLE atas_audios (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ata_id                   UUID NOT NULL REFERENCES atas(id) ON DELETE CASCADE,
    tenant_id                TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    file_storage_key         TEXT NOT NULL,        -- chave no storage (api/storage)
    file_name                TEXT NOT NULL,
    file_size_bytes          BIGINT NOT NULL,
    duracao_segundos         NUMERIC(10,2),

    status                   TEXT NOT NULL DEFAULT 'uploaded'
                             CHECK (status IN ('uploaded','transcribing','done','failed')),

    transcricao_text         TEXT,                 -- texto integral pós-Whisper
    transcricao_storage_key  TEXT,                 -- chave do .txt completo no storage (caso passar limite)
    qtde_chunks              INT,                  -- chunking do áudio pra Whisper (~10min cada)
    custo_estimado_usd       NUMERIC(10,4),        -- por audit/billing futuro

    error_detail             TEXT,
    uploaded_by_user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transcribed_at           TIMESTAMPTZ
);

ALTER TABLE atas_audios ENABLE ROW LEVEL SECURITY;
ALTER TABLE atas_audios FORCE ROW LEVEL SECURITY;

CREATE POLICY atas_audios_tenant_isolation ON atas_audios
    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

CREATE INDEX idx_atas_audios_ata ON atas_audios(ata_id, uploaded_at DESC);
CREATE INDEX idx_atas_audios_tenant_status ON atas_audios(tenant_id, status);

COMMIT;
