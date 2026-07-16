# Plano Mestre — Sprint Pitch ao Dono (10 dias)
## Trilhas Henrique + João, interdependências e impeditivos

> **Documento-irmão:** `ESCOPO_SPRINT_PITCH_DONO.md` (detalhamento técnico dos blocos do João).
> Este documento é o mapa de coordenação: quem faz o quê, quando as trilhas se cruzam, e o que trava o quê.

---

## 1. Como as trilhas se interligam (leia isto primeiro)

São duas trilhas paralelas com **7 pontos de cruzamento obrigatórios**:

```
JOÃO  (Frente A — Demo + Landing)
─────●────────●───●───●────●─────────●──────●────→ APRESENTAÇÃO
     D1       D3  D4  D5   D6        D8     D10
     │        │   │   │    │         │      │
     │     P1-P8  │  ata  números  DRY-RUN ensaio
     │   +custo  áudio real valida │      final
     │   OpenAI  +PDF │    │       │      │
─────●────────●───●───●────●─────────●──────●────→ APRESENTAÇÃO
HENRIQUE  (Frente B — Narrativa + Número + Deck + Política)
```

**A regra de ouro da coordenação:** o João nunca deve estar bloqueado esperando insumo seu. Cada entrega sua tem prazo D-x porque o bloco dele começa em D-x+1. Se um insumo vai atrasar, avisar o João com 24h de antecedência para ele reordenar blocos — o escopo dele tem folga interna para absorver 1 dia de reordenação, não mais.

**Fluxo inverso também existe:** o João te entrega 2 insumos que alimentam o SEU trabalho (estimativa de custo OpenAI para o slide do número; timing real do roteiro para calibrar o deck). Cobre-os dele.

---

## 2. Linha do tempo unificada

| Dia | HENRIQUE | JOÃO | Ponto de sincronização |
|-----|----------|------|------------------------|
| **D0 (hoje)** | Receber e avaliar o vídeo do Bloco 0 · Decisão go/reordena — **gate do sprint inteiro** | **BLOCO 0:** subir o `main` do zero + screen capture bruto de 5 min (landing, login lello, pergunta no chat, POST criando tenant, login com tema novo) + reporte de estado | ⟵ Vídeo sobe HOJE; Blocos 1–5 só começam com o go do Henrique |
| **D1** | Reunião com o Diretor de TI (ver 3.1) · Ligação ao marketing: hex oficiais + SVG do logo · Iniciar articulação da ata real · Decidir contratação do PJ de design (landing) | Bloco 1a-1b: diagnóstico de estado do repo + higiene do main | Fim do dia: check de 15 min — João reporta estado real do repo; qualquer surpresa reordena o plano AGORA, não no D5 |
| **D2** | Construção do número — parte 1: cotações AWS (calculadora oficial, arquitetura do dossiê), 2-3 cotações de PJ DevOps + pentest | Bloco 1c: migration de versionamento de embedding + tabela `schema_migrations` | — |
| **D3** | Construção do número — parte 2: verba de marketing/lançamento (com apoio do diretor), estimativa CLT ano 1 · **ENTREGA ao João: P1–P8 recalibradas para o dono** | Bloco 2 inicia: fluxos demo dos 3 módulos · **ENTREGA ao Henrique: estimativa de custo OpenAI da ingestão do corpus** (a partir de amostra — alimenta o slide do número) | ⟵⟶ Troca dupla: perguntas descem, custo sobe |
| **D4** | Consolidar o número em faixa com fases destraváveis (No Ar 1 → 3 → 2) + buffer 25-30% · **ENTREGA ao João: áudio de assembleia (2-3 min) + PDF de cobrança (≤5 pág.)** | Bloco 2 continua: Atas e Cobranças com os insumos recebidos · Config do tenant JHP | ⟶ Insumos de demo descem |
| **D5** | Deck — parte 1: estrutura dos 6 atos (ver 3.3) · **ENTREGA ao João: ata real** | Bloco 2 fecha: registro JHP ensaiado com fallback · Bloco 3 inicia: mascaramento da ata real + geração da carteira sintética | ⟶ Ata real desce |
| **D6** | Deck — parte 2: slides de negócio (mercado, modalidades, tese) · **Validar com a operação os números de inadimplência sintéticos** e devolver ao João · Cobrar hex do marketing (prazo ideal) | Bloco 3: ingestão da carteira sintética · Bloco 4 em paralelo: landing com os 8 agentes | ⟵⟶ Números validados descem; se hex chegou, aplica na landing |
| **D7** | Deck — parte 3: slide do pedido + apêndices (resposta Modalidade C em 4 camadas, comparativo Superlógica) · Bateria de perguntas hostis com esqueleto de resposta (ver 3.4) — sessão com o diretor | Bloco 3 fecha: pergunta-âncora validada 5x consecutivas · Bloco 4 fecha: landing completa | Fim do dia: João confirma "roteiro tecnicamente completo" |
| **D8** | **DRY-RUN COMPLETO** (Henrique + Diretor + João assistindo): apresentação inteira, tempo cronometrado, perguntas hostis simuladas pelo diretor | **FEATURE FREEZE ao fim do dia** · Gravar vídeo fallback da demo completa · Participar do dry-run operando a demo | ⟵⟶ Maior sincronização do sprint — presença dos 3 |
| **D9** | Ajustes de deck e narrativa apontados no dry-run · Segundo ensaio (pode ser só Henrique + João) | Apenas correções apontadas no dry-run (nada estrutural) · Segundo ensaio | ⟵⟶ Ensaio conjunto |
| **D10** | Ensaio final · Revisão do checklist · Preparação pessoal (quem fala o quê, transições) | Ensaio final · Checklist pré-apresentação (banco populado, serviços 1 comando, script JHP, vídeo acessível) | ⟵⟶ Ensaio final conjunto |

