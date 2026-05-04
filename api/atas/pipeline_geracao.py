"""
Pipeline de geração de ata via LLM (3 passos).

Fluxo planejado (Fase 3):
    1. PROMPT_GERACAO: texto da reunião + cabeçalho + edital → ata HTML inicial
    2. PROMPT_REVISAO: corrige inconsistências, datas, placeholders
    3. PROMPT_QUORUM: detecta falhas de quórum especial e insere parágrafo

Saída final: HTML estruturado em 8 blocos (título, abertura, eleição da mesa,
pauta, deliberações, discussões adicionais, encerramento, fechamento).

Persistência: cria nova linha em `atas_versoes` (tipo='gerada') e atualiza
`atas.versao_atual_id` + `atas.status='gerada'`.

Implementação portada de `01_gera_atas` na Fase 3.
"""
