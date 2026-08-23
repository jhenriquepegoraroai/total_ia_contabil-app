# Contrato de Features — trilho de ML

> Como um tenant entrega dado transacional para as capacidades de modelo
> (Churn, Fraude, Inadimplência, ISC).

## Por que existe

Os modelos são **globais, treinados no acervo da Lello, e calibrados por
tenant**. Um modelo global só roda na carteira de um parceiro se as variáveis
existirem lá **com a mesma semântica** — mesma definição de inadimplência,
mesma régua de cobrança, mesmo ciclo de boleto. O contrato é o documento que
torna isso verificável antes de qualquer score sair.

Sem ele, o risco não é o modelo falhar visivelmente: é ele devolver um número
plausível e errado. Resposta errada de chat o usuário percebe na hora; score
de churn errado ninguém percebe, e o parceiro age em cima dele por meses.

**O contrato é entregável de produto, não documentação interna.** É o que se
manda para o parceiro antes de ligar a capacidade.

## Como o contrato vive no banco

Migration `015_zona_features.sql`.

| Tabela | Papel |
|---|---|
| `feature_sets` | O contrato: nome, granularidade, versão e `schema_json` com as colunas esperadas |
| `feature_values` | Os dados entregues, série temporal por entidade e competência |
| `capability_scores` | A saída do modelo — worker escreve, API lê |
| `scoring_runs` | Auditoria de cada execução do batch |

Trocar de feature **não** exige migration: o contrato é linha em
`feature_sets`, não coluna em DDL.

### Formato do `schema_json`

```json
{
  "atraso_medio_dias": {
    "tipo": "number",
    "obrigatorio": true,
    "descricao": "Média de dias de atraso nos últimos 12 meses.",
    "nulo_significa": "sem histórico de cobrança no período"
  }
}
```

Campos: `tipo` (`number` | `integer` | `string` | `boolean` | `date`),
`obrigatorio`, `descricao` e — quando o `NULL` tiver significado de negócio —
`nulo_significa`. Esse último campo é o que evita o erro mais comum de
integração: parceiro manda `0` onde a Lello manda `NULL`, e o modelo lê
"pagou em dia" onde o correto era "não há histórico".

### Granularidade

`entidade` do `feature_set` diz o que é uma linha:

- `condominio` → uma linha por `referencia`; `entidade_id` repete a `referencia`
- `unidade` → uma linha por unidade; `entidade_id` é o identificador da unidade
  no sistema do parceiro (bloco/apartamento, matrícula, o que for estável)

`entidade_id` precisa ser **estável entre entregas**. Se mudar de competência
para competência, o histórico por entidade se perde e o modelo passa a ver
cada mês como uma entidade nova.

### Competência

`data_referencia` é a competência do dado, não a data de envio. Reenviar a
mesma competência substitui (há UNIQUE), não duplica.

## Conjuntos previstos

> ⚠️ **As listas abaixo são proposta, não contrato fechado.** Elas foram
> derivadas do domínio, não do modelo real. A lista definitiva de cada
> capacidade tem que vir do dono do modelo dentro da Lello — é a dependência
> externa nº 3 do plano da semana. Enquanto não vier, nada aqui deve ser
> enviado a parceiro.

### `churn_unidade` (proposta)

Granularidade: `unidade`. Alvo: risco de saída de condômino inadimplente.

| Coluna | Tipo | Obrigatório | O que é |
|---|---|---|---|
| `atraso_medio_dias` | number | sim | Média de dias de atraso em 12 meses |
| `qtde_atrasos_12m` | integer | sim | Quantos vencimentos pagos com atraso |
| `qtde_inadimplencias_abertas` | integer | sim | Cobranças em aberto hoje |
| `valor_em_aberto` | number | sim | Somatório em aberto, em reais |
| `meses_de_relacionamento` | integer | sim | Tempo desde o primeiro vínculo |
| `houve_acordo_12m` | boolean | não | Houve renegociação no período |
| `chamados_abertos_12m` | integer | não | Proxy de engajamento/atrito |

### `isc_condominio` (proposta)

Granularidade: `condominio`. Alvo: índice de saúde do condomínio.

| Coluna | Tipo | Obrigatório | O que é |
|---|---|---|---|
| `taxa_inadimplencia` | number | sim | Percentual da carteira em aberto |
| `saldo_caixa` | number | sim | Saldo em conta na competência |
| `saldo_fundo_reserva` | number | não | Fundo de reserva |
| `qtde_unidades` | integer | sim | Total de unidades |
| `despesa_media_mensal` | number | sim | Média de despesa em 12 meses |

## Como um tenant é onboardado

1. **Declarar o contrato** — cria linha em `feature_sets` com o `schema_json`
   da capacidade contratada.
2. **Mapear a origem** — o parceiro aponta de onde sai cada coluna no sistema
   dele. Divergência semântica aparece aqui, não depois.
3. **Carga histórica** — no mínimo 12 competências, senão não há série para
   calibrar.
4. **Calibração** — o modelo global é calibrado contra o histórico do tenant e
   a versão da calibração fica em `capability_scores.calibracao_versao`.
5. **Ligar a capacidade** — só depois disso o slug entra em
   `modulos_contratados`.

## Regras de isolamento

As quatro tabelas têm `tenant_id`, RLS e `FORCE ROW LEVEL SECURITY`. Vale a
mesma regra crítica do resto: **toda query inclui `tenant_id` no WHERE mesmo
com RLS ativa** (defesa em profundidade, `RULES.md`).

A zona de features é onde um vazamento cross-tenant seria mais caro do que em
qualquer outro lugar da plataforma: aqui o dado é financeiro e nominal, não
documento do condomínio.

## A Lello também passa por aqui

O tenant zero do piloto é a própria Lello, e o dado dela **não** entra por um
caminho interno privilegiado: entra pelo mesmo `feature_sets` +
`feature_values` que um parceiro usaria.

Isso é deliberado e custa um pouco de tempo agora. A alternativa — alimentar o
modelo direto da base da Lello porque é mais rápido — provaria um trilho que
só funciona em casa, e a descoberta viria no dia em que o primeiro parceiro
tentasse entrar, que é justamente a segunda metade do piloto.
