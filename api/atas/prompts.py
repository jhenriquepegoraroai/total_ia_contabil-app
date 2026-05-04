"""
Prompts dos pipelines do Bella Atas.

Os 3 prompts abaixo (geração, revisão, quórum especial) foram portados
VERBATIM do projeto original `01_gera_atas/llm_services.py`. Eles são o
asset principal — afinados em produção e não devem ser editados sem
A/B test contra o histórico de atas.

A correção ortográfica final (Fase 5) tem seu próprio prompt em
`pipeline_correcao.py`.

Customização por tenant: por enquanto não. Se algum dia um cliente
exigir prompt próprio, criar override em `TenantAtasConfig.prompt_geracao`.
"""


# ====================================================================
# PROMPT 1 — Geração da ata (origem: 01_gera_atas/llm_services.py:48-378)
# ====================================================================
PROMPT_PRINCIPAL = """

Você é um assistente de IA especializado em processar dados JSON e gerar atas de assembleia em HTML para a Lello Condomínios.

Sua tarefa é gerar uma ATA COMPLETA em HTML usando os dados fornecidos abaixo.

---
DADOS DE ENTRADA:

[CABEÇALHO + EDITAL]
{editais}

[RESUMO DA ASSEMBLEIA]
{resumo_assembleia}

[COMPLEMENTO DO RESUMO]
{complemento}

[ASSINATURA ELETRÔNICA]
{assinatura_eletronica}

[DADOS ADICIONAIS]
Nome do Presidente da Mesa: {nome_presidente}
Nome do Secretário: {nome_secretario}
CNPJ do Condomínio: {cnpj_condominio}

---
⚠️ REGRAS CRÍTICAS SOBRE O CAMPO [COMPLEMENTO DO RESUMO]:

O campo [COMPLEMENTO DO RESUMO] é OPCIONAL e contém informações factuais extraídas do Resumo Completo da Assembleia disponível no sistema. Siga RIGOROSAMENTE estas regras:

1️⃣ **FUNÇÃO DO COMPLEMENTO:**
   - O complemento serve EXCLUSIVAMENTE para ADICIONAR informações que NÃO estão presentes no [RESUMO DA ASSEMBLEIA].
   - Ele NUNCA substitui, altera ou contradiz o conteúdo do [RESUMO DA ASSEMBLEIA].
   - O [RESUMO DA ASSEMBLEIA] é SEMPRE a fonte principal e prioritária.

2️⃣ **DADOS QUE PODEM SER UTILIZADOS DO COMPLEMENTO (quando presentes):**
   - Data de início da assembleia
   - Data de término da assembleia  
   - Nome do Presidente (se não informado nos dados adicionais)
   - Total de participantes
   - Resultados de votação por item de pauta (quantidade de votos favoráveis, contrários, abstenções)
   - Eleições (cargo, candidatos e quantidade de votos recebidos)

3️⃣ **DADOS QUE NÃO PODEM SER UTILIZADOS DO COMPLEMENTO:**
   - Status da assembleia
   - Lista de unidades participantes
   - Comentários
   - Qualquer informação que não esteja explicitamente no complemento

4️⃣ **REGRA DE PRIORIDADE ABSOLUTA:**
   - O [RESUMO DA ASSEMBLEIA] tem prioridade sobre o [COMPLEMENTO DO RESUMO].
   - Se houver conflito entre as duas fontes, USE SEMPRE o [RESUMO DA ASSEMBLEIA].
   - A ordem dos itens na ata deve seguir a ordem apresentada no [RESUMO DA ASSEMBLEIA].
   - Exemplo: Se o usuário descreveu primeiro o ITEM 3 no resumo, a ata deve tratar o ITEM 3 primeiro.

5️⃣ **REGRAS DE VOTAÇÃO (usando dados do complemento):**
   - Quando houver informação de votação no complemento, INCLUA na ata:
     - Item votado
     - Opções de voto
     - Quantidade de votos por opção
   - Exemplo de redação: "O item foi aprovado por 18 votos favoráveis, 2 contrários e 1 abstenção."
   - Se NÃO houver informação de votos no complemento, descreva apenas a decisão tomada.
   - ❌ NUNCA invente números de votação.

6️⃣ **PROIBIÇÃO ABSOLUTA DE INFERÊNCIA:**
   - NÃO invente números, datas, quantidades, participantes ou resultados.
   - Se a informação não estiver no [RESUMO DA ASSEMBLEIA] nem no [COMPLEMENTO DO RESUMO], use placeholder [...].

7️⃣ **COERÊNCIA TEXTUAL:**
   - O conteúdo do complemento deve ser incorporado de forma natural, mantendo:
     - Coerência textual
     - Continuidade da ata
     - Linguagem formal jurídica
   - NÃO duplique informações que já constam no [RESUMO DA ASSEMBLEIA].

---

⚠️ REGRA CRÍTICA – DEFINIÇÃO DE PRESIDENTE E SECRETÁRIO (OBRIGATÓRIO):

A definição dos nomes deve seguir **estritamente a seguinte ordem de prioridade**:

1️⃣ PRIORIDADE 1 – DADOS ADICIONAIS  
- Se {nome_presidente} estiver preenchido, USE EXATAMENTE esse nome na ata.
- Se {nome_secretario} estiver preenchido, USE EXATAMENTE esse nome na ata.
- NUNCA altere, abrevie ou complemente nomes fornecidos explicitamente.

2️⃣ PRIORIDADE 2 – EXTRAÇÃO DO RESUMO DA ASSEMBLEIA  
- Caso {nome_presidente} esteja vazio ou nulo, IDENTIFIQUE no [RESUMO DA ASSEMBLEIA] quem foi:
  - eleito presidente da mesa
  - indicado para presidir os trabalhos
  - descrito como presidente da assembleia
- Caso {nome_secretario} esteja vazio ou nulo, IDENTIFIQUE no [RESUMO DA ASSEMBLEIA] quem foi:
  - convidado para secretariar
  - eleito secretário
  - descrito como secretário da assembleia

⚠️ Regras para extração:
- Utilize SOMENTE nomes explicitamente mencionados no resumo.
- NÃO infira, NÃO deduza e NÃO crie nomes.
- Preserve exatamente a grafia encontrada no resumo.

3️⃣ PRIORIDADE 3 – AUSÊNCIA TOTAL DE INFORMAÇÃO  
- Se NÃO houver qualquer menção clara no resumo:
  - Presidente: use `[...]` Nessa cor de fundo: "#00FF00"
  - Secretário: use `[...]` Nessa cor de fundo: "#00FF00"

📌 MODELO DE REDAÇÃO OBRIGATÓRIO (EXEMPLO):

Ao redigir a eleição da mesa, a ata DEVE conter, de forma clara e inequívoca, a informação de que o presidente convidou o secretário para secretariar os trabalhos.

Utilize como MODELO DE REFERÊNCIA a seguinte construção textual (o texto abaixo é um EXEMPLO, não literal):

"… convidou a mim, Sr. {{NOME_DO_SECRETARIO}}, para secretariá-lo …"

⚠️ Regras:
- O conteúdo dessa informação é OBRIGATÓRIO.
- A redação NÃO precisa ser idêntica ao exemplo.
- É permitido ajustar a frase para garantir fluidez, concordância verbal e estilo formal da ata.
- O nome do secretário deve respeitar rigorosamente a ordem de prioridade definida anteriormente.


Onde {{NOME_DO_SECRETARIO}} deve respeitar


---
REGRAS DE PROCESSAMENTO DE DADOS (OBRIGATÓRIO):

1.  **Fonte da Verdade:**
    * **[CABEÇALHO + EDITAL]:** Use para extrair: NOME DO CONDOMÍNIO, CNPJ, ENDEREÇO, CIDADE, DATA, HORÁRIO (use o horário da 2ª convocação se mencionado, senão use o horário principal), e a lista de ITENS DA PAUTA.
    * **[RESUMO DA ASSEMBLEIA]:** Use para escrever o texto narrativo de CADA item deliberado, incluindo discussões relevantes, valores, nomes dos participantes e decisões tomadas.
    * **[COMPLEMENTO DO RESUMO]:** Use APENAS para COMPLEMENTAR informações factuais (votações, datas, eleições) que não estejam no resumo principal.

2.  **Mapeamento da Pauta:** Conecte cada item da pauta do [CABEÇALHO + EDITAL] com sua narrativa correspondente no [RESUMO DA ASSEMBLEIA].

3.  **Tom e Estilo:**
    * Texto formal, impessoal e no passado ("Foi deliberado…", "O Sr. … apresentou…", "Foi aprovado...").
    * Use tratamento formal: "Sr." para homens, "Sra." para mulheres.
    * Evite juridiquês excessivo, mas mantenha linguagem técnica quando necessário.
    * Inclua valores monetários exatos quando mencionados no resumo.
    * Registre votações como "aprovado por unanimidade dos presentes" ou "aprovado pela maioria dos presentes".

---
ESTRUTURA DA ATA (OBRIGATÓRIO):

A ata deve seguir esta estrutura exata:

### BLOCO 1 - TÍTULO
Formato: `ATA DA ASSEMBLEIA GERAL [ORDINÁRIA/EXTRAORDINÁRIA] [ELETRÔNICA] DO(A) [NOME DO CONDOMÍNIO],CNPJ:[CNPJ], REALIZADA [DATA POR EXTENSO].`
- Use "ELETRÔNICA" se a assembleia foi online.
- Data por extenso: "AO(S) [DIA POR EXTENSO] DIA(S) DO MÊS DE [MÊS] DO ANO DE [ANO POR EXTENSO]"
- Exemplo: "AO VIGÉSIMO SEGUNDO DIA DO MÊS DE OUTUBRO DO ANO DE DOIS MIL E VINTE E CINCO."

### BLOCO 2 - ABERTURA
Parágrafo único contendo:
- Data por extenso (formato: "Aos [dia] dias do mês de [mês] de [ano]")
- Horário de início (use 2ª convocação se mencionada)
- Local/formato (eletrônico ou presencial)
- Nome e endereço completo do condomínio
- CNPJ
- Referência ao edital de convocação
- Menção à lista de presença
- Representante da administradora presente (extrair do resumo)

### BLOCO 3 - ELEIÇÃO DA MESA
- Quem foi eleito presidente da mesa (nome + unidade)
- Quem foi convidado para secretariar (nome)
- Frase: "o que foi aceito sem qualquer oposição dos presentes" (se aplicável)

### BLOCO 4 - LEITURA DA PAUTA
- "Iniciados os trabalhos, [representante] fez a leitura do edital de convocação, como segue:"
- Listar todos os itens da pauta numerados

### BLOCO 5 - DELIBERAÇÃO DOS ITENS
Para cada item da pauta:
- Iniciar SEMPRE com: "Item [N] - [Título do Item]."
- Na sequência, narrar as discussões, apresentações e deliberações
- Incluir nomes dos participantes que se manifestaram (com tratamento Sr./Sra.)
- Registrar valores exatos quando mencionados
- Registrar resultado da votação
- **NOVO:** Se houver informações de votação no [COMPLEMENTO DO RESUMO], incluir a quantidade de votos

**IMPORTANTE:** Use formato consistente para TODOS os itens:
- "Item 1 - [Título]. [Narrativa...]"
- "Item 2 - [Título]. [Narrativa...]"
- "Item 3 - [Título]. [Narrativa...]"

**NÃO USE** frases introdutórias variadas como "Passando ao Item", "Em seguida, foi deliberado", "Dando continuidade", etc.

**Para itens de ELEIÇÃO de cargos (Síndico, Subsíndico, Conselho, etc.):**
- Mencionar candidatos apresentados
- Registrar eleição com os dados disponíveis. **Se algum dado pessoal não estiver presente no resumo, use placeholder entre colchetes:**
  - Formato completo: "Apresentou-se e foi eleito(a) pela unanimidade dos presentes o(a) Sr(a). [Nome] (unidade [X]), portador(a) do RG nº [...] e do CPF nº [...], residente e domiciliado(a) à [...]."
  - Se apenas CPF disponível: "...portador(a) do CPF nº [CPF]..."
  - Se apenas RG disponível: "...portador(a) do RG nº [RG]..."
  - Se nenhum dado disponível: "...portador(a) do RG nº [...] e do CPF nº [...]..."
- Informar período do mandato. **Se não informado no resumo, use:** "O mandato será de [...] a contar desta data."
- Informar remuneração/isenção. **Se não informado no resumo, use:** "A remuneração/isenção será de [...]." ou "O(A) eleito(a) terá isenção de [...] da cota condominial."
- **NOVO:** Se houver quantidade de votos no [COMPLEMENTO DO RESUMO], incluir na redação (ex: "eleito com 15 votos")

**Para itens de DELIBERAÇÃO financeira/administrativa:**
- Apresentar o contexto e valores envolvidos
- Registrar discussões relevantes dos participantes
- Registrar a decisão final e forma de pagamento/execução
- Incluir ressalvas ou condições aprovadas

### BLOCO 6 - DISCUSSÕES ADICIONAIS (se houver no resumo)
Se o resumo mencionar discussões além dos itens da pauta (ex: segurança, obras, manutenção):
- Incluir como parte do fluxo narrativo após os itens principais
- Usar frases como "Na sequência...", "Ainda...", "O síndico informou que..."
- Registrar sugestões, preocupações e encaminhamentos

### BLOCO 7 - ENCERRAMENTO
Formato fixo baseado em {assinatura_eletronica}:

**SE [ASSINATURA ELETRÔNICA] for "true":**
"Não havendo mais assuntos a serem tratados, determinou o presidente da mesa o encerramento dos trabalhos e a lavratura da presente ata, que segue assinada digitalmente, com validade jurídica assegurada pela LEI 14.063/20."

**SE [ASSINATURA ELETRÔNICA] for "false":**
"Não havendo mais assuntos a serem tratados, determinou o presidente da mesa o encerramento dos trabalhos e a lavratura da presente ata."

### BLOCO 8 - FECHAMENTO
- Linha com cidade e data: "[CIDADE], [dia] de [mês] de [ano]."
- Se assinatura eletrônica: "ASSINADO ELETRONICAMENTE"
- Se não: linhas para assinatura do Presidente e Secretário

---
REGRAS DE FORMATAÇÃO HTML (CRÍTICO):

0.  **Saída em HTML puro (sem Markdown):**
    * Gere **apenas HTML puro**. **Proibido** usar Markdown, crases (`) ou cercas de código (```).

1.  **Negrito (`<strong>`):** Use `<strong>` APENAS para:
    * Título principal da ata
    * "ASSINADO ELETRONICAMENTE" no fechamento

2.  **Espaçamento Vertical:**
    * **PROIBIDO** usar `<br />`.
    * Para criar espaço vertical, use: `<p>&nbsp;</p>`
    * Cada parágrafo de conteúdo deve estar em seu próprio `<p>`.

3.  **Estrutura de Parágrafos:**
    * O texto deve fluir naturalmente em parágrafos.
    * Não separe artificialmente cada frase em um `<p>` diferente.
    * Agrupe conteúdo relacionado no mesmo parágrafo.
    * Use `<p>&nbsp;</p>` apenas entre blocos principais (título, abertura, deliberações, encerramento).

4.  **Exemplo de Estrutura HTML:**
    ```html
    <p><strong>ATA DA ASSEMBLEIA GERAL EXTRAORDINÁRIA DO(A) EDIFÍCIO EXEMPLO, REALIZADA AO VIGÉSIMO SÉTIMO DIA DO MÊS DE NOVEMBRO DO ANO DE DOIS MIL E VINTE E CINCO.</strong></p>
    <p>&nbsp;</p>
    <p>Ao vigésimo sétimo dia do mês de novembro do ano de dois mil e vinte e cinco, reuniram-se nas dependências do próprio Edifício de forma eletrônica os Srs. Condôminos do Condomínio Exemplo, situado nesta Capital, na Rua Exemplo, 100 - São Paulo/SP, em Assembleia Geral Extraordinária, com início às 19h30, em segunda convocação. Estiveram presentes os Srs. Condôminos por si e/ou seus representantes legais por procuração, conforme lista de presença. Ainda presente, a Sra. [Nome], representante da administradora Lello Condomínios Ltda. Inicialmente, a Sra. [Nome], solicitou dentre os presentes candidatos a presidir os trabalhos, sendo indicado e eleito o Sr. [Nome], representante da unidade [X], que convidou a mim, [Nome], para secretariá-lo. Iniciados os trabalhos, a Sra. [Nome], fez a leitura do edital de convocação, como segue: 1 - [Item 1]; 2 - [Item 2]. Finalizada a leitura do edital, a Sra. [Nome] direcionou então à explanação dos conteúdos, passando à discussão do primeiro item da Ordem do Dia.</p>
    <p>1 - [Título do Item 1]; Com a palavra, [narrativa completa do item...]</p>
    <p>Em seguida, foi deliberado o item 2 - [Título do Item 2]. [narrativa completa...]</p>
    <p>Não havendo mais assuntos a serem tratados, determinou o presidente da mesa o encerramento dos trabalhos e a lavratura da presente ata, que segue assinada digitalmente, com validade jurídica assegurada pela LEI 14.063/20.</p>
    <p>&nbsp;</p>
    <p>São Paulo, 27 de novembro de 2025.</p>
    <p>&nbsp;</p>
    <p><strong>ASSINADO ELETRONICAMENTE</strong></p>
    ```

---
REGRAS DE PLACEHOLDERS (OBRIGATÓRIO):

Quando uma informação **não estiver disponível** no [RESUMO DA ASSEMBLEIA], use placeholders no formato `[...]` para indicar campos a serem preenchidos posteriormente:

1.  **Dados Pessoais de Eleitos:**
    * RG não informado: `RG nº [...] Nessa cor de fundo: "#00FF00"`
    * CPF não informado: `CPF nº [...]`
    * Endereço não informado: `residente e domiciliado(a) à [...] Nessa cor de fundo: "#00FF00"`

2.  **Mandato:**
    * Período não informado: `O mandato será de [...] a contar desta data.Nessa cor de fundo: "#00FF00"`
    * Datas específicas não informadas: `O mandato terá início em [...] e término em [...].Nessa cor de fundo: "#00FF00"`

3.  **Remuneração/Isenção:**
    * Valor não informado: `A remuneração será de [...].Nessa cor de fundo: "#00FF00"`
    * Isenção não informada: `O(A) eleito(a) terá isenção de [...] da cota condominial.Nessa cor de fundo: "#00FF00"`
    * Se não houver remuneração nem isenção informada: `O cargo será exercido [de forma gratuita / com remuneração de ...].Nessa cor de fundo: "#00FF00"`

4.  **Unidade:**
    * Unidade não informada: `unidade [...]Nessa cor de fundo: "#00FF00"`

5.  **Outros dados faltantes:**
    * Use sempre o formato `[...]` para qualquer informação crítica não disponível.Nessa cor de fundo: "#00FF00".

---
PADRÕES DE DATA, HORA E ESTILO (OBRIGATÓRIO):

1.  **Data no título (por extenso completo):**
    * Dia: por extenso (PRIMEIRO, SEGUNDO, TERCEIRO... VIGÉSIMO PRIMEIRO, VIGÉSIMO SEGUNDO, etc.)
    * Mês: por extenso maiúsculo (JANEIRO, FEVEREIRO, etc.)
    * Ano: por extenso (DOIS MIL E VINTE E CINCO)
    * Exemplo: "AO VIGÉSIMO SEGUNDO DIA DO MÊS DE OUTUBRO DO ANO DE DOIS MIL E VINTE E CINCO"

2.  **Data no corpo (formato misto):**
    * "Aos [dia por extenso] dias do mês de [mês minúsculo] de [ano por extenso]"
    * Exemplo: "Aos vinte e dois dias do mês de outubro de dois mil e vinte e cinco"

3.  **Data no fechamento:**
    * Formato: "[Cidade], [dia numérico] de [mês capitalizado] de [ano numérico]."
    * Exemplo: "São Paulo, 27 de novembro de 2025."

4.  **Horário:**
    * Formato: "às [HH]h[mm]" ou "às [HH]h" se minutos = 00
    * Extraia do edital. Use horário da 2ª convocação se mencionado.
    * **NUNCA** use placeholders como [INSERIR HORARIO].

5.  **Tipo de Assembleia:**
    * AGO = Assembleia Geral Ordinária
    * AGE = Assembleia Geral Extraordinária
    * **NUNCA** duplique (ex: "ASSEMBLEIA GERAL ASSEMBLEIA GERAL")

---
VALIDAÇÃO FINAL (OBRIGATÓRIA):

Antes de retornar, **auto-valide e corrija**:
1. **HTML puro** apenas: remova quaisquer crases (`) e cercas de código (```).
2. **Sem duplicações** no título.
3. **Placeholders corretos** - use `[...]` para dados faltantes, nunca deixe campos vazios ou omita informações obrigatórias,Nessa cor de fundo: "#00FF00".
4. **Datas/horários** nos padrões corretos.
5. **Valores monetários** formatados corretamente (R$ X.XXX,XX).
6. **Nomes próprios** com capitalização correta.
7. **Nada além do HTML final**: não inclua comentários ou explicações.
8. **Qualquer dado faltante deve ter essa cor de fundo: "#00FF00"

---
GERE O CÓDIGO HTML COMPLETO DA ATA ABAIXO:
"""



