# Runbook — Onboarding de Novo Tenant

> Audience: time de implantação. Pré-requisito: dados cadastrais e documentos da administradora recebidos.

## Resumo
Habilitar uma nova administradora (tenant) no Assistente Virtual de Condomínios. O resultado final é: usuários daquela administradora conseguem fazer perguntas e receber respostas baseadas nos documentos dela, sem qualquer chance de vazar dados de outros tenants.

## Pré-requisitos
- [ ] Contrato assinado e flag de sandbox aprovada
- [ ] Identidade visual da administradora (cor primária, logo SVG, fonte) — opcional; se não vier, usa tema Lello
- [ ] Origem dos documentos definida (PDFs em pasta? Postgres deles? S3?)
- [ ] Tabela de condomínios e áreas comuns (CSV ou conexão direta)
- [ ] Lista inicial de condomínios para indexar (referências)

## Etapas

### 1. Criar tenant_id
- Convenção: snake-lower, curto, único. Ex: `lello`, `apsa`, `graiche`.
- Reservar o ID em `api/tenants/configs/_reserved.md` (anota quem é dono daquele ID).

### 2. Criar JSON de configuração
- Copiar `api/tenants/configs/_template.json` para `<tenant_id>.json`
- Preencher campos obrigatórios: `nome_empresa`, `nome_assistente`, `contatos`, `urls`, prompts customizados, `datasource`, `theme`
- Validar placeholders: o registry rejeita campos com `XX`, `XXXXXXXX`, `placeholder`

### 3. Subir secrets do datasource
- Se o tenant traz seu próprio Postgres/S3, criar entrada no Secrets Manager:
  ```
  Nome: tenant/<tenant_id>/datasource
  Valor (JSON): { "host": "...", "user": "...", "password": "...", ... }
  ```
- No JSON do tenant, referenciar por nome: `"datasource_secret_name": "tenant/<tenant_id>/datasource"`
- **Nunca colocar a senha no JSON do tenant.**

### 4. Carregar dados estruturados
- Tabelas `condominios` e `condominio_areas` populadas para o tenant
- Script: `python -m ingestion.load_structured --tenant <id> --csv ./data/<id>/condominios.csv --type condominios`
- Validar contagem: `SELECT COUNT(*) FROM condominios WHERE tenant_id = '<id>'`

### 5. Rodar pipeline de ingestão de embeddings
- Para cada condomínio (ou em lote):
  ```
  python -m ingestion.run \
      --tenant <id> \
      --connector pdf_folder \
      --path ./data/<id>/docs/<referencia> \
      --referencia <referencia>
  ```
- Acompanhar logs. Esperar mensagem `[finished] processados=N skipped=M erros=0` para cada referência.

### 6. Validar isolamento (CRÍTICO)
Antes de habilitar, rodar testes de isolamento:
```bash
pytest tests/test_tenant_isolation.py::test_tenant_<id> -v
```
O teste:
- Faz query como tenant A, conta linhas
- Tenta query cross-tenant (mesma referência, tenant_id errado) — deve retornar zero
- Verifica RLS ativo no Postgres

Se qualquer um falhar: **NÃO HABILITAR**. Reportar e investigar.

### 7. Validação funcional manual
- Subir frontend apontando para o tenant: `?tenant=<id>`
- Verificar que o tema visual aplica (cor primária, logo)
- Fazer 5 perguntas de validação:
  1. Pergunta sobre dados cadastrais (cat 0)
  2. Pergunta sobre área comum (cat 42)
  3. Pergunta sobre assembleia (cat 51)
  4. Pergunta vaga (cat esclarecimento)
  5. Pergunta sem documento — deve retornar `mensagem_nao_encontrada` configurada, **não** chute
- Citações de fonte aparecem na UI

### 8. Habilitar tenant
- Editar JSON: `"enabled": true`
- Recarregar registry (restart da API ou hot-reload se implementado)
- Confirmar no `/health`: tenant aparece em `tenants_enabled`

### 9. Comunicar e documentar
- Informar contato da administradora que está ativo
- Adicionar ao `MEMORY.md` do projeto: "Tenant `<id>` (`<nome_empresa>`) ativado em <data>. Stack: <connector>. Secrets: `tenant/<id>/datasource`."

## Checklist final

- [ ] JSON criado e sem placeholders
- [ ] Secrets no Secrets Manager
- [ ] Dados estruturados carregados (count > 0)
- [ ] Pipeline de embeddings concluído sem erros
- [ ] `tests/test_tenant_isolation.py::test_tenant_<id>` passou
- [ ] Validação manual com 5 perguntas
- [ ] `enabled: true` e tenant aparece no `/health`
- [ ] Memória do projeto atualizada

## Troubleshooting

| Sintoma | Provável causa | Ação |
|---------|----------------|------|
| Pipeline falha com 401 OpenAI | Chave OPEN_AI_KEY ausente/inválida | Verificar env e Secrets Manager |
| Pipeline falha com 429 repetido | Rate limit OpenAI | Reduzir `INGESTION_MAX_WORKERS` ou aguardar |
| Query do tenant retorna zero documentos | RLS bloqueou (faltou `SET app.current_tenant`) | Checar middleware da API; ver log do Postgres |
| Cross-tenant retorna linha de outro tenant | RLS desativado em alguma tabela | Auditar: `SELECT relname, relrowsecurity FROM pg_class WHERE relname IN ('documents_embeddings','condominios','condominio_areas')` |
| Tema visual não aplica | `theme` ausente no JSON ou typo nos hex codes | Validar contra schema; recarregar tenant |
