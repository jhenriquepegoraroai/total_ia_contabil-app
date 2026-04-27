# Assistente Virtual de Condomínios

SaaS multi-tenant de assistente conversacional com RAG para administradoras de condomínios. A primeira contratante é a **Lello Condomínios**.

> Para entender a arquitetura e os padrões antes de mexer em código, leia primeiro `SKILL.md`, `RULES.md`, `SPECS.md` e `CLAUDE.md`.

## Stack

- **Backend:** Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy + asyncpg
- **Banco:** Postgres 16 + pgvector (busca por similaridade)
- **LLM:** OpenAI `text-embedding-3-large` + GPT-5.2
- **Frontend:** Next.js 15 + React 19 + Tailwind + shadcn/ui (theming Lello + por tenant)
- **Cache/fila:** Redis 7
- **Infra prod (planejada):** AWS ECS/Fargate + RDS + S3 + Secrets Manager

## Status do projeto

🚧 **Fase 0 — Fundação.** Estrutura de pastas, documentação do método e infraestrutura local. Sem código de aplicação ainda.

### Roadmap

- [x] **Fase 0** — Fundação: SKILL/RULES/SPECS/CLAUDE, docker-compose, migration inicial, runbooks
- [ ] **Fase 1** — Adapter Pattern de DataSource (`base`, `postgres_pgvector`)
- [ ] **Fase 2** — Pipeline de Ingestão standalone (substitui o Spark da Lello)
- [ ] **Fase 3** — API FastAPI: auth, registry de tenants, core_logic, llm_services
- [ ] **Fase 4** — Frontend Next.js: chat, theming Lello, theming por tenant
- [ ] **Fase 5** — Onboarding do primeiro tenant Lello (em pgvector standalone)
- [ ] **Fase 6** — Deploy AWS (ECS/RDS/S3) — só após validação local

## Quickstart (dev local)

> Pré-requisitos: Docker Desktop, Python 3.11, Node 20+

```bash
# 1. Variáveis de ambiente
cp .env.example .env
# Edite .env e preencha OPEN_AI_KEY e SECRET_KEY_JWT

# 2. Subir infra
docker-compose up -d postgres redis

# 3. Aplicar migration
docker exec -i avc_postgres psql -U avc -d assistente_condominios < db/migrations/001_init.sql

# 4. Backend (em outro terminal — depois que a Fase 3 estiver feita)
cd api
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 5. Frontend (em outro terminal — depois que a Fase 4 estiver feita)
cd web
npm install
npm run dev
```

## Estrutura

```
.
├── SKILL.md          # Visão geral, stack, padrões de código
├── RULES.md          # Regras críticas (isolamento tenant, secrets, integridade)
├── SPECS.md          # Spec funcional: fluxo RAG, categorias, ingestão
├── CLAUDE.md         # Instruções para o Claude no repositório
├── docker-compose.yml
├── .env.example
│
├── api/              # Backend FastAPI
├── ingestion/        # Pipeline standalone de embeddings
├── web/              # Frontend Next.js
├── db/migrations/    # Schema Postgres + pgvector + RLS
├── instrucao/        # Runbooks operacionais
└── tests/
```

## Princípios

- **Isolamento multi-tenant é regra crítica** — query sem `tenant_id` é bug grave
- **A IA nunca inventa** — sem documento, retorna mensagem de "não encontrado"
- **Secrets nunca em código** — apenas via env vars / Secrets Manager
- **Cloud-agnostic com leve preferência AWS** (Lello é AWS); abstração de object storage permite Azure
- **Identidade visual da Lello como tema padrão**, com theming por tenant via CSS variables

## Origem

Evolução do projeto interno `api-bella-ia` da Lello — que era hardcoded para um único Databricks. Esta versão multi-empresas remove a dependência do Databricks dos clientes e adota Postgres+pgvector standalone.

## Licença

Proprietário — uso interno Lello + administradoras contratantes.