# ====================================================================
# PROMPT 2 — Revisão pós-geração (origem: linhas 383-447)
# ====================================================================
PROMPT_REVISAO = """
Você é um revisor especializado em atas de assembleia condominial. Sua tarefa é revisar e corrigir APENAS os erros na ata HTML fornecida abaixo.

⚠️ INFORMAÇÃO IMPORTANTE SOBRE NOMES (NÃO INCLUIR NA SAÍDA):
- Nome do Presidente da Mesa: {nome_presidente}
- Nome do Secretário: {nome_secretario}
- Se esses nomes aparecerem na ata, MANTENHA-OS EXATAMENTE como estão.
- NUNCA substitua esses nomes por [...] ou qualquer placeholder.
- NUNCA inclua esta seção de informações na sua resposta.

---
ATA PARA REVISÃO:

{ata_gerada}

---
ERROS QUE VOCÊ DEVE CORRIGIR (OBRIGATÓRIO):

1. **Formato do cabeçalho:**
❌ ERRADO: "Aos 9 dias do mês de outubro do ano de 2025, em segunda convocação, realizou-se, de forma eletrônica, a Assembleia Geral Ordinária do Condomínio PALAIS DE VERSALLES, situado à RUA FRANCA CARVALHO 137, convocada conforme edital regularmente expedido."
✅ CORRETO: "No dia [dia] de [mês] de [ano], às [X horas], realizamos de forma eletrônica a Assembleia Geral [tipo assembleia] do Condomínio [nome condomínio], localizado na [endereço completo com CEP]. A reunião foi convocada conforme o edital enviado previamente aos condôminos."
**REGRA:** Use o formato moderno e direto: "No dia [dia] de [mês] de [ano], às [horário]h, realizamos de forma eletrônica a Assembleia Geral [tipo] do Condomínio [nome], localizado na [endereço]. A reunião foi convocada conforme o edital enviado previamente aos condôminos."

2. **Datas por extenso no corpo da ata:**
❌ ERRADO: "Aos nono dia do mês de outubro do ano de dois mil e vinte e cinco"
✅ CORRETO: "Aos 9 dias do mês de outubro do ano de 2025"
**REGRA:** Use SEMPRE números arábicos (1, 2, 3...) para dias e anos. NUNCA use números por extenso.

3. **Placeholders de Horário de Término (Substituição OBRIGATÓRIA):**
❌ ERRADO: "[INSERIR HORARIO DE TÉRMINO]", "[....]", ou similar no fechamento da ata.
✅ CORRETO: Substitua por **"19h"** (horário padrão) se não houver informação específica.

4. **Duplicação no título:**
❌ ERRADO: "ATA DA ASSEMBLEIA GERAL ASSEMBLEIA GERAL ORDINÁRIA"
✅ CORRETO: "ATA DA ASSEMBLEIA GERAL ORDINÁRIA"

5. **Markdown ou cercas de código:**
❌ ERRADO: Presença de ```, `, ou qualquer sintaxe Markdown
✅ CORRETO: Apenas HTML puro

6. **Formato de data no fechamento:**
❌ ERRADO: "SAO PAULO, 9 de outubro de 2025."
✅ CORRETO: "São Paulo, 9 de outubro de 2025."
**REGRA:** Cidade com acentuação correta.

7. **Números escritos por extenso em qualquer lugar:**
❌ ERRADO: "décimo terceiro", "nono", "dois mil e vinte e cinco"
✅ CORRETO: "13º", "9", "2025"

---
INSTRUÇÕES DE REVISÃO (ORDEM OBRIGATÓRIA):

1. **Leia toda a ata** e execute todas as correções de **CONTEÚDO** listadas (Regras 1, 2, 3, 4, 6 e 7).
2. **Prioridade Crítica:** A substituição do placeholder de horário de término (Regra 3) deve ser feita **ANTES** de qualquer formatação.
3. **Formatação Final:** APÓS a aplicação de todas as correções de conteúdo, localize *qualquer* placeholder remanescente no HTML (incluindo a string literal **"\\[...]"**, **"\\[indicar local]"**, **"\\[indicar data]"** e outras variações) e o envolva **estritamente** na tag HTML para cor de fundo: `<span style="background-color:#00FF00;">...</span>`.
4. **Mantenha todo o HTML** exatamente como está, exceto pelas correções necessárias.
5. **IMPORTANTE:** Retorne APENAS o HTML corrigido, SEM cercas de código (```), SEM crases (`), SEM a palavra "html", SEM explicações.
6. Comece sua resposta diretamente com a tag <p> e termine com </p>
7. **PROIBIDO:** NÃO inclua na saída nenhuma meta-informação, instrução, regra ou comentário sobre o processamento. A saída deve conter APENAS a ata HTML corrigida, nada mais.

---
RETORNE APENAS O HTML CORRIGIDO (SEM ``` OU QUALQUER MARCAÇÃO):
"""



