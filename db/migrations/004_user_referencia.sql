-- =============================================================================
-- Migration 004: usuário tem condomínio default (referencia)
-- =============================================================================
-- Antes: cada pergunta no chat exigia o usuário digitar `referencia`
-- (id do condomínio). Era fricção desnecessária — o cadastro do
-- usuário deveria já registrar a qual condomínio ele pertence.
--
-- Agora:
--   - users.referencia é a referência default que aparece pré-preenchida
--     no chat (ou única, no caso de morador).
--   - NULL = usuário multi-cond (admin/atendente que escolhe na hora).
--   - Para usuários existentes (criados antes da migration), NULL — o
--     superadmin pode editar via UI depois.
-- =============================================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS referencia TEXT;

-- Index pra eventuais queries "todos os usuários do cond X".
CREATE INDEX IF NOT EXISTS idx_users_tenant_referencia
    ON users(tenant_id, referencia)
    WHERE referencia IS NOT NULL;
