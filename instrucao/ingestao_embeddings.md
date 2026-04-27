# Runbook — Ingestão de Embeddings

> Pipeline standalone que substitui o pipeline Spark/Databricks da Lello.
> Espelha a lógica do script Spark original (chunking 8191 tokens, batch 100, max_workers 10, idempotência via leftanti) mas grava em Postgres+pgvector.

## Quando rodar
- Onboarding inicial de um tenant (todos os condomínios de uma vez)
- Novo documento entra para um condomínio existente (incremental)
- Documento atualizado (content_hash muda → reembed)
- Reindex completo (raro — após mudança de modelo de embedding ou bug grave)

## Pré-requisitos
- [ ] Tenant existe no registry e tem `datasource` configurado
- [ ] Conector adequado para a origem dos documentos (PDFs, Postgres, S3...)
- [ ] `OPEN_AI_KEY` disponível no env
- [ ] Postgres com pgvector ativo e migration `001_init.sql` aplicada

## Comando padrão

```bash
python -m ingestion.run \
    --tenant <tenant_id> \
    --connector <pdf_folder|postgres|s3> \
    --path <path-ou-URI> \
    --referencia <numero-do-condominio>     # opcional; sem isso processa todas as refs
```

### Exemplos

```bash
# Lello — pasta local de PDFs de um condomínio
python -m ingestion.run \
    --tenant lello \
    --connector pdf_folder \
    --path ./data/lello/12345 \
    --referencia 12345

# Apsa — Postgres do cliente, todas as referências
python -m ingestion.run \
    --tenant apsa \
    --connector postgres \
    --path "postgresql://..."   # ou nome do secret no Secrets Manager
```

## Fluxo interno (resumo)

```
┌──────────────┐
│ Conector lê  │
│  origem      │
└──────┬───────┘
       ▼
┌───────────────────────────┐
│ Para cada documento:      │
│  • split em parágrafos    │
│  • content_hash por chunk │
└──────┬────────────────────┘
       ▼
┌───────────────────────────┐
│ Filtro idempotência:      │
│ SELECT 1 FROM             │
│  embeddings_audit WHERE   │
│  (tenant,ref,file,record) │
│  AND content_hash = ...   │
│ → SKIP se hash igual      │
└──────┬────────────────────┘
       ▼
┌───────────────────────────┐
│ Truncate por chunk:       │
│ tiktoken text-embedding-  │
│  3-large, MAX 8191        │
└──────┬────────────────────┘
       ▼
┌───────────────────────────┐
│ Batches de 100            │
│ ThreadPoolExecutor(10)    │
│ embed_query por chunk     │
└──────┬────────────────────┘
       ▼
┌───────────────────────────┐
│ UPSERT documents_embeddings│
│ (transação por batch)     │
└──────┬────────────────────┘
       ▼
┌───────────────────────────┐
│ Append em embeddings_audit│
│ (qtde, duração, erros)    │
└──────┬────────────────────┘
       ▼
┌───────────────────────────┐
│ Invalida cache da API     │
│ para (tenant, referencia) │
└───────────────────────────┘
```

## Logs esperados

```
[start] tenant=lello referencia=12345 connector=pdf_folder path=./data/lello/12345
[reading] 23 PDFs encontrados, 1287 parágrafos extraídos
[idempotency] 1180 já indexados (content_hash bate), 107 a processar
[batch 1/2] processando 100 chunks com 10 workers...
[batch 1/2] concluído em 8.43s
[batch 2/2] processando 7 chunks com 10 workers...
[batch 2/2] concluído em 1.12s
[upsert] 107 chunks inseridos em documents_embeddings
[audit] registro #45 escrito (qtde_processada=107, qtde_skipped=1180, qtde_erros=0)
[cache] invalidado (lello:12345)
[finished] tenant=lello referencia=12345 duracao=12.34s
```

## Defaults (configuráveis via env)

| Variável | Default | Origem (script Spark Lello) |
|----------|---------|----------------------------|
| `INGESTION_BATCH_SIZE` | 100 | `batch_size = 100` |
| `INGESTION_MAX_WORKERS` | 10 | `max_workers = 10` |
| `INGESTION_OPENAI_TIMEOUT` | 30 | `request_timeout=30` |
| `INGESTION_OPENAI_MAX_RETRIES` | 3 | `max_retries=3` |
| Token limit | 8191 | `MAX_TOKENS = 8191` |
| Modelo | `text-embedding-3-large` | idem |

## Idempotência (importante)

A chave de identidade de um chunk é **`(tenant_id, referencia, file_name, record_id)`**.

`content_hash = sha256(tenant_id + referencia + file_name + record_id + paragraph)`.

Antes de embeddar, o pipeline checa em `embeddings_audit` se já existe entrada com **mesma chave + mesmo content_hash**:
- Existe e hash igual → **SKIP** (chunk já indexado, conteúdo não mudou)
- Existe e hash diferente → **REEMBED** (conteúdo mudou, atualiza)
- Não existe → **EMBED** (novo)

Isso reproduz o `leftanti` do script Spark, mas com a vantagem de detectar atualização de conteúdo.

## Tabela de auditoria

`embeddings_audit` registra cada execução:

| coluna | descrição |
|--------|-----------|
| contador | sequencial |
| started_at, finished_at | timestamps |
| tenant_id | qual tenant |
| referencia | qual condomínio (NULL = full reindex) |
| connector | conector usado |
| qtde_chunks_origem | quantos vieram do conector |
| qtde_processada | embeddings novos/atualizados |
| qtde_skipped | hash igual, sem mudança |
| qtde_erros | falhas após retries |
| duracao_segundos | total |

Equivalente à tabela `controle_quantidade_tabelas_projeto_bella` do Spark da Lello.

## Recuperação de falhas

### Pipeline morreu no meio
- Sem problema. Reexecutar com mesmos parâmetros — o que já foi embeddado tem `content_hash` registrado e será pulado.

### Erros 429 OpenAI
- Pipeline pausa o pool por 60s e retoma.
- Se persiste: reduzir `INGESTION_MAX_WORKERS` para 5 e re-executar.

### Inconsistência: `documents_embeddings` tem linhas, `embeddings_audit` não tem registro
- Indica que o batch falhou após o INSERT mas antes do audit. Improvável (transação por batch).
- Diagnóstico: `SELECT COUNT(*) FROM documents_embeddings WHERE tenant_id=$1 AND referencia=$2`.
- Solução: deletar e re-rodar — `DELETE FROM documents_embeddings WHERE tenant_id=$1 AND referencia=$2` (com aprovação humana).

### Quero reembeddar do zero (após mudar modelo)
1. **Confirmar com o operador principal antes** — operação destrutiva.
2. Backup: `pg_dump -t documents_embeddings ...`
3. `DELETE FROM documents_embeddings WHERE tenant_id=$1`
4. Re-rodar pipeline.

## Métricas a observar
- Tempo médio por chunk (alvo: <0.5s)
- Taxa de erros (alvo: 0; >1% requer investigação)
- Custo OpenAI por execução (logado em `qtde_processada × ~0.00013 USD/1k tokens`)
