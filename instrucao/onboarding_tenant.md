# Runbook — Onboarding de Nova Administradora

> Audience: time de implantação. Pré-requisito: contrato fechado, dados cadastrais e amostra de documentos da administradora recebidos.

## Resumo

Habilitar uma nova administradora (tenant) no Assistente Virtual de Condomínios. Resultado final: usuários daquela administradora conseguem fazer perguntas e receber respostas baseadas nos documentos dela, sem qualquer chance de vazar dados de outros tenants.

A partir da Fase 5+, o onboarding é **inteiramente via UI** (`/admin`) — os JSONs em `api/tenants/configs/` são apenas seed do bootstrap inicial. Tudo que segue assume API + frontend rodando (`docker-compose up`).

## Pré-requisitos

- [ ] Contrato assinado e flag de sandbox aprovada
- [ ] Identidade visual da administradora (cor primária, logo SVG, fonte) — opcional; se não vier, usa tema Lello padrão
- [ ] Origem dos documentos definida: PDFs em pasta? Planilha Excel/CSV? Postgres deles? S3? Azure Blob?
- [ ] Lista inicial de condomínios para indexar (referências)
- [ ] Você tem credenciais de **superadmin** (criadas via `python -m api.cli create-superadmin`)
- [ ] Decisão sobre a chave OpenAI: cliente usa a chave compartilhada da Lello, ou traz a própria?

## Etapas

### 1. Login como superadmin

Acesse `/login` → aba **Superadmin** → entre com email + senha. Você cai em `/admin` (lista de Administradoras).

> O JWT vai pra um cookie HttpOnly `avc_token`; nada sensível em localStorage.

### 2. Criar a Administradora

`/admin` → botão **Nova administradora**. Campos obrigatórios:

- **tenant_id**: snake-lower, curto, único. Ex: `lello`, `apsa`, `petropolis`.
  - O ID `_system` é reservado.
- **nome_empresa**, **nome_assistente**, **contatos** (telefone, whatsapp, email), **urls** (app moradores, portal)
- **datasource**: por enquanto sempre `postgres_pgvector` (multi-tenant via RLS no DB principal).
- **theme** (opcional): cor primária, fonte. Se vazio → tema Lello.
- **prompts** (opcional na criação): usa defaults; você ajusta na tela de edição depois.

Validação no submit:
- Tenant_id duplicado → erro 400
- Placeholders (`XX`, `XXXXXXXX`, `placeholder`, `TBD`) em contatos/urls → warning no log mas aceita

> Atrás dos panos: insere em `tenants` + `tenant_configs` e recarrega o `tenant_registry` em memória.

### 3. (Opcional) Configurar chave OpenAI dedicada

`/admin/tenants/<id>` → tab **Visão geral** → card **Chave OpenAI**. Dois modos:

| Modo | Quando usar |
|---|---|
| `lello` (default) | Cliente paga via contrato com a Lello; usa `OPEN_AI_KEY` do env. |
| `custom` | Cliente quer pagar consumo direto na conta dele — cole a chave `sk-proj-...`. |

A chave fica mascarada no GET (só os últimos 4 chars). Em PROD, mover para Secrets Manager (campo `secret_name`).

### 4. Cadastrar usuários

`/admin/tenants/<id>` → tab **Usuários** → form **Novo usuário**:

- **email** (login), **nome** (display), **role** (`admin` / `sindico` / `atendente` / `morador`), **senha** (mínimo 8 chars, bcrypt)

Roles e permissões:
- `admin` da administradora: pode tudo dentro do tenant (não é superadmin global).
- `sindico` / `atendente` / `morador`: só consomem o chat.

Reset de senha: botão "Senha" inline. Desabilitar usuário: botão "Desativar" (mantém histórico).

### 5. Cadastrar fontes de dados

`/admin/tenants/<id>` → tab **Fontes de dados** → **Nova fonte**.

| Tipo | Quando usar | Notas |
|---|---|---|
| **PDFs (upload)** | Atas, regulamentos, editais. Upload manual via UI. | Após salvar, arrasta PDFs no card e clica **Executar ingestão**. |
| **Excel (upload)** | FAQ ou regras tabulares. Define `coluna_texto` e opcionalmente `coluna_referencia`/`coluna_data`. | Mesmo fluxo de upload + ingestão. |
| **CSV (upload)** | Idem Excel. Aceita delimitador `;` para CSV brasileiro. | |
| **AWS S3** | Cliente já tem PDFs em bucket. Pronto pra IAM role (PROD) ou keys (DEV). | Botão **Testar conexão** lista 1 chave pra validar. |
| **Azure Blob** | Equivalente ao S3, com SAS token ou DefaultAzureCredential. | Idem teste de conexão. |
| **Postgres do cliente** | Cliente tem tabela com texto/condominio. Modo `table` (mapeia colunas) ou `custom_query`. | **Crítico**: connector valida identificadores SQL contra injeção (regex restrita). |

Para mudar config depois: ícone de lápis no card → form pré-preenchido. **Tipo é imutável** — para mudar tipo, delete e recrie.

### 6. Disparar ingestão de embeddings

Para cada fonte com arquivos prontos:
- Card da fonte → **Executar ingestão**.
- Acompanha em `/admin/tenants/<id>` → tab **Histórico de jobs**: status `running` → `done` (ou `failed`).
- Métricas no detalhe do job: chunks processados, skipped (idempotência), erros, duração.

