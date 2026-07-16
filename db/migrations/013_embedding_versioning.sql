-- =============================================================================
-- Migration 013 — Versionamento de embedding em documents_embeddings
-- =============================================================================
-- O corpus real será ingerido em breve. Hoje o modelo de embedding é implícito
-- (só um comentário no schema) e a dimensão é fixa no tipo da coluna
-- (`vector(3072)`). Sem versionamento em linha, uma futura troca de modelo
-- (ou uso de `dimensions=1536` do text-embedding-3-large) seria silenciosa e
-- não-auditável — misturando vetores incompatíveis na mesma coluna.
--
-- Adicionamos 2 colunas em `documents_embeddings`:
--   embedding_model — nome do modelo OpenAI que gerou o vetor
--   embedding_dim   — dimensão do vetor (redundante com o tipo, mas explícita
--                     por linha para permitir convivência futura de modelos)
--
-- Backfill dos registros existentes com os valores atuais de fato
-- (text-embedding-3-large / 3072). Depois do backfill, aplicamos DEFAULT +
-- NOT NULL para que toda linha nova carregue o metadado.
--
-- NOTA (limitação conhecida, fora do escopo desta migration): o `content_hash`
-- de idempotência NÃO inclui o modelo. Trocar de modelo não invalida linhas
-- existentes (texto idêntico segue SKIPado no pipeline). Reindex por troca de
-- modelo é decisão da fase de migração de LLM (pós-pitch).
-- =============================================================================

BEGIN;

ALTER TABLE documents_embeddings
    ADD COLUMN embedding_model TEXT,
    ADD COLUMN embedding_dim   INT;

-- Backfill: os registros existentes foram gerados com o modelo default atual.
UPDATE documents_embeddings
   SET embedding_model = 'text-embedding-3-large',
       embedding_dim   = 3072
 WHERE embedding_model IS NULL;

-- A partir daqui, toda linha nova precisa do metadado. O default cobre o caminho
-- atual; o pipeline de ingestão passa a gravar o valor real explicitamente.
ALTER TABLE documents_embeddings
    ALTER COLUMN embedding_model SET DEFAULT 'text-embedding-3-large',
    ALTER COLUMN embedding_dim   SET DEFAULT 3072,
    ALTER COLUMN embedding_model SET NOT NULL,
    ALTER COLUMN embedding_dim   SET NOT NULL;

COMMIT;