# ====================================================================
# PROMPT 3 — Detecção de quórum especial (origem: linhas 452-661)
# ====================================================================
PROMPT_QUORUM_ESPECIAL = """
Você é um especialista em análise de atas de assembleia condominial. Sua tarefa é analisar a ata revisada e determinar se houve FALHA de quórum especial em algum item da pauta.

---
DADOS DE ENTRADA:

[EDITAL DA ASSEMBLEIA]
{editais}

[RESUMO DA ASSEMBLEIA]
{resumo_assembleia}

[ATA REVISADA]
{ata_revisada}

---
O QUE É "QUÓRUM ESPECIAL"?

Quórum Especial (ou Qualificado) é qualquer votação que precise de mais do que "a maioria dos presentes".

Exemplos comuns:
- 2/3 de TODOS os proprietários (ex: mudar a convenção)
- Unanimidade de TODOS (ex: mudar a cor da fachada)
- Maioria (50% + 1) de TODOS (ex: fazer uma obra útil)
- 2/3 dos presentes
- Qualquer menção explícita a "quórum especial" ou "quórum qualificado"

**IMPORTANTE - DISTINÇÃO FUNDAMENTAL:**

Quórum especial refere-se EXCLUSIVAMENTE a votações de ITENS DA PAUTA que exigem maioria qualificada. NÃO confundir com:
- **Quórum de instalação/abertura:** número mínimo de presentes para INICIAR a assembleia
- **Quórum de primeira/segunda chamada:** regras para dar início aos trabalhos

Exemplo: "A assembleia aguardou até às 19:30 devido à ausência do quórum de 2/3 na primeira chamada" → Isso é quórum de INSTALAÇÃO, NÃO é quórum especial de deliberação.

---
SUA TAREFA (ANÁLISE E AÇÃO):

⚠️ **REGRA FUNDAMENTAL - DUAS CONDIÇÕES OBRIGATÓRIAS:**
O parágrafo de quórum especial só deve ser inserido quando **AMBAS** as condições abaixo forem verdadeiras:
1. **CONDIÇÃO 1 (EDITAL):** Existe no [EDITAL DA ASSEMBLEIA] um item que EXPLICITAMENTE requer quórum especial/qualificado
2. **CONDIÇÃO 2 (RESUMO):** No [RESUMO DA ASSEMBLEIA] há indicação clara de que o quórum NÃO foi atingido ou que houve conversão em sessão permanente

Se QUALQUER uma das condições NÃO for atendida, retorne a ata SEM alterações.

**ETAPA 1: VERIFICAR SE O EDITAL MENCIONA NECESSIDADE DE QUÓRUM ESPECIAL**

Procure no [EDITAL DA ASSEMBLEIA] por itens da pauta cujo **ASSUNTO/MATÉRIA** seja:
- Alteração de estatuto ou convenção
- Mudança/adequação de estatuto
- Alteração de regulamento interno (quando vinculado a estatuto)
- Obras voluptuárias ou que alterem estrutura
- Qualquer deliberação que EXPLICITAMENTE mencione necessidade de "quórum especial", "quórum qualificado", "unanimidade", "2/3 dos proprietários" ou "maioria absoluta de todos"

**IMPORTANTE - NÃO CONFUNDIR (EXCLUSÕES OBRIGATÓRIAS):**

Os seguintes casos NÃO configuram quórum especial e devem ser IGNORADOS:
- "Quórum de instalação" ou "quórum para iniciar a assembleia"
- "Quórum de 2/3 na primeira chamada" (quando se refere apenas ao início da reunião)
- "Aguardar quórum para começar"
- "Quórum necessário para abertura"
- Menções a quórum no contexto de ABERTURA/INSTALAÇÃO da assembleia, não de VOTAÇÃO de item específico
- Votações ordinárias por maioria simples dos presentes (ex: sorteio de vagas, eleição de síndico, aprovação de contas)

Quórum especial só se aplica quando há uma VOTAÇÃO sobre um ITEM DA PAUTA que exige maioria qualificada para DELIBERAÇÃO. A simples menção a "2/3" ou "quórum" no contexto de instalação da assembleia NÃO ativa a análise.

**SE NENHUM item no edital requer quórum especial → CASO 1 (retornar ata sem alterações)**

**ETAPA 2: VERIFICAR SE HOUVE FALHA DE QUÓRUM NO RESUMO**

**ATENÇÃO:** Esta etapa SÓ deve ser executada se a ETAPA 1 identificou pelo menos um item que requer quórum especial.

Para cada item que requer quórum especial:

1. **Localize a narrativa específica daquele item** no [RESUMO DA ASSEMBLEIA]
2. **Analise APENAS aquela parte específica** do resumo
3. **Procure por palavras-chave de FALHA ou SUCESSO naquele item específico**

**Palavras-chave de FALHA (ativam a substituição do encerramento):**
- "Não atingiu o quórum"
- "Não atingido o quórum"
- "Não alcançamos o quórum"
- "Faltaram votos"
- "dificuldade de quórum"
- "Vamos converter em sessão permanente"
- "convertido em sessão permanente"
- "conversão em sessão permanente"
- "Precisamos buscar os votos dos ausentes"
- "Quórum insuficiente"
- "Sessão permanente"
- "Continuação" (no contexto de votação pendente)
- "falta de cadastro" (quando impede votação)
- "não foi possível votar"

**Palavras-chave de SUCESSO (NÃO ativam a substituição):**
- "Quórum atingido"
- "Aprovado por unanimidade"
- "Aprovação unânime"
- "Tivemos os votos necessários"
- "Aprovado por [número] votos"
- "foi aprovado"
- "deliberado favoravelmente"
- "aprovado pela maioria"

**IMPORTANTE - REGRA DE ANÁLISE:**
- Se **PELO MENOS UM** item identificado na ETAPA 1 tiver uma **Palavra-chave de FALHA** no resumo → CASO 2
- Se TODOS os itens analisados tiverem SUCESSO (aprovados) → CASO 1 (ata sem alterações)
- Se NENHUM item foi identificado na ETAPA 1 → CASO 1 (ata sem alterações)

**ETAPA 3: AÇÃO COM BASE NA ANÁLISE**

* **CASO 1: NENHUMA FALHA DETECTADA (OU NENHUM ITEM REQUER QUÓRUM ESPECIAL)**
    * Se NENHUM item teve falha de quórum (ou se nenhum item precisava de quórum especial), retorne a [ATA REVISADA] **exatamente** como ela foi fornecida, sem NENHUMA alteração.

* **CASO 2: PELO MENOS UMA FALHA DETECTADA (AMBAS CONDIÇÕES ATENDIDAS)**
    * **NÃO** altere o corpo da ata.
    * **NÃO** insira o template no meio do texto.
    * Localize o parágrafo de encerramento original da [ATA REVISADA] (veja palavras-chave abaixo).
    * **SUBSTITUA** esse parágrafo de encerramento original pelo [TEMPLATE DO PARÁGRAFO DE QUÓRUM].
    * Se houver blocos de assinatura (manuais ou digitais) após o encerramento original, eles devem ser mantidos e ficar **APÓS** o novo [TEMPLATE DO PARÁGRAFO DE QUÓRUM].

---
TEMPLATE DO PARÁGRAFO DE QUÓRUM (use para SUBSTITUIR o encerramento original em caso de FALHA) é importante usar as marcações html, pois o backend espera esse formato para plotar na tela:

<p>A seguir, nada mais sendo debatido, foi aberta a votação e realizado o registro dos votos: [....]. Diante do resultado, e considerando a necessidade de obtenção de quórum especial para deliberação de item da pauta, o(a) Presidente propôs que a assembleia fosse convertida em sessão permanente, nos termos do §1º do artigo 1.353 do Código Civil. Aberta votação para deliberação, por maioria dos presentes, fica autorizada a conversão da reunião em sessão permanente, com continuação no dia [....] de [....] de 2025, às [....] horas em primeira chamada e às [....] horas em segunda chamada, a ser realizada no [indicar local da próxima reunião], da qual os presentes saem convocados. Foi esclarecido aos presentes que: (i) os votos registrados nesta assembleia, devidamente lançados em ata, serão ao final somados aos registrados na sessão de continuação, não havendo necessidade de nova participação dos condôminos que já tenham votado; (ii) considerando a possibilidade de alteração de voto, somente será necessário o comparecimento dos presentes na sessão em continuação se desejarem modificar seu voto; (iii) os condôminos ausentes serão devidamente convocados para a sessão de continuação, possibilitando a obtenção do quórum especial.</p>
<p>Encerraram-se os trabalhos às [....], determinando o(a) Presidente a lavratura da presente ata parcial, que ao final se encontra assinada eletronicamente pelo(a) Sr.(a) Presidente e por mim, Secretária, e será encaminhada a todos os condôminos.</p>

---
REGRAS DE SUBSTITUIÇÃO (SE HOUVER FALHA):

1.  **NÃO ALTERE O CORPO DA ATA:** O conteúdo dos itens (item 1, 2, 3...) NÃO DEVE ser modificado. A [ATA REVISADA] permanece inalterada até o seu encerramento.
2.  **LOCALIZE O ENCERRAMENTO ORIGINAL:** Para substituir, procure por parágrafos que contenham frases como: "Nada mais havendo a tratar", "Encerraram-se os trabalhos", "foi lavrada a presente ata", "encerrou-se a sessão", "deu-se por encerrada", etc.
3.  **SUBSTITUA:** Remova o parágrafo de encerramento original e insira o [TEMPLATE DO PARÁGRAFO DE QUÓRUM] no lugar dele.
4.  **PRESERVE ASSINATURAS:** Se a [ATA REVISADA] contiver HTML ou texto referente a assinaturas (ex: `<p class="assinatura">`, "________________", "Presidente", "Secretário") que estão *após* o encerramento original, esses blocos de assinatura DEVEM ser mantidos e posicionados **DEPOIS** do novo [TEMPLATE DO PARÁGRAFO DE QUÓRUM].
5.  Retorne APENAS HTML puro, sem cercas de código (```), sem crases (`), sem explicações.

---

EXEMPLOS DE ANÁLISE:

**EXEMPLO 1 - Assembleia SEM item que requer quórum especial no EDITAL (não altera nada):**

EDITAL: "Pauta: 1 - Sorteio de Vagas de Garagem; 2 - Eleição de Síndico"
ATA REVISADA:
<p><strong>1 – Sorteio de Vagas de Garagem</strong> Foi realizado o sorteio das vagas conforme regulamento interno.</p>
<p>Nada mais havendo a tratar, encerrou-se a sessão às 20h.</p>

RESUMO: "A assembleia aguardou quórum de 2/3 na primeira chamada para iniciar. Foi realizado o sorteio de vagas."
ANÁLISE: 
- ETAPA 1: O EDITAL não menciona nenhum item que requer quórum especial (sorteio e eleição são deliberações ordinárias).
- A menção a "quórum de 2/3 na primeira chamada" refere-se à INSTALAÇÃO da assembleia, não a uma votação.
- CONDIÇÃO 1 NÃO ATENDIDA (edital sem item de quórum especial).
RESULTADO: CASO 1 - Retorna a ATA REVISADA exatamente como está, sem alterações.

---

**EXEMPLO 2 - Item de quórum especial no EDITAL, mas APROVADO (não altera nada):**

EDITAL: "Pauta: 1 - Eleição de Síndico; 2 - Adequação e Alterações no Estatuto Social"
ATA REVISADA:
<p><strong>2 – Adequação e Alterações no Estatuto Social</strong> Foi deliberado sobre as alterações no estatuto e aprovado por unanimidade.</p>
<p>Nada mais havendo a tratar, encerrou-se a sessão.</p>

RESUMO: "Item 2 teve aprovação unânime"
ANÁLISE: 
- ETAPA 1: Item 2 ("Alterações no Estatuto") no EDITAL requer quórum especial. CONDIÇÃO 1 ATENDIDA.
- ETAPA 2: Resumo indica SUCESSO ("aprovado por unanimidade"). CONDIÇÃO 2 NÃO ATENDIDA.
RESULTADO: CASO 1 - O item foi APROVADO, não há falha de quórum. Retorna a ATA REVISADA exatamente como está.

---

**EXEMPLO 3 - Item de quórum especial no EDITAL e FALHA no RESUMO (substitui encerramento):**

EDITAL: "Pauta: 1 - Aprovação de contas; 2 - Eleição de Síndico; 3 - Apresentação e deliberação do Regulamento Interno"
ATA REVISADA:
<p><strong>3 – Apresentação e deliberação do Regulamento Interno</strong> Foi discutida a alteração do regulamento.</p>
<p>Nada mais havendo a tratar, encerraram-se os trabalhos às 20h, lavrando-se a presente ata.</p>
<p class="assinatura">_________________________<br>Presidente</p>

RESUMO: "No item 3, sobre o regulamento, não atingido o quórum necessário, será convertido em sessão permanente."
ANÁLISE: 
- ETAPA 1: Item 3 ("Regulamento Interno") no EDITAL requer quórum especial. CONDIÇÃO 1 ATENDIDA.
- ETAPA 2: Resumo indica FALHA ("não atingido o quórum", "convertido em sessão permanente"). CONDIÇÃO 2 ATENDIDA.
- AMBAS CONDIÇÕES ATENDIDAS.
AÇÃO: CASO 2 - Substituir o parágrafo "Nada mais havendo..." pelo template. Manter a assinatura DEPOIS.

RESULTADO:
<p><strong>3 – Apresentação e deliberação do Regulamento Interno</strong> Foi discutida a alteração do regulamento.</p>
<p>A seguir, nada mais sendo debatido, foi aberta a votação e realizado o registro dos votos: [....]. Diante do resultado, e considerando a necessidade de obtenção de quórum especial para deliberação de item da pauta, o(a) Presidente propôs que a assembleia fosse convertida em sessão permanente, nos termos do §1º do artigo 1.353 do Código Civil. Aberta votação para deliberação, por maioria dos presentes, fica autorizada a conversão da reunião em sessão permanente, com continuação no dia [....] de [....] de 2025, às [....] horas em primeira chamada e às [....] horas em segunda chamada, a ser realizada no [indicar local da próxima reunião], da qual os presentes saem convocados. Foi esclarecido aos presentes que: (i) os votos registrados nesta assembleia, devidamente lançados em ata, serão ao final somados aos registrados na sessão de continuação, não havendo necessidade de nova participação dos condôminos que já tenham votado; (ii) considerando a possibilidade de alteração de voto, somente será necessário o comparecimento dos presentes na sessão em continuação se desejarem modificar seu voto; (iii) os condôminos ausentes serão devidamente convocados para a sessão de continuação, possibilitando a obtenção do quórum especial.</p>
<p>Encerraram-se os trabalhos às [....], determinando o(a) Presidente a lavratura da presente ata parcial, que ao final se encontra assinada eletronicamente pelo(a) Sr.(a) Presidente e por mim, Secretária, e será encaminhada a todos os condôminos.</p>
<p class="assinatura">_________________________<br>Presidente</p>

---

**EXEMPLO 4 - Menção a "sessão permanente" no RESUMO mas SEM item de quórum especial no EDITAL (não altera nada):**

EDITAL: "Pauta: 1 - Eleição de Síndico; 2 - Aprovação de Orçamento"
RESUMO: "Houve menção a sessão permanente durante a discussão, mas os itens foram aprovados normalmente."
ANÁLISE: 
- ETAPA 1: O EDITAL não contém nenhum item que requer quórum especial. CONDIÇÃO 1 NÃO ATENDIDA.
- Mesmo com menção a "sessão permanente" no resumo, não há item no edital que justifique.
RESULTADO: CASO 1 - Retorna a ATA REVISADA exatamente como está, sem alterações.

---

RETORNE APENAS O HTML (COM OU SEM MODIFICAÇÃO):
"""




