# Rotas da API — Lello AI Platform (v0.6.0)

Gerado em 2026-05-18 a partir de `api/routers/*.py`.
Para a lista ao vivo, suba a API e acesse: `GET http://localhost:8000/openapi.json`

---

## Health

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check da API |

---

## Auth (`/auth`)

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/auth/login` | Login com email + senha → JWT em cookie HttpOnly |
| POST | `/auth/logout` | Logout (invalida cookie) |
| POST | `/auth/dev-token` | Gera token de dev (desabilitado em produção) |

---

## Chat (`/chat`) — Módulo: `chat`

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/chat` | Pergunta ao assistente RAG — retorna resposta, citações, trace_id |

---

## Atas (`/atas`) — Módulo: `atas`

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/atas` | Lista atas do tenant |
| POST | `/atas` | Cria ata em status `rascunho` |
| GET | `/atas/{ata_id}` | Detalhe de uma ata |
| POST | `/atas/{ata_id}/audio/upload-url` | Gera SAS URL para upload direto de áudio |
| POST | `/atas/{ata_id}/audio/{audio_id}/concluir` | Confirma upload → dispara transcrição STT (202) |
| GET | `/atas/{ata_id}/audios` | Lista uploads de áudio com status de transcrição |
| PUT | `/atas/{ata_id}/insumos` | Atualiza insumos da geração (cabeçalho, resumo, edital) |
| POST | `/atas/{ata_id}/gerar` | Dispara geração via LLM em background (202) |
| PUT | `/atas/{ata_id}/edicao-consultor` | Consultor salva edição livre da ata |
| POST | `/atas/{ata_id}/enviar-sindico` | Consultor envia para revisão do síndico (202) |
| POST | `/atas/{ata_id}/enviar-presidente` | Consultor envia para revisão do presidente (202) |
| POST | `/atas/{ata_id}/devolver` | Síndico/presidente devolve ata editada → agenda comparador (202) |
| POST | `/atas/{ata_id}/aprovar-diff` | Consultor aprova/rejeita diff do comparador |
| POST | `/atas/{ata_id}/corrigir` | Consultor dispara corretor ortográfico diretamente (202) |
| POST | `/atas/{ata_id}/finalizar` | Consultor finaliza → move para `registrada` |
| GET | `/atas/{ata_id}/diff` | Retorna versão de comparação mais recente |
| GET | `/atas/{ata_id}/versoes` | Lista versões da ata (sem HTML) |
| GET | `/atas/{ata_id}/versoes/{versao_id}` | Versão específica com HTML completo |
| GET | `/atas/{ata_id}/exportar` | Export HTML standalone da ata |

---

## Cobranças (`/cobrancas`) — Módulo: `cobrancas`

| Método | Path | Descrição |
|--------|------|-----------|
| POST | `/cobrancas/extract` | Upload PDF → extrai dados via Document AI + GPT-4o (job assíncrono) |
| GET | `/cobrancas/jobs` | Lista jobs de extração do tenant |
| GET | `/cobrancas/jobs/{job_id}` | Status de um job |
| GET | `/cobrancas/jobs/{job_id}/result` | Resultado estruturado de um job concluído |
| GET | `/cobrancas/jobs/{job_id}/excel` | Download XLSX com resultados do job |
| DELETE | `/cobrancas/jobs/{job_id}` | Remove job e resultado |

---

## Admin — Tenants e Módulos (`/admin`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/admin/modulos` | Lista módulos disponíveis no catálogo |
| GET | `/admin/tenants` | Lista todos os tenants com métricas |
| GET | `/admin/tenants/{tenant_id}` | Detalhe de um tenant |
| POST | `/admin/tenants` | Cria novo tenant |
| PUT | `/admin/tenants/{tenant_id}` | Atualiza config completa de um tenant |
| PATCH | `/admin/tenants/{tenant_id}/enabled` | Habilita/desabilita tenant |
| GET | `/admin/audit` | Log de ações do superadmin |
| POST | `/admin/cobrancas/test-connection` | Testa credenciais GCP Document AI de um tenant |

---

## Admin — Dados (`/admin`)

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/admin/tenants/{tenant_id}/sources` | Lista fontes de dados do tenant |
| GET | `/admin/tenants/{tenant_id}/sources/{source_id}` | Detalhe de uma fonte |
| POST | `/admin/tenants/{tenant_id}/sources` | Cria fonte de dados |
| PATCH | `/admin/tenants/{tenant_id}/sources/{source_id}` | Edita fonte |
| DELETE | `/admin/tenants/{tenant_id}/sources/{source_id}` | Remove fonte |
| POST | `/admin/sources/test-connection` | Testa conexão de uma fonte |
| GET | `/admin/tenants/{tenant_id}/sources/{source_id}/files` | Lista arquivos na fonte |
| POST | `/admin/tenants/{tenant_id}/sources/{source_id}/ingest` | Dispara job de ingestão |
| GET | `/admin/tenants/{tenant_id}/ingestions` | Lista jobs de ingestão |
| GET | `/admin/tenants/{tenant_id}/ingestions/{job_id}` | Status de um job de ingestão |
| GET | `/admin/files` | Lista arquivos do storage do tenant |
| POST | `/admin/files/upload` | Upload de arquivo para o storage |
| GET | `/admin/tenants/{tenant_id}/users` | Lista usuários do tenant |
| POST | `/admin/tenants/{tenant_id}/users` | Cria usuário no tenant |
| PATCH | `/admin/tenants/{tenant_id}/users/{user_id}` | Edita usuário |
| PATCH | `/admin/tenants/{tenant_id}/users/{user_id}/password` | Reseta senha |
| DELETE | `/admin/tenants/{tenant_id}/users/{user_id}` | Remove usuário |
| GET | `/admin/tenants/{tenant_id}/chats` | Lista sessões de chat do tenant |
| GET | `/admin/tenants/{tenant_id}/chats/{session_id}` | Mensagens de uma sessão |
| GET | `/admin/tenants/{tenant_id}/tables` | Lista tabelas estruturadas do tenant |
| GET | `/admin/tenants/{tenant_id}/tables/{table_name}` | Conteúdo paginado de uma tabela |

---

## Tenant Users (`/tenant-users`) — auto-gestão pelo admin do tenant

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/tenant-users` | Lista usuários do próprio tenant (tenant_id vem do JWT) |
| POST | `/tenant-users` | Cria usuário no próprio tenant |
| PATCH | `/tenant-users/{user_id}` | Edita nome/role/enabled/referencia |
| PATCH | `/tenant-users/{user_id}/password` | Reseta senha |

---

## Resumo

| Escopo | Total de rotas |
|--------|---------------|
| Health | 1 |
| Auth | 3 |
| Chat | 1 |
| Atas | 19 |
| Cobranças | 6 |
| Admin (tenants/módulos) | 8 |
| Admin (dados/users/chats/tabelas) | 16 |
| Tenant Users | 4 |
| **Total** | **58** |
