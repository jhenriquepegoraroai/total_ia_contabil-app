# Assistente Virtual de Condomínios — Regras Obrigatórias (RULES.md)

## 🔴 REGRAS CRÍTICAS — NUNCA VIOLAR

### Isolamento Multi-Tenant
1. **Toda query a documentos, embeddings ou dados estruturados DEVE incluir `tenant_id` no `WHERE`.** Query sem filtro de tenant é bug crítico — cliente A não pode jamais ver dado de cliente B.
2. **Postgres com Row Level Security (RLS) ativo em todas as tabelas multi-tenant.** Toda conexão da aplicação seta `SET app.current_tenant = '<id>'` no início da transação. Sem fallback "admin bypass" no código de aplicação.
3. **Cache em memória usa chave composta `f"{tenant_id}:{referencia}"`.** Nunca apenas `referencia`. Colisão de cache entre tenants é leak.
4. **`tenant_id` é validado contra o JWT em toda request.** O tenant não vem do body da request — vem do token assinado. Cliente não pode escolher tenant arbitrário no payload.
5. **Logs incluem `tenant_id` mas não credenciais do tenant.** Connection strings, tokens de API e senhas dos datasources do tenant nunca aparecem em log, nem mascarados.

### Dados Sensíveis e PII
6. **Nunca logar e-mail, CPF, telefone ou nome completo em texto plano.** Mascaramento obrigatório: `joao***@gmail.com`, `123.***.**8-90`, `(11) 9****-1234`. Padrão: 3 primeiros e 2 últimos caracteres visíveis.
7. **PDFs e anexos são dados sensíveis.** Upload para S3/Blob via HTTPS, container privado, acesso via SAS/presigned URLs com expiração curta (≤ 15 min). Sem URL pública.
8. **Embeddings vetoriais não são "anonimizados" — são reversíveis em parte.** Tratar com o mesmo cuidado dos textos originais. Não exportar, não compartilhar entre tenants.
9. **Dados de moradores (lista de apartamentos, contatos, inadimplência) requerem RLS adicional por condomínio dentro do tenant.** Síndico do condomínio A não pode ver dados do condomínio B mesmo dentro da mesma administradora.

### Secrets e Credenciais
10. **Nenhum secret em código ou em `.env` versionado.** `.env.example` é template público com valores fake. `.env` está no `.gitignore`. Em produção, AWS Secrets Manager / Azure Key Vault.
11. **`config.py` lê secrets via `os.getenv("KEY")` sem fallback.** Se a variável não existe, `raise RuntimeError`. Nunca `os.getenv("KEY", "valor-de-dev")` — fallback hardcoded vaza pelo histórico do git.
12. **Credenciais de datasource do tenant ficam em Secrets Manager**, referenciadas no JSON do tenant por nome (`"db_password_secret_name": "tenant/lello/db"`). Nunca a string da senha no JSON.
13. **Rotação de chaves OpenAI a cada 90 dias.** Documentar a rotação em `instrucao/recuperacao_producao.md`.

### Integridade da Resposta
14. **A IA NUNCA inventa dados.** Se não há documento relevante (top-K abaixo do threshold de similaridade), retorna `mensagem_nao_encontrada` configurada por tenant. Nunca preenche com chute.
15. **Citação de fonte é obrigatória nas respostas.** Toda resposta gerada referencia `file_name` + página/parágrafo dos chunks usados. UI mostra a citação ao usuário.
16. **Classificação de categoria usa `temperature=0` e `top_p=1`.** Mesma pergunta deve cair na mesma categoria sempre (determinismo).
17. **Geração de resposta pode usar `temperature` configurável por tenant**, mas o default é `0.2` (baixa criatividade — RAG factual).
18. **Truncate de tokens antes de embeddar:** sempre via `tiktoken.encoding_for_model("text-embedding-3-large")` com `MAX_TOKENS=8191`. Espelha o `corta_para_limite_tokens` do script Spark original. Texto que passa do limite é truncado, nunca rejeitado silenciosamente.

## 🟡 REGRAS DE OPERAÇÃO

