# Assistente Virtual de Condomínios — Skill Guide para Claude Code

## Visão Geral do Projeto

SaaS multi-tenant de **assistente virtual conversacional para administradoras de condomínios**. Cada empresa contratante (administradora) é um tenant isolado. O assistente responde perguntas de moradores/síndicos/funcionários sobre o condomínio (atas, editais, regras, dados cadastrais, áreas comuns) usando RAG sobre os documentos da própria administradora.

**Quem vende:** Lello Condomínios. A Lello é o tenant principal e referência da identidade visual do produto. Outras administradoras contratantes entram como tenants adicionais com a sua própria identidade (theming por tenant via CSS variables).

**Origem:** evolução do projeto interno `api-bella-ia` da Lello, que era hardcoded para um único Databricks. Esta versão multi-empresas:
- Não depende de Databricks dos clientes
- Cada cliente tem sua própria base de documentos e seus próprios embeddings em Postgres+pgvector
- Conector configurável por cliente para origem de dados (PDFs, Postgres, S3, planilhas)
- Pipeline de ingestão de embeddings standalone (substitui o Spark/Databricks da Lello)

## Stack Tecnológica

### Backend (Python — `api/`)
- **Python 3.11+**
- **FastAPI** — API REST + OpenAPI
- **Pydantic v2** — DTOs e validação
- **SQLAlchemy 2 + asyncpg** — ORM async
- **Alembic** — migrations (a definir; SQL puro inicialmente em `db/migrations/`)
- **pgvector** — busca por similaridade no Postgres
- **OpenAI SDK** — `text-embedding-3-large` (embeddings) + GPT-5.2 (geração)
- **tiktoken** — contagem/truncate de tokens (limite 8191 do `text-embedding-3-large`)
- **PyJWT** — autenticação
- **loguru** — logging estruturado com mascaramento

### Pipeline de Ingestão (Python — `ingestion/`)
- Job standalone que substitui o pipeline Spark/Databricks da Lello
- **ThreadPoolExecutor** para paralelizar chamadas OpenAI (espelha o `max_workers=10`, `batch_size=100` do script Spark original)
- **Conectores plugáveis** para origens de dados (`pdf_folder`, `postgres`, `s3`, ...)
- **Idempotência** via tabela de auditoria (chave `tenant_id + referencia + file_name + record_id`) — não reprocessa o que já tem embedding
- Trigger inicial: CLI (`python -m ingestion.run --tenant <id> --referencia <ref>`); evolui para fila depois

### Frontend (TypeScript — `web/`)
- **Next.js 15** (App Router)
- **React 19**
- **Tailwind 3.4** + **shadcn/ui** (`class-variance-authority` + `clsx` + `tailwind-merge`)
- **lucide-react** — ícones
- **next-themes** — theming (CSS variables por tenant)
- Identidade Lello como tema padrão; outros tenants sobrescrevem variables

### Infraestrutura
- **Local:** `docker-compose.yml` com Postgres 16 + pgvector, Redis 7, API, Web
- **Produção (planejado AWS):** RDS Postgres com pgvector, ECS/Fargate, S3 (PDFs/anexos), Secrets Manager, ALB
- **Cloud-agnostic:** abstração de object storage (interface `Storage` com impls S3 e Azure Blob); sem Bedrock/Azure OpenAI — apenas OpenAI direto

## Multi-Tenancy

### Modelo de isolamento
- Cada tenant tem um JSON em `api/tenants/configs/<tenant_id>.json`
- O JSON define: contatos, URLs, prompts customizados, **datasource adapter** e suas credenciais, **theming** (cores/logo)
- Toda query a documentos passa por `tenant_id` — RLS no Postgres garante que vetores não vazem entre tenants
- Cache em memória usa chave `f"{tenant_id}:{referencia}"` (nunca apenas `referencia`)

### Adapter Pattern de DataSource
Hoje a Lello tem dados no Databricks. Outras administradoras não terão. Por isso:

```
api/tenants/datasources/
├── base.py              # interface abstrata DataSource
├── postgres_pgvector.py # default — embeddings em Postgres local
├── databricks.py        # legado Lello (opcional, ativável por config)
└── factory.py           # resolve adapter via tenant_config.datasource.type
```

A `core_logic` nunca chama Spark/SQL direto — chama `tenant.datasource.buscar_embeddings(referencia)`.

### Identidade visual por tenant
- Lello é o tema default (cores Lello em `web/theme/lello.ts`). Paleta estimada dos screenshots: `lello-red #CB1D40`, `lello-wine #5D0E1F`, `lello-peach #F5B79E`, `lello-ink #0E0E0E`. Hex oficiais pendentes de brandbook.
- Cada tenant pode sobrescrever: `primary`, `primary_foreground`, `secondary`, `accent`, `ink`, `muted`, logo, fontes
- Implementação via CSS custom properties + `next-themes`

