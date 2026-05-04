-- =============================================================================
-- Migration 012 — Workflow multi-ator de atas (snapshots de versão base)
-- =============================================================================
-- Quando o consultor envia uma ata pro síndico ou presidente, o sistema
-- precisa "fotografar" qual era a versão atual naquele momento — pra
-- depois comparar com a versão devolvida pelo ator externo.
--
-- Adicionamos 2 colunas em `atas`:
--   versao_base_sindico_id    — ID da atas_versoes que o síndico recebeu
--   versao_base_presidente_id — ID da atas_versoes que o presidente recebeu
--
-- Não são FKs declaradas (igual `versao_atual_id`) — evita ciclo na criação;
-- aplicação garante consistência. Setadas no momento do envio e mantidas
-- mesmo após aprovação (auditoria histórica).
-- =============================================================================

BEGIN;

ALTER TABLE atas
    ADD COLUMN versao_base_sindico_id    UUID,
    ADD COLUMN versao_base_presidente_id UUID;

COMMIT;
