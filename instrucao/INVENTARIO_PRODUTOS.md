# Inventário de Produtos — Lello AI Platform

Gerado em 2026-05-18. Mapeamento explícito: módulo técnico → produto comercial.

Referência estratégica: `VISION.md` na branch `feat/lello-ai-platform-recalibration`.

---

## Visão geral da plataforma

A Lello AI Platform é organizada em **4 camadas de produto** progressivas:

| Camada | Nome | Status |
|--------|------|--------|
| 1 — Compreensão | QA sobre documentos, extração estruturada | ✅ Implementado |
| 2 — Inteligência | Score ISC, predição de inadimplência, risco | 🔲 Roadmap (Fase 4, 9-12 meses) |
| 3 — Automação | Comunicados automáticos, cobrança, assembleias | 🔲 Roadmap (Fase 5, 12-18 meses) |
| 4 — Mercado | Dados anonimizados para seguradoras/bancos | 🔲 Roadmap (Fase 6, 18-24 meses) |

---

## Produtos implementados (Camada 1)

### Produto 1 — Agente Conversacional

**Slug do módulo:** `chat`
**Nome comercial sugerido:** Bella Chat / Agente Conversacional

**Arquivos técnicos:**
- `api/core/rag.py` — Pipeline RAG (classificação → busca → geração)
- `api/core/classifier.py` — Classificador de categoria (GPT, temperature=0)
- `api/llm/openai_client.py` — Wrapper OpenAI (embedding + geração)
- `api/routers/chat.py` — `POST /chat`
- `api/tenants/datasources/postgres_pgvector.py` — Busca vetorial por tenant
- `web/app/` (root) — Interface de chat
- `web/components/chat/` — Componentes da conversa

**O que faz:**
Responde perguntas em linguagem natural sobre documentos do condomínio (atas, editais, regulamentos, dados cadastrais). Usa RAG com busca vetorial (pgvector, texto-embedding-3-large) + geração GPT. Classifica a pergunta em 68+ categorias para roteamento inteligente (dados cadastrais, áreas comuns, assembleias, etc.). Nunca inventa — sem documentos, retorna mensagem de "não encontrei".

**Valor comercial:**
Reduz volume de chamadas e WhatsApp da administradora. Morador obtém resposta instantânea sobre seu condomínio específico, 24/7.

**Status no lello.json:** `"chat": true` ✅

---

### Produto 2 — Agente para Geração de Ata

**Slug do módulo:** `atas`
**Nome comercial sugerido:** Bella Atas / Agente de Ata

**Arquivos técnicos:**
- `api/atas/` — Módulo completo (9 arquivos)
- `api/routers/atas.py` — 19 endpoints REST
- `web/app/atas/` — Páginas de lista, criação e detalhe
- `web/components/atas/` — Editor e status badge
- `db/migrations/010_atas.sql` + `012_atas_workflow.sql`

**O que faz:**
Pipeline completo de ata de assembleia condominial:
1. Upload de áudio da assembleia → transcrição via Whisper (Azure Blob + OpenAI)
2. Geração da ata em 3 passos via LLM (GPT-5.4)
3. Fluxo multi-ator: consultor → síndico → presidente → correção → registro
4. Máquina de estados com 15 estados; notificações por e-mail em cada transição
5. Comparador automático de diferenças (difflib) entre versão gerada e devolvida
6. Correção ortográfica e formatação final
7. Export HTML standalone

**Valor comercial:**
Reduz horas de trabalho manual na elaboração de atas. Padroniza qualidade, garante rastreabilidade e elimina erros de digitação.

**Status no lello.json:** não contratado (necessário adicionar `"atas": true` para demo)

---

### Produto 3 — Agente Financeiro / Extração de Dados

**Slug do módulo:** `cobrancas`
**Nome comercial sugerido:** Bella Cobranças / Agente Financeiro

**Arquivos técnicos:**
- `api/cobrancas/` — Módulo completo (8 arquivos)
- `api/routers/cobrancas.py` — 6 endpoints REST
- `web/app/cobrancas/` — Página de upload e jobs
- `db/migrations/006_cobrancas_jobs.sql`

**O que faz:**
Extração estruturada de PDFs de cobrança condominial:
1. Upload do PDF pelo usuário
2. Google Document AI extrai texto e tabelas (OCR inteligente)
3. GPT-4o mapeia os campos para schema tipado (`CobrancaResultado`)
4. Resultado: morador, apartamento, vencimento, valor, juros — em JSON e XLSX

**Limitação atual:** PDFs ≤ 15 páginas (modo sync). Batch async para PDFs maiores está planejado.

**Valor comercial:**
Elimina digitação manual de boletos e demonstrativos. Integração com sistemas financeiros da administradora.

**Status no lello.json:** não contratado (necessário adicionar `"cobrancas": true` para demo)

---

## Produtos no roadmap (não implementados no `main`)

### Produto 4 — Agente Churn / Inadimplência

**Slug planejado:** `inadimplencia` (ainda não existe no catálogo)
**Camada:** 2 — Inteligência
**Status:** Mencionado no VISION.md como "AgenteInadimplência" existente na Lello. Precisa ser portado/integrado.

**O que faria:**
Score de risco de inadimplência por condomínio. Predição de churn de síndico. Integração com os dados históricos da Lello.

**Como adicionar ao catálogo quando implementado:**
1. Adicionar entrada em `api/tenants/modulos.py:MODULOS_DISPONIVEIS`
2. Usar `require_module("inadimplencia")` nas rotas
3. Criar migration para backfill

---

### Produto 5 — QA Multi-condomínio

**Status:** Previsto para Fase 2 (3-6 meses no roadmap do VISION.md)

**O que faria:**
Perguntas que cruzam a carteira inteira do tenant.
Exemplo da pergunta-âncora do demo: *"Quais condomínios da minha carteira tiveram aumento de inadimplência mencionado em ata nos últimos 6 meses?"*

O `search_chunks` do `QAService` na branch `feat/lello-ai-platform-recalibration` já aceita `condominio_id=None` para buscar em toda a carteira — é a base para este produto.

---

## Módulos no catálogo atual (`api/tenants/modulos.py`)

```python
MODULOS_DISPONIVEIS = {
    "chat":      "Bella Chat — assistente RAG sobre documentos",
    "cobrancas": "Bella Cobranças — extração de PDFs de cobrança",
    "atas":      "Bella Atas — geração e workflow de atas de assembleia",
}
```

Para adicionar novo módulo: 1) nova entrada aqui, 2) `require_module()` nas rotas, 3) migration de backfill se necessário.

---

## Configuração de módulos por tenant (para o demo)

O demo precisa mostrar os 3 módulos ativos. Alterar `lello.json` ou via admin UI:

```json
"modulos_contratados": {
  "chat": true,
  "atas": true,
  "cobrancas": true
}
```
