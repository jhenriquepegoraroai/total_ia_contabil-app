"""
Máquina de estados + workflow multi-ator das atas (Fase 7).

Estados (espelha o CHECK de `atas.status` na migration 010):

    rascunho → aguardando_transcricao → aguardando_geracao → gerada
    → revisao_consultor → aguardando_sindico → revisao_sindico
    → comparando → revisao_consultor_diff → aguardando_presidente
    → revisao_presidente → revisao_consultor_final → corrigindo
    → registrada (terminal)

Caminhos alternativos: `arquivada` (terminal manual) e `falhou` (com retry).

Atores e permissões:

    - **Consultor** (role='admin' do tenant): cria ata, dispara pipelines,
      aprova/rejeita versões, registra final.
    - **Síndico** (role='sindico', `atas.sindico_user_id == user.id`):
      edita durante 'aguardando_sindico'.
    - **Presidente** (role='sindico', `atas.presidente_user_id == user.id`):
      edita durante 'aguardando_presidente'.

Síndico e presidente são **opcionais**. Se nenhum for cadastrado, o
fluxo vai do consultor direto pra correção. Se só um, pula a etapa
do outro.

Este módulo só faz ops de banco e validação de estado/permissão.
**Side effects** (envio de e-mail, agendamento de BackgroundTask) ficam
com o router — recebe os dados de retorno e orquestra. Isso evita
acoplar workflow ao FastAPI/SMTP e facilita teste.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.atas import jobs_service

# =============================================================================
# Tabela de transições legais (validação)
# =============================================================================
TRANSICOES_LEGAIS: Final[dict[str, frozenset[str]]] = {
    "rascunho": frozenset({"aguardando_transcricao", "aguardando_geracao", "arquivada"}),
    "aguardando_transcricao": frozenset({"aguardando_geracao", "rascunho", "falhou", "arquivada"}),
    "aguardando_geracao": frozenset({"gerada", "falhou", "arquivada"}),
    "gerada": frozenset({"revisao_consultor", "aguardando_sindico", "aguardando_presidente",
                         "corrigindo", "arquivada"}),
    "revisao_consultor": frozenset({"aguardando_sindico", "aguardando_presidente",
                                    "corrigindo", "aguardando_geracao", "arquivada"}),
    "aguardando_sindico": frozenset({"revisao_sindico", "comparando", "arquivada"}),
    "revisao_sindico": frozenset({"comparando", "arquivada"}),
    "comparando": frozenset({"revisao_consultor_diff", "revisao_consultor_final",
                             "falhou", "arquivada"}),
    "revisao_consultor_diff": frozenset({"aguardando_presidente", "aguardando_sindico",
                                         "corrigindo", "arquivada"}),
    "aguardando_presidente": frozenset({"revisao_presidente", "comparando", "arquivada"}),
    "revisao_presidente": frozenset({"comparando", "arquivada"}),
    "revisao_consultor_final": frozenset({"corrigindo", "registrada", "aguardando_presidente",
                                          "aguardando_sindico", "arquivada"}),
    "corrigindo": frozenset({"registrada", "revisao_consultor_final", "falhou", "arquivada"}),
    "registrada": frozenset({"arquivada"}),
    "arquivada": frozenset(),
    "falhou": frozenset({"aguardando_geracao", "comparando", "corrigindo", "arquivada"}),
}


# =============================================================================
# Resultados das transições — info que o router usa pra orquestrar email + BG
# =============================================================================
@dataclass
class TransicaoResultado:
    """Resultado de uma operação de workflow. Router usa pra agendar side-effects."""

    sucesso: bool
    proximo_status: str | None = None
    versao_criada_id: str | None = None
    erro: str | None = None
    # Quem deve ser notificado por e-mail e em que template:
    notificar_papel: Literal["sindico", "presidente", "consultor", "todos"] | None = None
    # Se há BG task a disparar (comparador/corretor), o router agenda.
    agendar: Literal["comparar", "corrigir"] | None = None
    # Dados auxiliares específicos da transição (consultor, ator externo, motivo, etc).
    extra: dict[str, Any] | None = None


# =============================================================================
# Helpers de validação
# =============================================================================
def _validar_transicao(origem: str, destino: str) -> None:
    """Levanta ValueError se a transição não está em TRANSICOES_LEGAIS."""
    permitidos = TRANSICOES_LEGAIS.get(origem, frozenset())
    if destino not in permitidos:
        raise ValueError(
            f"Transição inválida: '{origem}' → '{destino}'. "
            f"Permitidos a partir de '{origem}': {sorted(permitidos)}"
        )


def _papel_do_user(ata: dict[str, Any], user_id: UUID) -> Literal["consultor", "sindico", "presidente"] | None:
    """Determina qual papel o user tem nesta ata específica."""
    uid = str(user_id)
    if str(ata["consultor_user_id"]) == uid:
        return "consultor"
    if ata.get("sindico_user_id") and str(ata["sindico_user_id"]) == uid:
        return "sindico"
    if ata.get("presidente_user_id") and str(ata["presidente_user_id"]) == uid:
        return "presidente"
    return None


# =============================================================================
# A. Consultor edita a ata (versão livre antes de enviar)
# =============================================================================
async def editar_consultor(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    consultor_user_id: UUID,
    conteudo_html: str,
) -> TransicaoResultado:
    """
    Consultor salva edição livre da ata atual. Cria nova versão imutável
    (tipo='edicao_consultor') e atualiza `versao_atual_id`. Status segue
    em `revisao_consultor` (ou avança de `gerada` pra `revisao_consultor`).

    Permitido em: gerada, revisao_consultor, revisao_consultor_diff, revisao_consultor_final.
    """
    ata = await jobs_service.buscar_ata(session, tenant_id, ata_id)
    if not ata:
        return TransicaoResultado(sucesso=False, erro="Ata não encontrada.")

    # Validações de papel + estado
    if str(ata["consultor_user_id"]) != str(consultor_user_id):
        return TransicaoResultado(
            sucesso=False, erro="Apenas o consultor da ata pode editar a versão do consultor."
        )

    estados_aceitos = {
        "gerada", "revisao_consultor", "revisao_consultor_diff", "revisao_consultor_final"
    }
    if ata["status"] not in estados_aceitos:
        return TransicaoResultado(
            sucesso=False,
            erro=(
                f"Status '{ata['status']}' não permite edição livre do consultor. "
                f"Esperado: {sorted(estados_aceitos)}."
            ),
        )

    versao_id = await jobs_service.criar_versao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        tipo="edicao_consultor",
        conteudo_html=conteudo_html,
        criada_por_user_id=consultor_user_id,
    )
    await jobs_service.atualizar_versao_atual(
        session, tenant_id=tenant_id, ata_id=ata_id, versao_id=versao_id
    )
    if ata["status"] == "gerada":
        await jobs_service.atualizar_status(
            session, tenant_id=tenant_id, ata_id=ata_id, status="revisao_consultor"
        )
    await jobs_service.registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=consultor_user_id,
        acao="editada_consultor",
        detalhe={"versao_id": str(versao_id)},
    )
    return TransicaoResultado(
        sucesso=True,
        proximo_status="revisao_consultor",
        versao_criada_id=str(versao_id),
    )


# =============================================================================
# B. Consultor envia pro síndico (snapshot versao_base + status)
# =============================================================================
async def enviar_para_sindico(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    consultor_user_id: UUID,
) -> TransicaoResultado:
    """
    Marca a versão atual como `versao_base_sindico` (snapshot pra diff
    posterior), muda status pra `aguardando_sindico` e devolve dados pro
    router enviar o e-mail.

    Permitido em: gerada, revisao_consultor, revisao_consultor_diff
    (caso raro: consultor rejeitou diff do presidente e quer reenviar
    pro síndico).
    """
    ata = await jobs_service.buscar_ata(session, tenant_id, ata_id)
    if not ata:
        return TransicaoResultado(sucesso=False, erro="Ata não encontrada.")

    if str(ata["consultor_user_id"]) != str(consultor_user_id):
        return TransicaoResultado(
            sucesso=False, erro="Apenas o consultor pode enviar pro síndico."
        )
    if not ata.get("sindico_user_id"):
        return TransicaoResultado(
            sucesso=False,
            erro="Ata não tem síndico cadastrado. Edite os dados antes de enviar.",
        )
    if not ata.get("versao_atual_id"):
        return TransicaoResultado(
            sucesso=False, erro="Ata sem versão atual — gere ou edite antes."
        )

    estados_aceitos = {"gerada", "revisao_consultor", "revisao_consultor_diff"}
    if ata["status"] not in estados_aceitos:
        return TransicaoResultado(
            sucesso=False,
            erro=f"Status '{ata['status']}' não permite envio pro síndico.",
        )
    _validar_transicao(ata["status"], "aguardando_sindico")

    await jobs_service.atualizar_versao_base(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        quem="sindico",
        versao_id=ata["versao_atual_id"],
    )
    await jobs_service.atualizar_status(
        session, tenant_id=tenant_id, ata_id=ata_id, status="aguardando_sindico"
    )
    await jobs_service.registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=consultor_user_id,
        acao="enviada_sindico",
        detalhe={"versao_base_id": str(ata["versao_atual_id"])},
    )
    return TransicaoResultado(
        sucesso=True,
        proximo_status="aguardando_sindico",
        notificar_papel="sindico",
    )


# =============================================================================
# C. Consultor envia pro presidente
# =============================================================================
async def enviar_para_presidente(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    consultor_user_id: UUID,
) -> TransicaoResultado:
    """Análogo ao envio pro síndico, com snapshot versao_base_presidente."""
    ata = await jobs_service.buscar_ata(session, tenant_id, ata_id)
    if not ata:
        return TransicaoResultado(sucesso=False, erro="Ata não encontrada.")

    if str(ata["consultor_user_id"]) != str(consultor_user_id):
        return TransicaoResultado(
            sucesso=False, erro="Apenas o consultor pode enviar pro presidente."
        )
    if not ata.get("presidente_user_id"):
        return TransicaoResultado(
            sucesso=False,
            erro="Ata não tem presidente cadastrado. Edite os dados antes de enviar.",
        )
    if not ata.get("versao_atual_id"):
        return TransicaoResultado(
            sucesso=False, erro="Ata sem versão atual."
        )

    estados_aceitos = {"gerada", "revisao_consultor", "revisao_consultor_diff",
                       "revisao_consultor_final"}
    if ata["status"] not in estados_aceitos:
        return TransicaoResultado(
            sucesso=False,
            erro=f"Status '{ata['status']}' não permite envio pro presidente.",
        )
    _validar_transicao(ata["status"], "aguardando_presidente")

    await jobs_service.atualizar_versao_base(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        quem="presidente",
        versao_id=ata["versao_atual_id"],
    )
    await jobs_service.atualizar_status(
        session, tenant_id=tenant_id, ata_id=ata_id, status="aguardando_presidente"
    )
    await jobs_service.registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=consultor_user_id,
        acao="enviada_presidente",
        detalhe={"versao_base_id": str(ata["versao_atual_id"])},
    )
    return TransicaoResultado(
        sucesso=True,
        proximo_status="aguardando_presidente",
        notificar_papel="presidente",
    )


# =============================================================================
# D. Síndico/presidente devolve a ata editada
# =============================================================================
async def devolver_ator_externo(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    user_id: UUID,
    conteudo_html: str,
) -> TransicaoResultado:
    """
    Síndico ou presidente devolve a ata editada. Cria versão
    'edicao_sindico' ou 'edicao_presidente', atualiza versao_atual,
    move status pra 'comparando', e devolve metadata pro router agendar
    o BG comparador.
    """
    ata = await jobs_service.buscar_ata(session, tenant_id, ata_id)
    if not ata:
        return TransicaoResultado(sucesso=False, erro="Ata não encontrada.")

    papel = _papel_do_user(ata, user_id)
    if papel not in ("sindico", "presidente"):
        return TransicaoResultado(
            sucesso=False,
            erro="Apenas o síndico ou presidente da ata pode devolver.",
        )

    estados_sindico = {"aguardando_sindico", "revisao_sindico"}
    estados_presidente = {"aguardando_presidente", "revisao_presidente"}
    if papel == "sindico" and ata["status"] not in estados_sindico:
        return TransicaoResultado(
            sucesso=False,
            erro=f"Síndico não pode devolver no status '{ata['status']}'.",
        )
    if papel == "presidente" and ata["status"] not in estados_presidente:
        return TransicaoResultado(
            sucesso=False,
            erro=f"Presidente não pode devolver no status '{ata['status']}'.",
        )

    versao_base_col = f"versao_base_{papel}_id"
    versao_base_id = ata.get(versao_base_col)
    if not versao_base_id:
        return TransicaoResultado(
            sucesso=False,
            erro=(
                f"Ata sem versão base do {papel} — não dá pra comparar. "
                "Esse estado é inesperado; reenvie pelo consultor."
            ),
        )

    tipo = "edicao_sindico" if papel == "sindico" else "edicao_presidente"
    versao_devolvida_id = await jobs_service.criar_versao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        tipo=tipo,
        conteudo_html=conteudo_html,
        criada_por_user_id=user_id,
    )
    await jobs_service.atualizar_versao_atual(
        session, tenant_id=tenant_id, ata_id=ata_id, versao_id=versao_devolvida_id
    )
    await jobs_service.atualizar_status(
        session, tenant_id=tenant_id, ata_id=ata_id, status="comparando"
    )
    await jobs_service.registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=user_id,
        acao=f"editada_{papel}",
        detalhe={
            "versao_devolvida_id": str(versao_devolvida_id),
            "versao_base_id": str(versao_base_id),
        },
    )
    await jobs_service.registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=None,
        acao="comparacao_iniciada",
        detalhe={"papel": papel},
    )

    # Próximo status pós-comparação:
    # - Síndico devolveu → revisao_consultor_diff (consultor decide se vai pro presidente ou correção)
    # - Presidente devolveu → revisao_consultor_final (consultor decide registrar)
    proximo_pos_compare = (
        "revisao_consultor_diff" if papel == "sindico" else "revisao_consultor_final"
    )

    return TransicaoResultado(
        sucesso=True,
        proximo_status="comparando",
        versao_criada_id=str(versao_devolvida_id),
        notificar_papel="consultor",
        agendar="comparar",
        extra={
            "papel": papel,
            "versao_base_id": str(versao_base_id),
            "versao_devolvida_id": str(versao_devolvida_id),
            "proximo_status_pos_compare": proximo_pos_compare,
        },
    )


# =============================================================================
# E. Consultor aprova / rejeita o diff
# =============================================================================
async def aprovar_diff(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    consultor_user_id: UUID,
    decisao: Literal["aceitar", "rejeitar"],
    motivo: str | None = None,
) -> TransicaoResultado:
    """
    Em `revisao_consultor_diff` (após síndico) ou `revisao_consultor_final`
    (após presidente). Decide se aceita o diff e segue, ou rejeita e
    devolve pro mesmo ator pra revisar.
    """
    ata = await jobs_service.buscar_ata(session, tenant_id, ata_id)
    if not ata:
        return TransicaoResultado(sucesso=False, erro="Ata não encontrada.")
    if str(ata["consultor_user_id"]) != str(consultor_user_id):
        return TransicaoResultado(
            sucesso=False, erro="Apenas o consultor decide aprovação do diff."
        )

    if ata["status"] not in ("revisao_consultor_diff", "revisao_consultor_final"):
        return TransicaoResultado(
            sucesso=False,
            erro=f"Status '{ata['status']}' não admite aprovar_diff.",
        )

    # Quem foi o último ator (síndico ou presidente)? Olha o tipo da versão atual.
    versao_atual = (
        await jobs_service.buscar_versao(session, tenant_id, ata["versao_atual_id"])
        if ata.get("versao_atual_id")
        else None
    )
    if not versao_atual:
        return TransicaoResultado(sucesso=False, erro="Versão atual ausente.")
    tipo = versao_atual["tipo"]
    if tipo == "edicao_sindico":
        ultimo_ator = "sindico"
    elif tipo == "edicao_presidente":
        ultimo_ator = "presidente"
    else:
        return TransicaoResultado(
            sucesso=False,
            erro=f"Versão atual não é edição de ator externo (tipo='{tipo}').",
        )

    if decisao == "rejeitar":
        proximo = (
            "aguardando_sindico" if ultimo_ator == "sindico" else "aguardando_presidente"
        )
        _validar_transicao(ata["status"], proximo)
        await jobs_service.atualizar_status(
            session, tenant_id=tenant_id, ata_id=ata_id, status=proximo
        )
        await jobs_service.registrar_acao(
            session,
            tenant_id=tenant_id,
            ata_id=ata_id,
            ator_user_id=consultor_user_id,
            acao="aprovacao_consultor_diff",
            detalhe={"decisao": "rejeitar", "motivo": motivo, "ultimo_ator": ultimo_ator},
        )
        return TransicaoResultado(
            sucesso=True,
            proximo_status=proximo,
            notificar_papel=ultimo_ator,           # avisa o ator que a edição voltou
            extra={"motivo": motivo},
        )

    # decisao == "aceitar"
    if ultimo_ator == "sindico":
        # Tem presidente? Se sim, vai pra ele. Senão, vai pra correção.
        if ata.get("presidente_user_id"):
            proximo = "aguardando_presidente"
            await jobs_service.atualizar_versao_base(
                session,
                tenant_id=tenant_id,
                ata_id=ata_id,
                quem="presidente",
                versao_id=ata["versao_atual_id"],
            )
            await jobs_service.atualizar_status(
                session, tenant_id=tenant_id, ata_id=ata_id, status=proximo
            )
            await jobs_service.registrar_acao(
                session,
                tenant_id=tenant_id,
                ata_id=ata_id,
                ator_user_id=consultor_user_id,
                acao="aprovacao_consultor_diff",
                detalhe={"decisao": "aceitar", "ultimo_ator": "sindico", "next": "presidente"},
            )
            await jobs_service.registrar_acao(
                session,
                tenant_id=tenant_id,
                ata_id=ata_id,
                ator_user_id=consultor_user_id,
                acao="enviada_presidente",
                detalhe={"versao_base_id": str(ata["versao_atual_id"])},
            )
            return TransicaoResultado(
                sucesso=True,
                proximo_status=proximo,
                notificar_papel="presidente",
            )
        # Sem presidente — vai pra correção direto.
        proximo = "corrigindo"
        await jobs_service.atualizar_status(
            session, tenant_id=tenant_id, ata_id=ata_id, status=proximo
        )
        await jobs_service.registrar_acao(
            session,
            tenant_id=tenant_id,
            ata_id=ata_id,
            ator_user_id=consultor_user_id,
            acao="aprovacao_consultor_diff",
            detalhe={"decisao": "aceitar", "ultimo_ator": "sindico", "next": "corrigindo"},
        )
        await jobs_service.registrar_acao(
            session,
            tenant_id=tenant_id,
            ata_id=ata_id,
            ator_user_id=None,
            acao="correcao_iniciada",
            detalhe={"versao_origem_id": str(ata["versao_atual_id"])},
        )
        return TransicaoResultado(
            sucesso=True,
            proximo_status=proximo,
            agendar="corrigir",
            extra={"versao_origem_id": str(ata["versao_atual_id"])},
        )

    # ultimo_ator == "presidente": vai pra correção.
    proximo = "corrigindo"
    await jobs_service.atualizar_status(
        session, tenant_id=tenant_id, ata_id=ata_id, status=proximo
    )
    await jobs_service.registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=consultor_user_id,
        acao="aprovacao_consultor_diff",
        detalhe={"decisao": "aceitar", "ultimo_ator": "presidente", "next": "corrigindo"},
    )
    await jobs_service.registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=None,
        acao="correcao_iniciada",
        detalhe={"versao_origem_id": str(ata["versao_atual_id"])},
    )
    return TransicaoResultado(
        sucesso=True,
        proximo_status=proximo,
        agendar="corrigir",
        extra={"versao_origem_id": str(ata["versao_atual_id"])},
    )


# =============================================================================
# F. Consultor pede correção sem ter passado por síndico/presidente
# =============================================================================
async def disparar_correcao_direta(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    consultor_user_id: UUID,
) -> TransicaoResultado:
    """
    Atalho — consultor pula síndico e presidente e vai direto pra correção.
    Aceito a partir de gerada, revisao_consultor, revisao_consultor_final.
    """
    ata = await jobs_service.buscar_ata(session, tenant_id, ata_id)
    if not ata:
        return TransicaoResultado(sucesso=False, erro="Ata não encontrada.")
    if str(ata["consultor_user_id"]) != str(consultor_user_id):
        return TransicaoResultado(
            sucesso=False, erro="Apenas o consultor dispara correção."
        )

    estados_aceitos = {"gerada", "revisao_consultor", "revisao_consultor_final",
                       "revisao_consultor_diff"}
    if ata["status"] not in estados_aceitos:
        return TransicaoResultado(
            sucesso=False,
            erro=f"Status '{ata['status']}' não permite disparar correção.",
        )
    if not ata.get("versao_atual_id"):
        return TransicaoResultado(
            sucesso=False, erro="Ata sem versão atual."
        )

    _validar_transicao(ata["status"], "corrigindo")
    await jobs_service.atualizar_status(
        session, tenant_id=tenant_id, ata_id=ata_id, status="corrigindo"
    )
    await jobs_service.registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=consultor_user_id,
        acao="correcao_iniciada",
        detalhe={"versao_origem_id": str(ata["versao_atual_id"])},
    )
    return TransicaoResultado(
        sucesso=True,
        proximo_status="corrigindo",
        agendar="corrigir",
        extra={"versao_origem_id": str(ata["versao_atual_id"])},
    )


# =============================================================================
# G. Consultor finaliza — após corretor com salvar=False, consultor
#    revisa destaques e aprova → registrada
# =============================================================================
async def finalizar_ata(
    session: AsyncSession,
    *,
    tenant_id: str,
    ata_id: UUID,
    consultor_user_id: UUID,
) -> TransicaoResultado:
    """
    Move ata de `revisao_consultor_final` pra `registrada`. Não roda
    corretor novamente — apenas confirma que o consultor revisou os
    destaques e aceita o resultado.
    """
    ata = await jobs_service.buscar_ata(session, tenant_id, ata_id)
    if not ata:
        return TransicaoResultado(sucesso=False, erro="Ata não encontrada.")
    if str(ata["consultor_user_id"]) != str(consultor_user_id):
        return TransicaoResultado(
            sucesso=False, erro="Apenas o consultor finaliza a ata."
        )

    if ata["status"] != "revisao_consultor_final":
        return TransicaoResultado(
            sucesso=False,
            erro=f"Status '{ata['status']}' não permite finalizar.",
        )
    _validar_transicao(ata["status"], "registrada")
    await jobs_service.atualizar_status(
        session, tenant_id=tenant_id, ata_id=ata_id, status="registrada"
    )
    await jobs_service.registrar_acao(
        session,
        tenant_id=tenant_id,
        ata_id=ata_id,
        ator_user_id=consultor_user_id,
        acao="registrada",
        detalhe={"versao_final_id": str(ata.get("versao_atual_id") or "")},
    )
    return TransicaoResultado(
        sucesso=True,
        proximo_status="registrada",
        notificar_papel="todos",
    )