---

## 3. Escopo detalhado — HENRIQUE

### 3.1 · D1 — Reunião de alinhamento com o Diretor de TI (a reunião mais importante do sprint)

Pauta obrigatória, nesta ordem:
1. **Objetivo da reunião com o dono** — decidir entre: (A) sair com recursos aprovados, (B) sair com mandato de princípio + segunda reunião para o número detalhado, (C) híbrido com faixa de valor ancorada. *Quem conhece o dono é o diretor — a decisão é dele com seu apoio.*
2. **Divisão de papéis na apresentação** — proposta: diretor abre (ameaça/janela) e fecha (pedido); Henrique conduz a demo e a tese. Ajustar conforme o conforto dele.
3. **Como o dono decide** — extrair do diretor: o dono é de números ou de visão? Reunião longa ou curta? Já rejeitou projetos de tecnologia antes, e por quê?
4. **Resposta combinada para "quanto isso já custou?"** — alinhar a versão antes que a pergunta exista.
5. **Confirmar disponibilidade dele para o dry-run em D8** — sem o diretor no dry-run, a apresentação a dois não existe.

### 3.2 · D2–D4 — Construção do número

Bottom-up, usando o plano No Ar 1 → 3 → 2 como esqueleto:

| Componente | Fonte | Fase |
|---|---|---|
| Infraestrutura AWS (ECS/Fargate, RDS, S3) | Calculadora oficial AWS, arquitetura já especificada no dossiê | No Ar 1 |
| Custo OpenAI de ingestão do corpus | **João entrega em D3** (estimativa por amostra) | No Ar 1 |
| PJ DevOps + pentest | 2-3 cotações rápidas | No Ar 1 |
| Verba de lançamento/marketing | Diretor + área de marketing da Lello | No Ar 3 |
| 2-3 contratações CLT ano 1 + jurídico + CS | Estimativa salarial de mercado | No Ar 2 |

Formato final: **faixa, faseada, com pontos de decisão** — "fase 1 custa X e entrega Y em N meses; fases 2 e 3 são decisões futuras com estes preços". Buffer de 25-30% embutido, não destacado.

### 3.3 · D5–D7 — Deck (arco de ~25 minutos, 6 atos)

1. **A ameaça e a janela** (Superlógica/agentes/agosto) — *diretor* — 3 min
2. **A tese:** white-label de operação → white-label de dados/IA — *Henrique* — 2 min
3. **Demo:** Chat → Atas → Cobranças → pergunta-âncora (clímax) → registro live JHP ("assim um concorrente vira cliente em 5 min") — *Henrique conduz* — 10-12 min
4. **O negócio:** mercado (500 mil condomínios, R$165 bi), modalidades A e B em destaque, C em tom de visão, landing projetada como prova — 3 min
5. **O pedido**, faseado — *diretor* — 3 min
6. **Perguntas** — apêndices de bolso prontos

Regra de honestidade verbalizada na demo: fronteira explícita entre "funciona hoje" e "os recursos constroem" (produtos "em breve" e carteira sintética apresentada como *"carteira de demonstração modelada na nossa operação"*).

### 3.4 · D7 — Bateria de perguntas hostis (preparar com o diretor)

Mínimo obrigatório, cada uma com esqueleto de resposta ensaiado:
- "Quanto isso já custou?" (resposta combinada em D1)
- "Por que não compramos da Superlógica?" (→ comprar dela é entregar a ela o único ativo defensável da Lello: o dado)
- "Como garantem que os dados dos clientes não vazam/não são vendidos?" (→ resposta em 4 camadas: contratual, técnica, incentivo, verificação — apêndice pronto)
- "Quem mantém isso se o João sair?" (→ parte do pedido é justamente estruturar o time)
- "Quando isso dá dinheiro?" (→ *"o modelo comercial está desenhado — híbrido de mensalidade da plataforma, preço por condomínio ativo, módulos premium e franquia de consumo — e a precificação final, calibrada com custos reais de operação, é entregável da fase 1 do investimento"* + o slide de fases responde o horizonte)

