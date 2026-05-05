"""
Prompts do Bella Cobranças — extração de dados de relatórios condominiais
via GPT-4o (a partir do output do Document AI).

Conteúdo idêntico ao do projeto Decob original — esses prompts foram
calibrados manualmente sobre PDFs reais e reproduzem 1:1 o comportamento
de extração da versão standalone.
"""

EXTRACTION_PROMPT = """
Você é um especialista em extração de dados de documentos financeiros de condomínios.

## TAREFA
Extraia ABSOLUTAMENTE TODOS os registros de cobrança do documento e preencha o schema JSON fornecido.

## REGRAS CRÍTICAS - LEIA COM ATENÇÃO

### 1. ESTRUTURA DO DOCUMENTO
O documento segue esta hierarquia:
- **CONDOMÍNIO** (cabeçalho geral)
  - **UNIDADE/BLOCO** (cada condômino)
    - **RECIBO** (cada boleto, identificado por número único)
      - **LINHAS DE COBRANÇA** (cada item cobrado: condomínio, fundo reserva, 13º, etc.)

### 2. PROPAGAÇÃO DE DADOS
Quando uma linha NÃO repete um valor, HERDE do registro anterior:
- Se a linha não tem número de recibo → use o recibo da linha anterior
- Se a linha não tem vencimento → use o vencimento da linha anterior
- Se a linha não tem emissão → use a emissão da linha anterior
- O CONDOMÍNIO e UNIDADE se aplicam a todas as linhas até aparecer outro

### 3. CADA LINHA = UM REGISTRO
Crie UM REGISTRO SEPARADO para CADA linha de cobrança, mesmo que pertençam ao mesmo recibo.

### 4. SITUAÇÃO - REGRA ESPECIAL
A SITUAÇÃO é determinada pela UNIDADE, não pelo recibo individual:
- Verifique se a unidade aparece na seção "Tipo do processo: Jurídico" → TODAS as cobranças dessa unidade são "JURIDICO"
- Verifique a legenda: (J) = Jurídico, (P) = Protesto, (A) = Acordo, (AE) = Acordo Extrajudicial, (AJ) = Acordo Judicial
- Se a unidade está listada como "Jurídico" com valor total, TODOS os recibos dessa unidade são JURIDICO
- Se não houver indicação → "NORMAL"

### 5. NÃO PULE NENHUMA LINHA
Extraia TODAS as linhas: condomínio mensal, fundo de reserva, 13º salário, taxas extras,
obras/melhorias, multas e juros, qualquer item listado.

### 6. CAMPOS

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| CONDOMINIO | Código + Nome completo | "0287 CONDOMINIO EDIFICIO DOWN-TOWN" |
| UNIDADE | Número da unidade | "000034" |
| PRIMEIRO_VENCTO | Data DD/MM/YYYY | "01/06/2025" |
| MULTA | Valor de multa (null se não houver) | null |
| EMISSAO | Código de emissão | "320911" |
| NR_DO_RECIBO | Número do recibo/boleto | "2996205" |
| REGISTRO_EMISSAO | Registro de emissão (null se não houver) | null |
| SITUACAO | NORMAL, JURIDICO, PROTESTO, ACORDO | "JURIDICO" |
| CONTA | Código da conta contábil | "22" |
| HISTORICO | Descrição EXATA como no documento | "CONDOMÍNIO JUNHO/2025" |
| VALOR_ORIGINAL | Valor numérico (float) | 789.0 |

### 7. HISTÓRICO - COPIE EXATAMENTE
Copie o histórico EXATAMENTE como aparece no documento (mantenha mês/ano, parcelas, datas).

## SCHEMA ALVO
{schema}

## DADOS DO DOCUMENTO

### Texto Completo:
{full_text}

### Tabelas Extraídas:
{tables_text}

### Campos de Formulário:
{form_fields}

## OUTPUT
Retorne APENAS o JSON preenchido, sem markdown ou explicações.
"""
