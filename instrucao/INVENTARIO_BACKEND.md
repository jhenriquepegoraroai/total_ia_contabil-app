# Inventário Backend — Lello AI Platform

Gerado em 2026-05-18. Branch: `main` (f97cf1a).

---

## Módulos em `api/`

### Core / Infraestrutura

| Arquivo | Descrição |
|---------|-----------|
| `api/main.py` | Entry point FastAPI v0.6.0 — lifespan, middlewares, routers |
| `api/config.py` | Leitura de env vars com fail-fast (`_required` / `_optional`) |
| `api/db.py` | Engine SQLAlchemy asyncpg, `tenant_session` (com RLS), `superadmin_session` |
| `api/auth.py` | JWT login/logout, `CurrentUser`, `usuario_atual` dependency, `is_superadmin` |
| `api/cli.py` | CLI de manutenção (criar superadmin, etc.) |
| `api/middleware/trace_middleware.py` | Gera e propaga `trace_id` por request |
| `api/utils/logging.py` | Loguru — JSON em prod, human-readable em dev |
| `api/utils/masking.py` | `mascara_email`, `mascara_phone`, `mascara_json` — PII nos logs |
| `api/utils/trace.py` | Helper de contexto de trace |

### Tenants / Multi-tenancy

| Arquivo | Descrição |
|---------|-----------|
| `api/tenants/registry.py` | Registry de tenants — DB-first, seed via JSON, cache em memória |
| `api/tenants/models.py` | `TenantConfig` Pydantic — datasource, theme, RAG, prompts, módulos |
| `api/tenants/modulos.py` | Catálogo de módulos: `chat`, `cobrancas`, `atas` |
| `api/tenants/deps.py` | `require_module("slug")` — FastAPI dependency para gating de módulo |
| `api/tenants/datasources/base.py` | Interface abstrata do Adapter Pattern de datasource |
| `api/tenants/datasources/postgres_pgvector.py` | Adapter Postgres+pgvector (default) |
| `api/tenants/datasources/factory.py` | Factory que instancia o adapter certo por config |

### Módulo Chat (RAG)

| Arquivo | Descrição |
|---------|-----------|
| `api/core/rag.py` | Orquestrador RAG completo: reformulação → classificação → busca → geração |
| `api/core/classifier.py` | Classificador de categoria via GPT (`temperature=0`) |
| `api/llm/openai_client.py` | Wrapper OpenAI: `classificar`, `responder`, `reformular`, embedding |
| `api/routers/chat.py` | `POST /chat` — entry point do assistente |

### Módulo Atas (Bella Atas)

| Arquivo | Descrição |
|---------|-----------|
| `api/atas/pipeline_geracao.py` | Geração de ata em 3 passos via LLM |
| `api/atas/pipeline_comparacao.py` | Comparação entre versão gerada e devolvida (difflib) |
| `api/atas/pipeline_correcao.py` | Correção ortográfica e formatação final |
| `api/atas/stt_service.py` | STT: upload Azure Blob SAS + Whisper API |
| `api/atas/workflow.py` | Máquina de estados (15 estados, múltiplos atores) |
| `api/atas/jobs_service.py` | CRUD de atas e versões no banco |
| `api/atas/email_service.py` | Envio de e-mails por evento do workflow |
| `api/atas/email_templates.py` | Templates HTML/texto dos e-mails |
| `api/atas/prompts.py` | Prompts de geração, comparação e correção |
| `api/atas/schema.py` | Pydantic schemas do módulo atas |
| `api/routers/atas.py` | 19 endpoints REST do módulo atas |

### Módulo Cobranças (Bella Cobranças)

| Arquivo | Descrição |
|---------|-----------|
| `api/cobrancas/pipeline.py` | Orquestrador: Document AI → GPT-4o mapping → JSON estruturado |
| `api/cobrancas/documentai_client.py` | Wrapper Google Document AI (sync ≤15 pág.) |
| `api/cobrancas/documentai.py` | Utilitários de parsing do output Document AI |
| `api/cobrancas/prompts.py` | Prompts de extração para o GPT |
| `api/cobrancas/schema.py` | `CobrancaResultado` — schema tipado de extração |
| `api/cobrancas/excel_export.py` | Export XLSX formatado com resultados |
| `api/cobrancas/jobs_service.py` | Rastreamento de jobs assíncronos |
| `api/routers/cobrancas.py` | 6 endpoints REST do módulo cobranças |

### Admin Panel