Atrás dos panos: roda `ingestion.pipeline.executar()` num `asyncio.create_task` (não bloqueia o request HTTP). Cada chunk vai para `documents_embeddings` com `tenant_id` setado e RLS forçada — isolamento garantido a nível de DB.

#### CLI alternativo (batch / scripts)

Para casos batch sem passar pela UI (ex: ingestão noturna de uma pasta cheia):
```bash
python -m ingestion.run \
    --tenant <id> \
    --connector pdf_folder \
    --path ./data/<id>/docs/<referencia> \
    --referencia <referencia>
```

### 7. Validar isolamento (CRÍTICO)

Antes de habilitar, confirmar que RLS está bloqueando cross-tenant:

```bash
# Suite de isolamento (requer Postgres rodando)
docker exec avc_api python -m pytest tests/test_tenant_isolation.py -v
```

O teste verifica:
- Query como tenant A em uma referência → retorna linhas de A.
- Query como tenant A com `tenant_id` de B no body → retorna **zero** (RLS bloqueia mesmo com tenant_id manipulado).
- `pg_class.relrowsecurity = true` em todas as tabelas multi-tenant.

Se qualquer um falhar: **NÃO HABILITAR**. Reportar e investigar.

### 8. Validação funcional manual

1. `/login` → entrar como um morador do tenant criado (criado no passo 4).
2. Tela de chat aparece com identidade visual da administradora.
3. Fazer 5 perguntas-chave, escolhendo `referencia` = condomínio real:
   1. Dados cadastrais (cat 0 — estruturado): "qual o cnpj do condomínio?"
   2. Área comum (cat 42 — embeddings): "como reservar o salão?"
   3. Assembleia (cat 51 — pattern): "qual a pauta da última assembleia?"
   4. Pergunta vaga (cat -1 — esclarecimento): "e aí?"
   5. Pergunta sem documento — tem que retornar `mensagem_nao_encontrada` configurado, **não** chute.
4. Verificar que cada resposta traz citações de fonte (file_name + data_valida).

#### Auditoria das conversas

`/admin/tenants/<id>` → tab **Conversas**: lista de chat sessions com primeira pergunta + qtde mensagens. Click → bubbles user/assistant + citações + cat. Útil para LGPD e identificar perguntas frequentes que merecem virar `respostas_padrao`.

### 9. Comunicar e documentar

- Avisar contato da administradora que está ativo.
- Atualizar [MEMORY.md](../MEMORY.md) do projeto: "Tenant `<id>` (`<nome_empresa>`) ativado em <data>. Fontes: <tipos>. Modo OpenAI: <lello/custom>."

## Checklist final

- [ ] Tenant criado via UI sem placeholders
- [ ] Chave OpenAI configurada (lello shared ou custom)
- [ ] Usuários iniciais criados (síndico, admin do cliente)
- [ ] Pelo menos 1 fonte cadastrada com **última run OK**
- [ ] `tests/test_tenant_isolation.py` passa
- [ ] Validação manual com 5 perguntas
- [ ] Tab **Conversas** mostra os chats da validação
- [ ] [MEMORY.md](../MEMORY.md) atualizado

## Troubleshooting

| Sintoma | Provável causa | Ação |
|---------|----------------|------|
| `/admin` retorna 403 | Token JWT não tem `is_superadmin=true` | Confirmar que logou com email de superadmin (`SELECT email FROM users WHERE is_superadmin = true`). |
| Login retorna 401 mesmo com senha certa | Cookie HttpOnly não está chegando (CORS / credentials) | Confirmar que requests usam `credentials: 'same-origin'` e que está acessando via Next rewrite (`/api/auth/login`), não cross-origin. |
| Job de ingestão fica em `running` indefinidamente | Worker travou (provável OpenAI 429 ou rede) | Logs do `avc_api`: `docker logs avc_api --tail 200`. Reset manual: `UPDATE ingestion_jobs SET status='failed' WHERE id = '...'`. |
| Pipeline falha com 401 OpenAI | Chave da chave do tenant inválida (modo custom) | Validar no card OpenAI; trocar para `lello` se for o caso. |
| Pipeline falha com 429 repetido | Rate limit OpenAI | Reduzir `INGESTION_MAX_WORKERS` (env) ou aguardar reset. |
| Chat retorna "sem documento" mesmo com PDF subido | Categoria roteou para estruturado vazio + busca por embeddings também vazia | Verificar que a ingestão criou rows: `SELECT COUNT(*) FROM documents_embeddings WHERE tenant_id = '<id>' AND referencia = '<ref>'`. Se 0 → re-disparar ingestão. |
| Cross-tenant retorna linha de outro tenant | RLS desativada em alguma tabela | Auditar: `SELECT relname, relrowsecurity FROM pg_class WHERE relname IN ('documents_embeddings','condominios','condominio_areas','chat_sessions','chat_messages','tenant_data_sources','users')` — todas devem ter `t`. |
| UI não carrega tenant criado | Registry em memória não recarregou | Em DEV: `docker restart avc_api`. Em PROD: confirmar que o `/admin/tenants/<id>` PUT chamou `registry.recarregar()`. |
| Fonte do tipo Postgres falha "Identificador SQL inválido" | Nome de tabela/coluna tem caractere fora de `[A-Za-z_][A-Za-z0-9_]*` | Renomear no banco do cliente OU usar `custom_query` em vez de modo tabela. |
