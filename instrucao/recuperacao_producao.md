# Runbook — Recuperação de Produção

> Quando algo dá errado em PROD. **Sempre confirmar com o operador principal antes de qualquer ação destrutiva.**

## Princípios
1. **Estabilizar antes de investigar.** Se usuários estão impactados, primeiro restaura — depois entende.
2. **Evidência antes de mudança.** Screenshots, logs, queries de leitura ficam antes de qualquer DDL/DML.
3. **Reversível por default.** Toda ação tem caminho de rollback documentado **antes** de executar.
4. **Comunicar.** Informar o operador principal + stakeholders quando algo sério.

## Saúde do sistema

### Health check rápido
```bash
curl https://api.assistente-condominios.lello.com.br/health
# Espera: {"status":"ok","tenants_enabled":[...],"db":"ok","redis":"ok","openai":"ok"}
```

### Logs recentes (CloudWatch / Loki / wherever)
```bash
# Últimos 15 minutos, severidade ERROR
aws logs tail /ecs/avc-api --since 15m --filter-pattern '"level":"ERROR"'
```

## Cenários comuns

### 1. API retorna 500 em todas as requests
**Provável causa:** banco caiu / Secrets rotacionados sem atualizar app / OpenAI down

**Diagnóstico:**
```bash
curl https://api.assistente-condominios.lello.com.br/health    # quem está down?
aws logs tail /ecs/avc-api --since 5m | grep -i "error\|exception"
```

**Ações por causa:**
- DB down → checar RDS console; failover se Multi-AZ
- Secrets rotacionados → atualizar task definition do ECS, fazer redeploy
- OpenAI down → degraded mode (responder "estamos indisponíveis temporariamente, tente em alguns minutos")

### 2. Tenant específico retornando "documento não encontrado" para tudo
**Provável causa:** RLS bloqueando / cache corrompido / pipeline de embeddings falhou

**Diagnóstico:**
```sql
-- Conectar como super-user (não como app)
SELECT COUNT(*) FROM documents_embeddings WHERE tenant_id = '<tenant>';
SELECT MAX(finished_at), qtde_processada, qtde_erros FROM embeddings_audit
  WHERE tenant_id = '<tenant>' ORDER BY finished_at DESC LIMIT 5;
```

**Ações:**
- Count zero ou desatualizado → re-rodar pipeline de ingestão
- Count OK → invalidar cache (`DEL avc:cache:<tenant>:*` no Redis) e testar
- Se persistir → checar logs da API para `tenant_id=<tenant>` no período

### 3. Cross-tenant leak detectado
**Severidade: 🚨 CRÍTICA. PARAR TUDO.**

**Ações imediatas (com aprovação do operador principal):**
1. Desabilitar tenant impactado: `UPDATE tenants SET enabled=false WHERE id IN (...)`
2. Capturar evidência: query/log que mostrou o leak
3. Verificar RLS:
   ```sql
   SELECT relname, relrowsecurity, relforcerowsecurity
   FROM pg_class
   WHERE relname IN ('documents_embeddings','condominios','condominio_areas','documents');
   ```
4. Auditar últimas requests do tenant afetado
5. Comunicar admins dos tenants envolvidos (LGPD — pode ser incidente reportável)
6. Pós-mortem obrigatório

**NUNCA tentar "limpar" o cache e seguir** — se RLS falhou, o problema é estrutural.

### 4. Pipeline de embeddings travado / heartbeat ausente
**Diagnóstico:**
```bash
ps aux | grep "ingestion.run"
aws logs tail /ecs/avc-ingestion --since 30m | tail -50
```

**Ações:**
- Sem heartbeat por > 5min → matar processo e reexecutar (idempotente, seguro)
- Erros 429 OpenAI persistentes → reduzir `INGESTION_MAX_WORKERS` para 5

### 5. Custo OpenAI disparou
**Provável causa:** loop de reembed / pipeline rodou em modo full reindex sem necessidade

**Diagnóstico:**
```sql
SELECT DATE(finished_at), SUM(qtde_processada)
FROM embeddings_audit
WHERE finished_at > NOW() - INTERVAL '7 days'
GROUP BY 1 ORDER BY 1 DESC;
```

**Ações:**
- Achar o execução anômala em `embeddings_audit`
- Verificar se foi mudança de modelo (esperado caro) ou bug (não esperado)
- Bug → fix + reverter operação

## Procedimentos de manutenção

### Rotação de secrets
1. Criar novo secret no Secrets Manager (versão nova)
2. Atualizar referência na task definition do ECS
3. Deploy rolling (zero downtime)
4. Validar no `/health` que API subiu com versão nova
5. Após 24h, retirar versão antiga
6. Documentar rotação aqui

### Backup do banco
- RDS automatizado: 7 dias retenção (config padrão)
- Backup manual antes de migration: `aws rds create-db-snapshot --db-snapshot-identifier avc-pre-mig-YYYYMMDD ...`

### Restore de backup
- **Confirmar com o operador principal primeiro.**
- Restore cria nova instância — não sobrescreve a atual.
- Apontar app para nova instância só após validação.

## Janela de operação

- **PROD freeze:** evitar deploys em horário de pico (08:00-18:00 BRT, dias úteis)
- **Janelas seguras:** madrugada (00:00-06:00 BRT) e fim de semana
- **Hotfix urgente:** sempre OK, com aprovação do operador principal + comunicação stakeholders

## Contatos
- Operador principal — TBD: email/canal
- Cliente principal (administração) — TBD: email/canal de incidente
- OpenAI status — https://status.openai.com
- AWS status (sa-east-1) — https://status.aws.amazon.com

## Pós-mortem
Para qualquer incidente que afete usuários por > 5 min, abrir post-mortem em `instrucao/postmortems/YYYY-MM-DD_<slug>.md` com:
- Linha do tempo
- Causa raiz
- Resolução
- Ações preventivas
- Status de cada ação preventiva
