"""
Pipeline de correção ortográfica final da ata (Fase 5).

Portado de `03_corrige_atas/{corrige_ata_core,llm_services}.py`. Roda
sobre o HTML do diff produzido pelo comparador (Fase 4) — ou seja, um
HTML que pode conter spans coloridos vermelho (riscado/removido) e azul
(negrito/adicionado).

Estratégia em dois caminhos:

  COM CONFLITOS REAIS (vermelho+azul adjacentes, azul não-vazio):
    - Aplica destaques visuais nos pares conflituosos SEM chamar LLM
    - Texto isolado [REMOVIDO] vira preto (consultor não validou remoção)
    - Texto isolado [ADICIONADO] vira preto (adição validada)
    - Retorna salvar=False — consultor precisa revisar antes de fechar a ata

  SEM CONFLITOS:
    - Converte spans em marcadores `[REMOVIDO]...[/REMOVIDO]` /
      `[ADICIONADO]...[/ADICIONADO]`
    - Passa pelo LLM com PROMPT_CORRECAO_FINAL (correções ortográficas
      mínimas, preserva estrutura HTML)
    - Aplica destaque verde nos placeholders ([...], __/__/____, R$ [...])
    - Retorna salvar=True — pronta pra registro em cartório

Saída: nova linha em `atas_versoes` com tipo='correcao_ortografica'
(salvar=True → status='registrada' aguardando ato final) ou
'comparacao' (salvar=False → status='revisao_consultor_final').
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, NavigableString
from loguru import logger
from openai import AsyncOpenAI

from api.atas.pipeline_geracao import limpar_markdown
from api.atas.prompts import SYSTEM_PROMPT_FINAL
from api.llm.openai_client import _modelo_moderno, get_llm_client_for_tenant
from api.tenants.models import TenantConfig


# =============================================================================
# Resultado
# =============================================================================
@dataclass
class ResultadoCorrecao:
    sucesso: bool
    ata_html: str | None = None
    salvar: bool = False                # True = pronta pro registro; False = consultor precisa revisar
    qtde_conflitos: int = 0
    erro: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Helpers de classificação de spans
# =============================================================================
def _eh_apenas_pontuacao(texto: str) -> bool:
    """True se o texto só tem pontuação e/ou espaços (irrelevante semanticamente)."""
    return bool(re.match(r"^[\s\.,;:!?\-–—\'\"\(\)\[\]\{\}]*$", texto.strip()))


def _identificar_tipo_span(span) -> str:
    """
    Identifica o tipo do span pela presença de cores/classes específicas.

    Cobre 2 formatos de input:
      - Original (#F22200 vermelho riscado / #2F80ED azul) — antes da
        comparação rodar
      - Reenvio (#cc0000 / #0066cc) — saída do comparador da Fase 4
    """
    style = span.get("style", "")
    classes = span.get("class", []) or []

    # Formato original (saída antiga)
    if "#F22200" in style or ("line-through" in style and "#cc0000" not in style):
        return "removido"
    if "#2F80ED" in style:
        return "adicionado"

    # Formato de reenvio (saída do comparador da Fase 4)
    if "#cc0000" in style or "line-through" in style:
        return "removido_destacado"
    if "#0066cc" in style:
        return "adicionado_destacado"

    # Por classe CSS
    if "texto-removido" in classes:
        return "removido"
    if "texto-adicionado" in classes:
        return "adicionado"
    if "texto-igual" in classes:
        return "igual"
    return "igual"


def _normalizar_tipo(tipo: str) -> str:
    """Colapsa removido_destacado → removido, etc."""
    if "removido" in tipo:
        return "removido"
    if "adicionado" in tipo:
        return "adicionado"
    return "igual"


def _sao_adjacentes(span1, span2) -> bool:
    """
    True se `span1` e `span2` estão consecutivos no DOM (sem texto
    significativo entre eles — só whitespace e pontuação contam como ok).
    """
    sibling = span1.next_sibling
    while sibling is not None and sibling != span2:
        if isinstance(sibling, NavigableString):
            t = str(sibling).strip()
            if t and not _eh_apenas_pontuacao(t):
                return False
        elif sibling.name is not None and sibling != span2:
            return False
        sibling = sibling.next_sibling
    return sibling == span2


# =============================================================================
# Detecção de conflitos por parágrafo
# =============================================================================
def _detectar_conflitos(html_comparacao: str) -> tuple[bool, list[dict[str, Any]]]:
    """
    Procura pares vermelho+azul (ou azul+vermelho) adjacentes em cada
    parágrafo. Conflitos com azul = só pontuação são descartados.

    Retorna (tem_conflitos, lista_conflitos). Cada conflito traz texto
    removido/adicionado, índice do parágrafo, contexto antes/depois e
    referências aos spans no soup.
    """
    soup = BeautifulSoup(html_comparacao, "html.parser")
    conflitos: list[dict[str, Any]] = []

    for idx_p, paragrafo in enumerate(soup.find_all("p")):
        spans = paragrafo.find_all("span", recursive=False) or paragrafo.find_all("span")
        relevantes: list[tuple[Any, str]] = [
            (s, _identificar_tipo_span(s))
            for s in spans
            if _normalizar_tipo(_identificar_tipo_span(s)) in ("removido", "adicionado")
        ]

        i = 0
        while i < len(relevantes) - 1:
            span_atual, tipo_atual = relevantes[i]
            span_proximo, tipo_proximo = relevantes[i + 1]
            tipo_a = _normalizar_tipo(tipo_atual)
            tipo_b = _normalizar_tipo(tipo_proximo)
            texto_a = span_atual.get_text().strip()
            texto_b = span_proximo.get_text().strip()

            if not _sao_adjacentes(span_atual, span_proximo):
                i += 1
                continue

            # Conflito = vermelho seguido de azul (ou vice-versa) em que o
            # azul não é só pontuação.
            par_substituicao: dict[str, Any] | None = None
            if tipo_a == "removido" and tipo_b == "adicionado" and not _eh_apenas_pontuacao(texto_b):
                par_substituicao = {
                    "removido": texto_a,
                    "adicionado": texto_b,
                    "span_removido": span_atual,
                    "span_adicionado": span_proximo,
                }
            elif tipo_a == "adicionado" and tipo_b == "removido" and not _eh_apenas_pontuacao(texto_a):
                par_substituicao = {
                    "removido": texto_b,
                    "adicionado": texto_a,
                    "span_removido": span_proximo,
                    "span_adicionado": span_atual,
                }

            if par_substituicao is not None:
                # Coleta contexto (~50 chars antes e depois) pra identificação única.
                contexto_antes = ""
                prev = par_substituicao["span_removido"].previous_sibling
                while prev is not None and len(contexto_antes) < 50:
                    if isinstance(prev, NavigableString):
                        contexto_antes = str(prev) + contexto_antes
                    elif hasattr(prev, "get_text"):
                        contexto_antes = prev.get_text() + contexto_antes
                    prev = getattr(prev, "previous_sibling", None)

                contexto_depois = ""
                nxt = par_substituicao["span_adicionado"].next_sibling
                while nxt is not None and len(contexto_depois) < 50:
                    if isinstance(nxt, NavigableString):
                        contexto_depois += str(nxt)
                    elif hasattr(nxt, "get_text"):
                        contexto_depois += nxt.get_text()
                    nxt = getattr(nxt, "next_sibling", None)

                conflitos.append({
                    "tipo": "substituicao",
                    "removido": par_substituicao["removido"],
                    "adicionado": par_substituicao["adicionado"],
                    "paragrafo_idx": idx_p,
                    "contexto_antes": contexto_antes.strip()[-50:],
                    "contexto_depois": contexto_depois.strip()[:50],
                })
            i += 1

    logger.info(f"[atas/correcao] conflitos detectados: {len(conflitos)}")
    return len(conflitos) > 0, conflitos


# =============================================================================
# Caminho 1 — COM conflitos: aplica destaques visuais sem LLM
# =============================================================================
def _aplicar_destaques(html_comparacao: str, conflitos: list[dict[str, Any]]) -> str:
    """
    Mantém vermelho/azul nos conflitos reais e converte spans isolados
    (vermelho ou azul fora de par) para texto preto.

    Decisão deliberada: NÃO chama LLM aqui — segurança contra alteração
    de texto não autorizada quando há ambiguidade.
    """
    soup = BeautifulSoup(html_comparacao, "html.parser")

    for idx_p, paragrafo in enumerate(soup.find_all("p")):
        for span in paragrafo.find_all("span"):
            tipo = _normalizar_tipo(_identificar_tipo_span(span))
            if tipo not in ("removido", "adicionado"):
                continue
            texto = span.get_text()

            # É conflito se o texto bate com algum dos conflitos do mesmo parágrafo.
            eh_conflito = False
            for c in conflitos:
                if c["paragrafo_idx"] != idx_p:
                    continue
                if tipo == "removido" and texto.strip() == c["removido"].strip():
                    eh_conflito = True
                    break
                if tipo == "adicionado" and texto.strip() == c["adicionado"].strip():
                    eh_conflito = True
                    break

            if eh_conflito:
                if tipo == "removido":
                    span["style"] = (
                        "color: #cc0000; text-decoration: line-through; "
                        "background-color: #ffe6e6; font-size: 1.1em; "
                        "font-weight: bold; padding: 2px 4px;"
                    )
                    span["class"] = ["conflito-removido"]
                else:
                    span["style"] = (
                        "color: #0066cc; background-color: #e6f2ff; "
                        "font-size: 1.1em; font-weight: bold; padding: 2px 4px;"
                    )
                    span["class"] = ["conflito-adicionado"]
            else:
                # Span isolado: descarta o span e mantém só o texto (preto).
                span.replace_with(texto)

    # Limpa container de comparação se existir.
    style_tag = soup.find("style")
    if style_tag:
        style_tag.decompose()
    conteudo = soup.find("div", class_="conteudo-comparacao")
    if conteudo:
        return "".join(str(child) for child in conteudo.children).strip()
    return str(soup).strip()


# =============================================================================
# Caminho 2 — SEM conflitos: marca [REMOVIDO]/[ADICIONADO] e passa pro LLM
# =============================================================================
def _processar_sem_conflitos(html_comparacao: str) -> str:
    """
    Converte o HTML do diff em texto plano com marcadores
    `[REMOVIDO]...[/REMOVIDO]` e `[ADICIONADO]...[/ADICIONADO]` que o
    prompt do LLM sabe interpretar.
    """
    soup = BeautifulSoup(html_comparacao, "html.parser")
    paragrafos_saida: list[str] = []

    for paragrafo in soup.find_all("p"):
        partes: list[str] = []
        for elemento in paragrafo.descendants:
            if getattr(elemento, "name", None) == "span":
                inner = str(elemento)
                inner = re.sub(r"<br\s*/?>", "\n", inner)
                texto = BeautifulSoup(inner, "html.parser").get_text()
                tipo = _normalizar_tipo(_identificar_tipo_span(elemento))
                if tipo == "removido":
                    partes.append(f"[REMOVIDO]{texto}[/REMOVIDO]")
                elif tipo == "adicionado":
                    partes.append(f"[ADICIONADO]{texto}[/ADICIONADO]")
                else:
                    partes.append(texto)
            elif isinstance(elemento, NavigableString) and elemento.parent.name not in (
                "span",
                "script",
                "style",
            ):
                t = str(elemento)
                if t.strip():
                    partes.append(t)
        if partes:
            paragrafos_saida.append("".join(partes))

    return "\n\n".join(paragrafos_saida)


async def _gerar_ata_final_via_llm(
    *,
    client: AsyncOpenAI,
    model: str,
    texto_marcado: str,
    temperature: float,
    max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    """Chamada LLM com PROMPT_CORRECAO_FINAL. Retorna HTML pronto."""
    user_msg = (
        "Processe esta ATA e gere a versão final em HTML.\n\n"
        "REGRAS CRÍTICAS:\n"
        "- MANTENHA a estrutura original de parágrafos\n"
        "- NÃO adicione espaços extras (<p>&nbsp;</p>)\n"
        "- NÃO adicione negrito (<strong>) onde não havia\n"
        "- Faça APENAS correções ortográficas mínimas\n"
        '- DESTAQUE placeholders com <span style="background-color: #00FF00;">placeholder</span>\n\n'
        f"TEXTO DA ATA:\n\n{texto_marcado}"
    )

    kwargs: dict[str, Any] = {"model": model}
    if _modelo_moderno(model):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature
        kwargs["top_p"] = 1.0

    resp = await client.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_FINAL},
            {"role": "user", "content": user_msg},
        ],
        **kwargs,
    )
    choice = resp.choices[0]
    html = (choice.message.content or "").strip()

    # Reaplica limpeza de markdown (mesmo helper do gerador).
    html = limpar_markdown(html)

    metadata: dict[str, Any] = {
        "model": model,
        "finish_reason": getattr(choice, "finish_reason", None),
    }
    if hasattr(resp, "usage") and resp.usage is not None:
        metadata["usage"] = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
            "completion_tokens": getattr(resp.usage, "completion_tokens", None),
            "total_tokens": getattr(resp.usage, "total_tokens", None),
        }
    return html, metadata


# =============================================================================
# Limpeza pós-LLM e destaque de placeholders
# =============================================================================
def _limpar_pontuacao_duplicada(texto: str) -> str:
    """
    Rede de segurança pós-LLM: remove pontuação duplicada e espaços
    incorretos. Preserva reticências (`...`) deliberadamente.
    """
    texto = re.sub(r"[,\s]*,+[,\s]*,", ",", texto)        # 2+ vírgulas
    texto = re.sub(r"\s+,", ",", texto)                    # espaço antes de vírgula
    texto = re.sub(r"[;\s]*;+[;\s]*;", ";", texto)
    texto = re.sub(r"\s+;", ";", texto)
    texto = re.sub(r"[:\s]*:+[:\s]*:", ":", texto)
    texto = re.sub(r"\s+:", ":", texto)
    texto = re.sub(r"\.{4,}", "...", texto)                # 4+ pontos → reticências
    texto = re.sub(r"(?<!\.)\.\.(?!\.)", ".", texto)       # 2 pontos → 1
    texto = re.sub(r"\s+\.", ".", texto)
    texto = re.sub(r",([^\s\d)\]\n])", r", \1", texto)     # garante espaço após ,
    texto = re.sub(r";([^\s\d)\]\n])", r"; \1", texto)
    return texto


def _destacar_placeholders_correcao(html: str) -> str:
    """
    Aplica `<span style="background-color: #00FF00;">...</span>` em
    placeholders identificados por padrões mais ricos que o do gerador
    (cobre datas vazias, horários, valores monetários incompletos, etc.).

    Idempotente: pula matches que já estão dentro de span verde.
    """
    padroes = [
        # Valores monetários incompletos
        (r"(R\$\s*\[[^\]]*\])", r'<span style="background-color: #00FF00;">\1</span>'),
        (r"(R\$\s*_{2,})", r'<span style="background-color: #00FF00;">\1</span>'),
        # Colchetes com instruções
        (
            r"(\[(?:inserir|indicar|digite|digitar|informar|preencher|colocar|"
            r"nome|data|valor|horário|local|endereço)[^\]]*\])",
            r'<span style="background-color: #00FF00;">\1</span>',
        ),
        # Lacunas com símbolos
        (r"(\[[\s\.…]+\])", r'<span style="background-color: #00FF00;">\1</span>'),
        # Datas vazias
        (r"(_{2,}/_{2,}/_{2,})", r'<span style="background-color: #00FF00;">\1</span>'),
        (r"(\bdd/mm/aaaa\b)", r'<span style="background-color: #00FF00;">\1</span>'),
        # Horários vazios
        (r"(\.{2,}h\.{2,}(?:min)?)", r'<span style="background-color: #00FF00;">\1</span>'),
        (r"(_{2,}h_{2,}(?:min)?)", r'<span style="background-color: #00FF00;">\1</span>'),
        (r"(_{2,}:_{2,})", r'<span style="background-color: #00FF00;">\1</span>'),
    ]

    resultado = html
    for padrao, sub in padroes:
        resultado = re.sub(padrao, sub, resultado, flags=re.IGNORECASE)

    # Colapsa eventual span aninhado por dupla aplicação.
    resultado = re.sub(
        r'<span style="background-color: #00FF00;"><span style="background-color: #00FF00;">'
        r"([^<]*)</span></span>",
        r'<span style="background-color: #00FF00;">\1</span>',
        resultado,
    )
    return resultado


# =============================================================================
# Orquestrador
# =============================================================================
async def corrigir_ata(
    *,
    tenant_config: TenantConfig,
    html_comparacao: str,
    max_tokens: int = 4000,
) -> ResultadoCorrecao:
    """
    Roda o caminho 1 (destaques sem LLM) ou caminho 2 (LLM com correção
    ortográfica) conforme presença de conflitos no HTML do diff.
    """
    if not html_comparacao or not html_comparacao.strip():
        return ResultadoCorrecao(sucesso=False, erro="HTML de comparação é obrigatório.")

    atas_cfg = tenant_config.atas
    if atas_cfg is None:
        return ResultadoCorrecao(
            sucesso=False,
            erro="Tenant sem TenantAtasConfig — modelo OpenAI do módulo atas não configurado.",
        )

    try:
        tem_conflitos, conflitos = _detectar_conflitos(html_comparacao)
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[atas/correcao] erro detectando conflitos: {exc}")
        return ResultadoCorrecao(sucesso=False, erro=str(exc))

    if tem_conflitos:
        try:
            html = _aplicar_destaques(html_comparacao, conflitos)
            html = _limpar_pontuacao_duplicada(html)
            html = _destacar_placeholders_correcao(html)
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[atas/correcao] erro aplicando destaques: {exc}")
            return ResultadoCorrecao(sucesso=False, erro=str(exc))

        return ResultadoCorrecao(
            sucesso=True,
            ata_html=html,
            salvar=False,
            qtde_conflitos=len(conflitos),
            metadata={"caminho": "destaques_sem_llm", "conflitos": len(conflitos)},
        )

    # Caminho 2 — sem conflitos, vai pro LLM.
    try:
        texto_marcado = _processar_sem_conflitos(html_comparacao)
        llm = get_llm_client_for_tenant(tenant_config)
        html, meta_llm = await _gerar_ata_final_via_llm(
            client=llm.async_client,
            model=atas_cfg.openai_model,
            texto_marcado=texto_marcado,
            temperature=atas_cfg.temperature_correcao,
            max_tokens=max_tokens,
        )
        html = _limpar_pontuacao_duplicada(html)
        html = _destacar_placeholders_correcao(html)
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[atas/correcao] erro no LLM: {exc}")
        return ResultadoCorrecao(sucesso=False, erro=str(exc))

    return ResultadoCorrecao(
        sucesso=True,
        ata_html=html,
        salvar=True,
        qtde_conflitos=0,
        metadata={"caminho": "llm_correcao_ortografica", "llm": meta_llm},
    )
