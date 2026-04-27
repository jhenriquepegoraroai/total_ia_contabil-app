# Assistente Virtual de Condomínios — Especificação Funcional (SPECS.md)

## 1. Contexto

Administradoras de condomínios atendem milhares de moradores e síndicos com perguntas recorrentes sobre seus condomínios: "qual o horário do salão de festas?", "quando é a próxima assembleia?", "qual a taxa de condomínio?", "o que diz a última ata sobre obra na fachada?".

Esse atendimento hoje é feito por humanos por telefone, WhatsApp e portal. O Assistente Virtual de Condomínios automatiza essas respostas usando RAG sobre os documentos da própria administradora (atas, editais, regulamentos, dados cadastrais).

A primeira contratante é a **Lello Condomínios**. O produto é multi-tenant para que outras administradoras possam contratar.

## 2. Conceitos do Domínio

- **Tenant** = administradora contratante (ex: Lello, Apsa, Graiche)
- **Condomínio** = unidade gerenciada pela administradora; identificado por `referencia` (número interno do condomínio na administradora)
- **Documento** = ata, edital, regulamento, comunicado etc. de um condomínio
- **Parágrafo / chunk** = unidade indexada (um documento gera N parágrafos com embedding cada)
- **Categoria** = classificação semântica da pergunta para roteamento (ex: "dados cadastrais", "áreas comuns", "assembleia", "edital")

## 3. Fluxo Principal de Pergunta

```
Usuário envia pergunta + referencia (condomínio)
      │
      ▼
┌─────────────────────────────────────────┐
│ ETAPA 1 — Autenticação e tenant         │
│  • valida JWT                           │
│  • extrai tenant_id do token            │
│  • carrega TenantConfig do registry     │
│  • SET app.current_tenant no Postgres   │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│ ETAPA 2 — Reformulação (opcional)       │
│  • prompt_formatacao reformula p/ busca │
│  • temperature=0                        │
└──────────────┬──────────────────────────┘
               ▼
┌─────────────────────────────────────────┐
│ ETAPA 3 — Classificação                 │
│  • categorias_prompt do tenant          │
│  • temperature=0, top_p=1               │
│  • retorna número da categoria          │
└──────────────┬──────────────────────────┘
               ▼
       ┌───────┴────────┐
       │   Categoria?   │
       └───┬────┬───┬──┘
           │    │   │
           ▼    ▼   ▼
   ┌────────┐ ┌─────────┐ ┌───────────────┐
   │Resposta│ │ Query   │ │ Busca por     │
   │Padrão  │ │Estrutu- │ │ Embeddings    │
   │        │ │rada     │ │ (default)     │
   └────┬───┘ └────┬────┘ └───────┬───────┘
        │          │              │
        └──────────┴──────────────┤
                                   ▼
                    ┌──────────────────────────┐
                    │ ETAPA 4 — Geração GPT    │
                    │ • prompt_principal       │
                    │ • contexto = chunks      │
                    │ • temperature configurável│
                    │ • cita fontes            │
                    └──────────────┬───────────┘
                                   ▼
                            Resposta + citações
```

## 4. Categorias e Roteamento

Cada tenant define suas categorias no JSON. O default herdado da Lello inclui:

| Cat | Nome | Tipo de roteamento | Observação |
|-----|------|--------------------|------------|
| 0 | Dados cadastrais do condomínio | Query estruturada | Lê tabela `condominios` por referência |
| 42 | Áreas comuns do condomínio | Query estruturada | Lê tabela `areas` por referência |
| 51 | Resumo de assembleia mais recente | Busca direta sem embeddings | Filtra por regex AGE/AGO/ATA + data mais recente |
| 65 | Conteúdo de edital | Busca direta sem embeddings | Filtra `file_name LIKE '%edital%'` + data mais recente |
| 67 | Data do edital mais recente | Query estruturada | Retorna apenas a data |
| 68 | Comparação edital vs ata | Combinação | Edital mais recente + atas mais recentes |
| esclarecimento | Pergunta vaga | `prompt_esclarecimento` | Retorna pergunta ao usuário |
| (default) | Demais perguntas | Busca por embeddings | Top-K via cosine similarity |

