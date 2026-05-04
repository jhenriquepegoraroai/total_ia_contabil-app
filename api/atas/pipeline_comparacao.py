"""
Pipeline de comparação entre duas versões de ata (sem LLM).

Algoritmo (portado de `02_compara_atas` na Fase 4):
    - Extrai blocos textuais de elementos `<p>, <li>, <h*>, <td>, <th>`
    - Alinha blocos via `difflib.SequenceMatcher` (ratio > 0.3)
    - Diff token-a-token nos blocos similares
    - Saída: HTML com spans coloridos (vermelho=removido, azul=adicionado)
    - Estatísticas: % alteração, contagens

Stateless. Cria linha em `atas_versoes` (tipo='comparacao') com o HTML
do diff em `conteudo_html` e estatísticas em `metadata_json`.
"""