| Arquivo | Descrição |
|---------|-----------|
| `api/admin/service.py` | CRUD de tenants no banco com audit log |
| `api/admin/users_service.py` | CRUD de usuários por tenant |
| `api/admin/sources_service.py` | CRUD de datasources por tenant |
| `api/admin/sources_models.py` | Schemas Pydantic para fontes de dados |
| `api/admin/chats_service.py` | Browser read-only de sessões e mensagens |
| `api/admin/ingestion_service.py` | Trigger e monitoramento de jobs de ingestão |
| `api/admin/tables_service.py` | Browser read-only de tabelas estruturadas do tenant |
| `api/routers/admin.py` | Endpoints de tenant/módulo management (superadmin) |
| `api/routers/admin_data.py` | Endpoints de sources, users, chats, tabelas (superadmin) |
| `api/routers/tenant_users.py` | Endpoints de self-service de users (admin do tenant) |

### Storage

| Arquivo | Descrição |
|---------|-----------|
| `api/storage/base.py` | Interface abstrata de storage |
| `api/storage/local.py` | Storage local (dev) |
| `api/storage/s3.py` | AWS S3 |
| `api/storage/azure_blob.py` | Azure Blob Storage + SAS URL generator |
| `api/storage/factory.py` | Factory por `STORAGE_PROVIDER` |

---

## Migrations aplicadas (`db/migrations/`)

> Não há tabela de controle de versão. Aplicação manual via `psql $DATABASE_URL -f <arquivo>`.

| Arquivo | O que cria/altera |
|---------|------------------|
| `001_init.sql` (15.9 KB) | Schema base: tenants, tenant_configs, users, condominios, condominio_areas, documents, documents_embeddings (pgvector 3072-dim), embeddings_audit, chat_sessions, chat_messages, chat_citations. RLS em todas. |
| `002_admin.sql` (3.4 KB) | `admin_audit_log` |
| `003_sources.sql` (4.6 KB) | `tenant_data_sources`, `ingestion_jobs` |
| `004_user_referencia.sql` (1.1 KB) | ALTER TABLE users ADD COLUMN referencia (condomínio default do usuário) |
| `005_modulos_contratados.sql` (1.7 KB) | Backfill JSONB `modulos_contratados` em tenant_configs |
| `006_cobrancas_jobs.sql` (2.6 KB) | `cobrancas_jobs` |
| `010_atas.sql` (11.3 KB) | `atas`, `atas_versoes`, `atas_acoes`, `atas_audios` |
| `012_atas_workflow.sql` (1.1 KB) | Ajustes no workflow de atas |

---

## Tabelas no banco (schema `public`)

| Tabela | Módulo | Descrição |
|--------|--------|-----------|
| `tenants` | Core | Registro de cada cliente/administradora |
| `tenant_configs` | Core | Config JSONB por tenant (prompts, tema, módulos, etc.) |
| `users` | Core | Usuários da plataforma (roles: admin, sindico, atendente, morador) |
| `admin_audit_log` | Admin | Log imutável de ações do superadmin |
| `tenant_data_sources` | Admin | Fontes de dados configuradas por tenant |
| `ingestion_jobs` | Admin | Jobs de ingestão de embeddings |
| `condominios` | Chat | Dados cadastrais dos condomínios |
| `condominio_areas` | Chat | Áreas comuns dos condomínios |
| `documents` | Chat | Metadados de documentos indexados |
| `documents_embeddings` | Chat | Chunks com vetores pgvector (3072-dim) |
| `embeddings_audit` | Chat | Log de execuções do pipeline de ingestão |
| `chat_sessions` | Chat | Sessões de conversa por tenant/usuário |
| `chat_messages` | Chat | Mensagens (user + assistant) por sessão |
| `chat_citations` | Chat | Citações de documentos por resposta |
| `cobrancas_jobs` | Cobranças | Jobs de extração de PDFs de cobrança |
| `atas` | Atas | Registro de atas e seu estado atual |
| `atas_versoes` | Atas | Versões HTML da ata (gerada, editada, devolvida, final) |
| `atas_acoes` | Atas | Log de ações do workflow (audit trail) |
| `atas_audios` | Atas | Uploads de áudio com status de transcrição |

**Total: 19 tabelas.** Todas com RLS habilitada e `tenant_id` em cada row.

---

## Tenants configurados

| tenant_id | Nome | Módulos contratados | Status |
|-----------|------|---------------------|--------|
| `lello` | Administradora Exemplo (placeholder) | `chat: true` | enabled |

> **Atenção:** `lello.json` tem placeholders nos dados de contato e URL.
> Ver `instrucao/INVENTARIO_PRODUTOS.md` para o mapeamento produto × módulo.

---

## Notas técnicas

- **Sem tabela de migrations:** controle é manual por nome de arquivo. Aplicar em ordem numérica.
- **Neon Postgres:** DATABASE_URL precisa de `?sslmode=require`. O `api/db.py` pode precisar converter para `connect_args={"ssl": True}` — validar no smoke test.
- **13.846 linhas de Python** em 67 arquivos.