Tenants novos podem **adicionar/remover/redefinir** categorias no seu JSON. O motor é genérico.

## 5. Ingestão de Embeddings

### 5.1 Origens suportadas (conectores)
- **`pdf_folder`** — varre uma pasta com PDFs e extrai texto + metadados (file_name, data inferida do nome ou conteúdo)
- **`postgres`** — lê uma tabela do banco do cliente (configurável: schema, tabela, colunas que viram texto e metadados)
- **`s3`** — varre bucket/prefixo
- (extensível) `csv`, `sharepoint`, `gdrive` etc.

### 5.2 Pipeline (espelha o script Spark da Lello)

```
Conector lê origem
      │
      ▼
Para cada documento:
  • split em parágrafos (heurística simples ou via PDF layout)
  • cada parágrafo vira um "chunk"
      │
      ▼
Idempotência:
  • content_hash = sha256(tenant_id + referencia + file_name + record_id + paragraph)
  • se já existe em embeddings_audit com mesmo hash → SKIP
      │
      ▼
Truncate por chunk:
  • tiktoken encoding "text-embedding-3-large"
  • MAX_TOKENS = 8191 → trunca se exceder
      │
      ▼
Batches de 100 chunks
      │
      ▼
ThreadPoolExecutor (max_workers=10):
  • OpenAI embed_query por chunk
  • retry exp backoff (max_retries=3, timeout=30s)
  • on 429 → pausa 60s
      │
      ▼
Upsert em documents_embeddings (transação por batch):
  • (tenant_id, referencia, file_name, record_id, paragraph, embedding, data_valida, content_hash)
      │
      ▼
Append em embeddings_audit:
  • contador, started_at, finished_at, qtde_processada, qtde_skipped, qtde_erros
      │
      ▼
Invalida cache da API para (tenant, referencia)
```

### 5.3 Comparação com o pipeline Spark original
| Item | Lello/Spark | Assistente Virtual |
|------|-------------|--------------------|
| Origem dos parágrafos | Tabela Delta `lello_documents_data_paragrafo_valida_filtrada` | Conector configurável |
| Geração de embedding | `pandas_udf` distribuído no Spark | `ThreadPoolExecutor` em Python |
| Paralelismo | `max_workers=10`, `batch_size=100` | Mesmos defaults |
| Truncate tokens | `tiktoken` MAX_TOKENS=8191 | Idêntico |
| Persistência intermediária | Parquet em DBFS | Transação por batch direto no Postgres |
| Tabela final | Delta particionada por `referencia` | Postgres particionada por `tenant_id` (ou `(tenant_id, referencia)` se volume justificar) |
| Idempotência | leftanti join por `(recordId, referencia, nomedoarquivo)` | content_hash em audit + upsert |
| Auditoria | `controle_quantidade_tabelas_projeto_bella` | `embeddings_audit` |
| OPTIMIZE / ANALYZE | `OPTIMIZE` Delta | `VACUUM ANALYZE` + reindex periódico do índice ivfflat/hnsw |

## 6. Schema do Banco (resumo)

Detalhes em `db/migrations/001_init.sql`. Tabelas principais:

- **`tenants`** — uma linha por tenant; metadata e flag `enabled`
- **`tenant_configs`** — JSON da config (snapshot versionado)
- **`condominios`** — dados cadastrais por tenant + referência
- **`condominio_areas`** — áreas comuns por tenant + referência
- **`documents`** — metadados de documento (tenant, referencia, file_name, data_valida, ...)
- **`documents_embeddings`** — chunks com `embedding vector(3072)`, `paragraph text`, `content_hash`
- **`embeddings_audit`** — log de cada execução do pipeline
- **`chat_sessions`** / **`chat_messages`** — histórico de conversa por tenant + sessão
- **`users`** — usuários da plataforma (síndicos, atendentes, admins)