## Estrutura de Diretórios

```
<raiz do projeto>
├── SKILL.md                 # este arquivo — visão geral
├── RULES.md                 # regras críticas obrigatórias
├── SPECS.md                 # especificação funcional do RAG e categorias
├── CLAUDE.md                # instruções pro Claude no repo
├── README.md
├── docker-compose.yml
├── .env.example
│
├── instrucao/               # runbooks operacionais
│   ├── onboarding_tenant.md
│   ├── ingestao_embeddings.md
│   └── recuperacao_producao.md
│
├── api/                     # backend FastAPI
│   ├── main.py              # entry point FastAPI
│   ├── auth.py              # JWT
│   ├── config.py            # secrets via env (sem fallbacks!)
│   ├── core/                # lógica RAG (classificação, busca, geração)
│   ├── llm/                 # wrappers OpenAI (embeddings + completion)
│   ├── tenants/
│   │   ├── models.py        # TenantConfig (Pydantic)
│   │   ├── registry.py      # carregamento e cache dos JSONs
│   │   ├── datasources/     # Adapter Pattern
│   │   └── configs/         # 1 JSON por tenant
│   ├── storage/             # abstração S3/Azure Blob
│   └── pdf/                 # processamento de PDFs (chunking, OCR)
│
├── ingestion/               # pipeline standalone de embeddings
│   ├── run.py               # CLI: --tenant, --referencia, --connector
│   ├── chunking.py          # truncate 8191 tokens via tiktoken
│   ├── audit.py             # tabela controle (idempotência)
│   └── connectors/          # leitura de origens diferentes
│       ├── pdf_folder.py
│       ├── postgres.py
│       └── s3.py
│
├── web/                     # frontend Next.js 15
│   ├── app/
│   ├── components/
│   ├── theme/
│   │   ├── lello.ts         # tema padrão (cores Lello)
│   │   └── default.ts
│   └── public/
│
├── db/
│   └── migrations/
│       ├── 001_init.sql     # extensão pgvector + tabelas multi-tenant
│       └── 002_audit.sql    # tabela de auditoria de ingestão
│
└── tests/
```

## Padrões de Código

### Python (backend + ingestão)
- Type hints em todas as funções
- Docstrings em português
- `async`/`await` em I/O (Postgres, OpenAI, HTTP)
- Classes com responsabilidade única
- Logging estruturado com loguru (JSON em produção)
- Tratamento de exceções granular — nunca silenciar
- Constantes em UPPER_SNAKE_CASE em `config.py`
- **Secrets via env** — `os.getenv("KEY")` sem fallback de string. Se faltar, derruba o boot.

### TypeScript (frontend)
- Componentes funcionais + hooks
- shadcn/ui como base (não recriar primitives)
- Theming via CSS variables; `next-themes` para troca dinâmica
- Server Components por padrão; `"use client"` só quando necessário

## Convenções de Nomenclatura

- Arquivos Python: `snake_case.py`
- Arquivos TypeScript: `kebab-case.ts` / `kebab-case.tsx`
- Classes: `PascalCase`
- Funções/métodos: `snake_case` (Python), `camelCase` (TypeScript)
- Variáveis de ambiente: `UPPER_SNAKE_CASE`
- Tenants: `tenant_id` em snake-lower (ex: `lello`, `apsa`, `graiche`)
- Tabelas Postgres: `snake_case`, plural (ex: `documents_embeddings`, `tenants`)

## Como Executar (local)

```bash
# 1. Subir infra
docker-compose up -d postgres redis

# 2. Aplicar migrations
psql -h localhost -U bella -d assistente_condominios -f db/migrations/001_init.sql

# 3. Backend
cd api && pip install -r requirements.txt && uvicorn main:app --reload --port 8000

# 4. Frontend
cd web && npm install && npm run dev   # porta 3000

# 5. Ingestão de embeddings (exemplo)
cd ingestion && python run.py --tenant lello --referencia 12345 --connector pdf_folder --path /docs/lello/12345
```

## Referências Importantes

- **Modelo de embedding:** OpenAI `text-embedding-3-large` (3072 dimensões, limite 8191 tokens)
- **Modelo de geração:** OpenAI GPT-5.2
- **Truncate de tokens:** sempre via `tiktoken.encoding_for_model("text-embedding-3-large")` antes de embeddar — espelha o comportamento do `corta_para_limite_tokens` do script Spark original da Lello
- **Busca de similaridade:** `pgvector` `<=>` (cosine distance); top-K configurável por tenant
- **Categorias:** o sistema classifica a pergunta em categorias (ex: dados cadastrais, áreas comuns, assembleias, editais). Cada categoria pode mapear para resposta padrão, query estruturada nomeada, ou busca por embeddings (default). Definição em `SPECS.md`.
