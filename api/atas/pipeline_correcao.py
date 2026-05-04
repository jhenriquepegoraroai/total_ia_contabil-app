"""
Pipeline de correção ortográfica final da ata (Fase 5).

Lógica de dois caminhos (portado de `03_corrige_atas`):
    - COM conflitos vermelho+azul adjacentes: aplica destaques visuais sem
      LLM (segurança — não altera texto não autorizado).
    - SEM conflitos: passa por LLM com PROMPT_CORRECAO (apenas correções
      ortográficas mínimas, preserva estrutura HTML).

Saída: ata final HTML pronta pra registro em cartório. Cria linha em
`atas_versoes` (tipo='correcao_ortografica' ou 'final').
"""
