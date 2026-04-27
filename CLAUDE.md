# CLAUDE.md — Instruções para o Claude neste repositório

## Antes de qualquer mudança
1. Leia `RULES.md` — regras críticas que nunca podem ser violadas (isolamento multi-tenant, secrets, integridade de resposta).
2. Confirme em qual fase do projeto está pelo `README.md`.
3. Para qualquer mudança em `core/`, `tenants/datasources/` ou pipeline de ingestão, há regra obrigatória de teste de isolamento cross-tenant — adicione/atualize antes de marcar a task como concluída.

## Princípios de operação
- **Cautela com PROD.** O operador principal é cauteloso com produção (histórico no Total IA Contábil — ver memória do projeto). Nunca deployar, rodar migration em prod, ou tocar Secrets Manager sem aprovação explícita.
- **Mostrar comandos antes de executar.** Quando propuser comandos de ambiente (docker, alembic, psql em PROD), mostre o comando e aguarde aprovação. Em dev local, pode executar.
- **Plano antes de código** para mudanças não-triviais. Para fix pontual, ir direto.
- **Português** em docstrings, comentários, mensagens de log, mensagens de UI. Identifiers em inglês quando convencionais (ex: `tenant_id`, `embedding`, `ThreadPoolExecutor`).

## Padrões obrigatórios

### Multi-tenant
- Toda função que toca dados recebe `tenant_config: TenantConfig` ou `tenant_id: str` como parâmetro explícito. **Nunca** lê de variável global ou contexto implícito.
- Toda query SQL inclui `tenant_id` no WHERE — mesmo quando RLS está ativo. Defesa em profundidade.
- Cache em memória usa chave `f"{tenant_id}:{...}"`.

### Secrets
- `os.getenv("KEY")` sem fallback de string. Se faltar variável, derruba boot com mensagem clara.
- Nunca commitar `.env`. `.env.example` é o template público.

### Logging
- `from loguru import logger` — não usar `print` nem `logging` nativo no código de aplicação.
- Mascarar PII: `mascara_email("joao@gmail.com")` → `"joa***@gmail.com"`. Helpers em `api/utils/masking.py`.
- Trace ID propagado em todas as mensagens via `logger.contextualize(trace_id=...)`.

### Erros
- `except Exception: pass` é proibido.
- Erros conhecidos (sessão Postgres caída, OpenAI 429) têm tratamento específico com retry; demais propagam ou logam com `exc_info=True`.

## Stack do repositório

- **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 + asyncpg, pgvector, OpenAI SDK, tiktoken, loguru
- **Pipeline:** Python standalone (CLI), ThreadPoolExecutor
- **Frontend:** Next.js 15, React 19, Tailwind 3.4, shadcn/ui, lucide-react, next-themes
- **Infra local:** docker-compose (Postgres 16+pgvector, Redis 7)
- **Infra prod (planejada):** AWS ECS/Fargate, RDS Postgres, S3, Secrets Manager

## Comandos úteis (dev local)

```bash
# Subir infra (Postgres com pgvector + Redis)
docker-compose up -d postgres redis

# Aplicar migrations
psql "$DATABASE_URL" -f db/migrations/001_init.sql

# Rodar API com reload
cd api && uvicorn main:app --reload --port 8000

# Rodar Web
cd web && npm run dev

# Rodar pipeline de ingestão
cd ingestion && python run.py --tenant lello --referencia 12345 --connector pdf_folder --path ./samples/lello/12345

# Teste de isolamento cross-tenant (deve passar antes de qualquer PR)
pytest tests/test_tenant_isolation.py -v
```

## Coisas que o Claude NÃO deve fazer

- ❌ Adicionar fallback hardcoded em `config.py` ("só pra dev funcionar")
- ❌ Logar pergunta do usuário em texto plano (pode conter PII)
- ❌ Fazer query de embeddings sem `tenant_id` no WHERE, mesmo "temporariamente"
- ❌ Acoplar `core/` a um datasource específico — sempre via Adapter
- ❌ Trocar identidade visual sem confirmação (cores Lello são spec)
- ❌ Sumir com PII em logs com hash não-mascarado — usar mascaramento explícito
- ❌ Importar código copiado da `api-bella-ia` original sem revisar (a versão original tem secrets hardcoded e outras dívidas)

## Memória do projeto

Este projeto usa o sistema de memória do Claude. Antes de assumir contexto histórico, consulte os arquivos em `memory/` (no `.claude/projects/...` do usuário).

Memórias relevantes que podem existir:
- Perfil do operador principal (postura com PROD)
- Decisões arquiteturais (stack, theming, AWS-leaning)
- Bugs ou incidentes históricos do projeto Lello/Bella original

## Referências cruzadas

- **Sercofi/Total IA Contábil** — projeto irmão interno; estrutura de RULES/SPECS/SKILL foi inspirada nele.
- **api-bella-ia original** — versão Lello-only anterior deste produto. Origem do `core_logic.py`, `llm_services.py`, `data_loader.py` e `tenants/`. Não importar arquivos diretos — adaptar com cuidado e remover dívidas técnicas (secrets hardcoded, acoplamento Databricks).
