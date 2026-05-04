"""
Prompts dos pipelines do Bella Atas.

Conteúdo definitivo será portado do projeto original `01_gera_atas` na
Fase 3 (geração) e `03_corrige_atas` na Fase 5 (correção). O comparador
da Fase 4 não usa LLM (difflib puro).

Os prompts ficam aqui em vez de ficarem no `api/tenants/configs/<tenant>.json`
porque são longos (~375 linhas no original) e não são genuinamente
customizáveis por tenant na maioria dos casos. Se algum dia um cliente
quiser prompt próprio, criamos override em `TenantAtasConfig.prompt_geracao`.
"""

# Placeholders — preenchidos nas próximas fases.
PROMPT_GERACAO: str = ""
PROMPT_REVISAO: str = ""
PROMPT_QUORUM: str = ""
PROMPT_CORRECAO: str = ""