### Pipeline de Ingestão de Embeddings
19. **Idempotência obrigatória.** Antes de embeddar, checar tabela de auditoria `embeddings_audit` — se `(tenant_id, referencia, file_name, record_id)` já existe e o `content_hash` bate, pular. Replica a lógica `leftanti` do script Spark.
20. **Atomicidade em batches.** Cada batch (default 100 chunks) é uma transação. Falha de um chunk no batch não deve gerar embeddings parciais persistidos.
21. **Audit log de cada execução.** Registrar `tenant_id`, `referencia`, `connector`, `qtde_processada`, `qtde_skipped`, `qtde_erros`, `duracao_segundos`, `started_at`, `finished_at`. Equivalente à tabela `controle_quantidade_tabelas_projeto_bella` do Spark original.
22. **Paralelismo controlado.** ThreadPoolExecutor com `max_workers=10` por default (mesmo do script Spark). Configurável por tenant para respeitar rate limits da OpenAI.
23. **Retry com backoff exponencial em chamadas OpenAI.** `max_retries=3`, `request_timeout=30s`. Após esgotar, marcar o chunk como `EMBEDDING_FAILED` no audit e seguir.
24. **Rate limit awareness.** Se OpenAI retorna 429, pausar o pool por 60s. Não tentar burlar.

### RAG / Busca
25. **Top-K default = 8 chunks.** Configurável por tenant. Threshold mínimo de similaridade (cosine) default = `0.30` — abaixo disso, considera "não encontrado".
26. **Categorização ANTES da busca.** Pergunta passa por classificador GPT determinístico → cai em categoria → cada categoria roteia para: resposta padrão, query estruturada nomeada, ou busca por embeddings.
27. **Esclarecimento quando ambíguo.** Se a pergunta é vaga (categoria "esclarecimento"), retornar prompt de esclarecimento ao invés de chutar resposta.
28. **Contexto da conversa não cruza tenants.** Histórico de mensagens é particionado por tenant + sessão.

### Datasource Adapter
29. **`core_logic` nunca importa `databricks.connect`, `psycopg`, `boto3` etc.** Só conhece `tenant.datasource.buscar_embeddings(...)`. Trocar adapter é trocar JSON do tenant — não requer deploy de código.
30. **Toda implementação de `DataSource` filtra por `tenant_id` no SQL/query.** A interface não confia em filtros do chamador.
31. **Reconexão automática em sessões caídas.** Adapter Databricks já trata `INVALID_HANDLE.SESSION_CHANGED` (ver `data_loader.py` da Bella original). Adapter Postgres trata `connection closed`.

## 🟢 REGRAS DE QUALIDADE

### Logging e Observabilidade
32. **Trace ID por request** em formato `avc_{tenant}_{timestamp}_{uuid8}` (`avc` = Assistente Virtual de Condomínios). Propagado em headers (`X-Trace-Id`) e em todos os logs daquela request.
33. **Métricas mínimas:** tempo de classificação, tempo de busca vetorial, tempo de geração GPT, tokens consumidos por request, tenant, categoria. Exportar via `/metrics` (Prometheus format) quando entrar em produção.
34. **Erros nunca são silenciados.** `except Exception: pass` é proibido. `except Exception as e: logger.error(..., exc_info=True)` no mínimo.
35. **Logs estruturados (JSON) em produção, formato humano em dev.** loguru com sink condicionado a `APP_ENV`.

### Resiliência
36. **Circuit breaker em chamadas OpenAI.** Após 5 falhas consecutivas no serviço, pausar 60s antes de novas tentativas. Espelha a regra do Sercofi.
37. **Heartbeat do pipeline de ingestão.** Job longo emite heartbeat a cada 60s. Sem heartbeat por 5 min → considerar travado e alertar.
38. **Cache invalidado quando reindex roda.** Após pipeline de ingestão concluir para `(tenant, referencia)`, invalidar cache em memória da API daquela chave.

### Testes
39. **Todo adapter de DataSource tem teste de isolamento cross-tenant.** Cenário: 2 tenants com dados, query do tenant A não pode trazer linha do tenant B. Bug aqui é showstopper.
40. **Pipeline de ingestão tem teste de idempotência.** Rodar 2x a mesma referência não duplica linhas; modificação de conteúdo gera reembed (content_hash mudou).
41. **Truncate de tokens tem teste de boundary** (8190, 8191, 8192 tokens — só o último é truncado).
42. **Classificador de categoria tem golden tests.** Conjunto de perguntas-rótulo congelado; mudanças de prompt rodam contra o golden e reportam diferenças.