RLS ativo em todas as tabelas com `tenant_id`. Política: `current_setting('app.current_tenant') = tenant_id`.

## 7. Identidade Visual e Theming

### 7.1 Tema padrão (Lello)
Paleta calibrada visualmente a partir do site `site-da-administradora.exemplo` (screenshots de 2026-04-27). **Valores são estimativas visuais — devem ser substituídos pelos hex oficiais quando o brandbook chegar.**

| Token | Hex | Uso observado no site |
|-------|-----|----------------------|
| `lello-red` | `#CB1D40` | Logo, eyebrows ("PRAZER, LELLO!"), CTA primário ("2ª via do boleto"), faixa do footer |
| `lello-wine` | `#5D0E1F` | CTA secundário ("Fale com o time comercial") |
| `lello-peach` | `#F5B79E` | Card lateral do hero (tom acolhedor) |
| `lello-ink` | `#0E0E0E` | Headlines pretas ("Viver o Condomínio Une!") |
| `lello-gray-bg` | `#EDEDED` | Background do footer |
| `lello-white` | `#FFFFFF` | Background principal |

- Tom da marca: **humanizado, acolhedor, premiado** — fotos com pessoas reais, selos visíveis, headlines em peso forte
- Fonte: sans-serif moderna; Inter como fallback até confirmar a fonte oficial Lello
- Cantos arredondados (~8-12px em botões e cards)
- Sombras sutis; layout limpo com bastante respiro
- Logo Lello em `web/public/themes/lello/logo.svg` (SVG pendente — capturar do site oficial ou solicitar)

### 7.2 Theming por tenant
- Cada tenant define no seu JSON:
  ```json
  "theme": {
    "primary": "#CB1D40",
    "primary_foreground": "#FFFFFF",
    "secondary": "#5D0E1F",
    "accent": "#F5B79E",
    "ink": "#0E0E0E",
    "muted": "#EDEDED",
    "logo_url": "/themes/lello/logo.svg",
    "favicon_url": "/themes/lello/favicon.ico",
    "font_family": "Inter, sans-serif"
  }
  ```
- Aplicação via CSS custom properties no `<html>` (definidas server-side a partir do tenant)
- shadcn/ui consome essas variables (`--primary`, `--primary-foreground`, etc.)

## 8. Onboarding de Novo Tenant (resumo)

Detalhes em `instrucao/onboarding_tenant.md`. Etapas:

1. Criar JSON em `api/tenants/configs/<tenant_id>.json` (template em `_template.json`)
2. Subir secrets do datasource no Secrets Manager
3. Carregar dados cadastrais (`condominios`, `areas`) — script de import por tenant
4. Rodar pipeline de ingestão para popular `documents_embeddings`
5. Validar: query de teste por tenant + checagem de isolamento (não retorna dados de outro tenant)
6. Habilitar tenant (`enabled=true`)

## 9. Premissas / Decisões Já Tomadas

- Stack: FastAPI + Postgres+pgvector + Next.js 15 + Tailwind + shadcn (espelha Total IA no front)
- Cloud: agnostic, mira AWS (Lello é AWS); Azure como segunda opção via abstração de storage
- Sem dependência de Bedrock, Azure OpenAI ou Databricks **dos clientes** — apenas OpenAI direto
- Lello continuará sendo possível como adapter Databricks (legado) **se desejado** — mas o default e a recomendação para qualquer cliente novo é Postgres+pgvector

## 10. Itens em Aberto (a alinhar com o cliente)

- [ ] Confirmar hex oficiais da Lello (paleta atual é estimativa visual dos screenshots de 2026-04-27)
- [ ] Fonte oficial Lello (fallback atual: Inter)
- [ ] SVG do logo oficial (capturar do site ou solicitar)
- [ ] Quem é o segundo cliente piloto (define prioridades do conector)
- [ ] Modelo de cobrança (por tenant? por mensagem? por documento indexado?) — pode impactar audit/billing tables
- [ ] Canais de entrada: web only? WhatsApp? Telefone (voz)? — define API surface