### 3.5 · Atividades paralelas NÃO-bloqueantes (não travam o pitch, mas a carta branca cobre e o relógio delas já corre)

- **Jurídico:** iniciar o template de contrato de tenant com cláusula de dados agregados (lead time de semanas — se começar só depois do pitch, vira gargalo do No Ar 2)
- **Funil de contratação CLT:** abrir agora, mesmo que a pessoa chegue em 2-3 meses (aterrissa no No Ar 2)
- Ambas podem ser mencionadas ao dono como "já em andamento" — sinal de execução, não de promessa

---

## 4. Escopo resumido — JOÃO (detalhe completo no documento-irmão)

| Bloco | Dias | Entrega |
|---|---|---|
| 1 — Discovery + Higiene + Fundações | D1–D2 | App sobe limpo; migration versionamento embedding; `schema_migrations` |
| 2 — Módulos live + JHP | D3–D5 | Roteiro dos 3 módulos <12 min sem erro 3x; registro JHP ensaiado c/ fallback |
| 3 — Carteira sintética + pergunta-âncora | D6–D7 | 15-25 atas sintéticas (molde: ata real); pergunta-âncora correta 5x; ata real mascarada no Bella Chat |
| 4 — Landing | D3–D8 paralelo | 8 agentes (4 live/fase final + 4 em breve); modalidades; hex oficiais quando chegarem |
| 5 — Freeze + ensaios | D8–D10 | Vídeo fallback; 3 execuções limpas consecutivas; checklist |

**Entregas do João para o Henrique:** estimativa de custo OpenAI (D3) · confirmação "roteiro tecnicamente completo" (D7) · demo operada no dry-run (D8).

---

## 5. Impeditivos mapeados (e o plano B de cada um)

| # | Impeditivo | Trava o quê | Plano B |
|---|---|---|---|
| 1 | Diretor indisponível no D1 | Objetivo da reunião, papéis, número de marketing | Reunião vira call de 30 min; se impossível, Henrique assume premissas (objetivo B — mandato de princípio) e valida depois |
| 2 | Ata real não chega até D5 | Bloco 3 parcialmente | João gera carteira 100% sintética usando modelos públicos de ata como molde (Alternativa B); perde-se o momento de autenticidade, demo sobrevive |
| 3 | Hex/logo do marketing não chegam até D6 | Polimento da landing | Apresentar com paleta estimada atual — risco conhecido e aceito; ninguém trava por isso |
| 4 | Operação não valida números de inadimplência até D6 | Verossimilhança da carteira | Henrique valida sozinho com benchmarks públicos de inadimplência condominial em SP; menos ideal, suficiente |
| 5 | Diretor indisponível no dry-run D8 | Apresentação a dois | Gravar o dry-run e enviar; ensaio com ele em D9 mesmo que curto; NUNCA apresentar a dois sem um ensaio conjunto |
| 6 | Repo em estado inesperado no D1 (lição das sessões anteriores) | Todo o cronograma | Check de fim de dia D1 existe exatamente para isso; 1 dia de folga estrutural absorve; mais que isso → cortar pela ordem definida (landing → cenário simplificado → X-User-Id) |
| 7 | Registro live do JHP falhar na apresentação | Momento white-label | Fallback já no escopo do João: tenant pré-criado em banco paralelo, transição invisível |
| 8 | Demo quebrar ao vivo | Tudo | Vídeo fallback gravado no D8 + roteiro fixo + ambiente congelado 48h |

---

## 6. Regras de coordenação do sprint

1. **Check diário de 15 min** (fim do dia, formato livre): cada um reporta entregue/em risco/bloqueado. Único ritual obrigatório.
2. **Insumo vai atrasar → aviso com 24h** para reordenação de blocos.
3. **Mudança de escopo só passa pelo Henrique** — inclusive as "melhorias rápidas" que aparecem no meio do caminho. Depois do D8, nem pelo Henrique.
4. **Decisões travadas neste documento são âncoras** — reabrir uma decisão custa tempo do cronograma e exige trade-off explícito (o que sai para essa mudança entrar?).

---

## 7. Critério de pronto do sprint (os dois juntos)

- ✅ Roteiro completo (landing → módulos → JHP live → pergunta-âncora) em ~15 min, 3x sem erro, ambiente congelado 48h, vídeo fallback gravado — *João*
- ✅ Deck de 6 atos ensaiado a dois, número em faixa faseada, 5 perguntas hostis com resposta pronta, papéis definidos — *Henrique*
- ✅ Um dry-run completo com o diretor realizado — *os dois*
