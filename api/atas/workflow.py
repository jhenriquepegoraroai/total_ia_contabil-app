"""
Máquina de estados + workflow multi-ator das atas (Fase 7).

Estados (espelha o CHECK de `atas.status`):
    rascunho → aguardando_transcricao → aguardando_geracao → gerada
    → revisao_consultor → aguardando_sindico → revisao_sindico
    → comparando → revisao_consultor_diff → aguardando_presidente
    → revisao_presidente → revisao_consultor_final → corrigindo
    → registrada (terminal)

Caminhos alternativos: `arquivada` (terminal manual) e `falhou` (com retry).

Atores e permissões:
    - Consultor (role='admin' do tenant): cria ata, dispara pipelines,
      aprova/rejeita versões, registra final.
    - Síndico (role='sindico', `atas.sindico_user_id == user.id`): edita
      durante 'aguardando_sindico'.
    - Presidente (role='sindico', `atas.presidente_user_id == user.id`):
      edita durante 'aguardando_presidente'.

A transição NÃO é livre — cada handler valida origem→destino válida e
audita em `atas_acoes`.

Implementação na Fase 7 — bootstrap só esboça as transições.
"""

from typing import Final


# Tabela de transições legais (origem → destinos permitidos).
# Preenchida na Fase 7. Por ora, listada pra documentar a máquina.
TRANSICOES_LEGAIS: Final[dict[str, frozenset[str]]] = {
    "rascunho": frozenset({"aguardando_transcricao", "aguardando_geracao", "arquivada"}),
    "aguardando_transcricao": frozenset({"aguardando_geracao", "falhou", "arquivada"}),
    "aguardando_geracao": frozenset({"gerada", "falhou", "arquivada"}),
    "gerada": frozenset({"revisao_consultor", "arquivada"}),
    "revisao_consultor": frozenset({"aguardando_sindico", "aguardando_geracao", "arquivada"}),
    "aguardando_sindico": frozenset({"revisao_sindico", "arquivada"}),
    "revisao_sindico": frozenset({"comparando", "arquivada"}),
    "comparando": frozenset({"revisao_consultor_diff", "falhou", "arquivada"}),
    "revisao_consultor_diff": frozenset({"aguardando_presidente", "aguardando_sindico", "arquivada"}),
    "aguardando_presidente": frozenset({"revisao_presidente", "arquivada"}),
    "revisao_presidente": frozenset({"revisao_consultor_final", "arquivada"}),
    "revisao_consultor_final": frozenset({"corrigindo", "aguardando_presidente", "arquivada"}),
    "corrigindo": frozenset({"registrada", "falhou", "arquivada"}),
    "registrada": frozenset({"arquivada"}),
    "arquivada": frozenset(),  # terminal
    "falhou": frozenset({"aguardando_geracao", "comparando", "corrigindo", "arquivada"}),  # retry
}
