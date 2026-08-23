"""
Pipeline de comparação entre duas versões de ata (algoritmo puro, sem LLM).

Portado de `02_compara_atas/compare_atas_core.py` (versão de produção).

Estratégia:
    - Parse HTML via BeautifulSoup
    - Extrai blocos textuais de `<p>, <li>, <h*>, <td>, <th>`
    - Alinha blocos via `difflib.SequenceMatcher` em nível de bloco
    - Pra blocos similares (ratio > 0.3) faz diff token-a-token
    - Saída: HTML do comparado-base com spans coloridos:
        vermelho riscado = removido
        azul negrito     = adicionado
    - Estatísticas: contagens de palavras + percentual de alteração

Stateless. Quando integrado no workflow (Fase 7), o resultado vira nova
linha em `atas_versoes` (tipo='comparacao') com o HTML em `conteudo_html`
e estatísticas em `metadata_json`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from html import escape
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

# CSS embutido no HTML resultante. Mantido idêntico ao original.
CSS_STYLES = """
<style>
    .comparacao-container {
        font-family: Arial, sans-serif;
        line-height: 1.6;
        padding: 20px;
    }
    .texto-removido {
        color: #cc0000;
        text-decoration: line-through;
        background-color: #ffe6e6;
    }
    .texto-adicionado {
        color: #0066cc;
        font-weight: bold;
        background-color: #e6f2ff;
    }
    .bloco-removido {
        border-left: 3px solid #cc0000;
        padding-left: 10px;
        margin: 5px 0;
    }
    .bloco-adicionado {
        border-left: 3px solid #0066cc;
        padding-left: 10px;
        margin: 5px 0;
    }
</style>
"""


# =============================================================================
# Resultado
# =============================================================================
@dataclass
class EstatisticasDiff:
    palavras_iguais: int = 0
    palavras_removidas: int = 0
    palavras_adicionadas: int = 0
    total_palavras: int = 0
    percentual_alteracao: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "palavras_iguais": self.palavras_iguais,
            "palavras_removidas": self.palavras_removidas,
            "palavras_adicionadas": self.palavras_adicionadas,
            "total_palavras": self.total_palavras,
            "percentual_alteracao": self.percentual_alteracao,
        }


@dataclass
class ResultadoComparacao:
    sucesso: bool
    html_comparacao: str | None = None
    estatisticas: EstatisticasDiff = field(default_factory=EstatisticasDiff)
    erro: str | None = None


# =============================================================================
# Helpers de tokenização e diff inline
# =============================================================================
def _tokenizar_texto(texto: str) -> list[str]:
    """Divide o texto em tokens (palavras + espaços), mantendo whitespace."""
    return re.findall(r"\S+|\s+", texto)


def _comparar_tokens_inline(
    tokens_orig: list[str], tokens_comp: list[str]
) -> list[tuple[str, str]]:
    """Diff token-a-token. Retorna lista de (tipo, texto) onde tipo ∈ {igual, removido, adicionado}."""
    matcher = SequenceMatcher(None, tokens_orig, tokens_comp)
    resultado: list[tuple[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            resultado.append(("igual", "".join(tokens_orig[i1:i2])))
        elif tag == "replace":
            texto_orig = "".join(tokens_orig[i1:i2])
            texto_comp = "".join(tokens_comp[j1:j2])
            if texto_orig.strip():
                resultado.append(("removido", texto_orig))
            if texto_comp.strip():
                resultado.append(("adicionado", texto_comp))
        elif tag == "delete":
            texto_orig = "".join(tokens_orig[i1:i2])
            if texto_orig.strip():
                resultado.append(("removido", texto_orig))
        elif tag == "insert":
            texto_comp = "".join(tokens_comp[j1:j2])
            if texto_comp.strip():
                resultado.append(("adicionado", texto_comp))

    return resultado


def _gerar_html_diff_inline(diferencas: list[tuple[str, str]]) -> str:
    """Renderiza diferenças inline como HTML com spans coloridos."""
    parts: list[str] = []
    for tipo, texto in diferencas:
        texto_escaped = escape(texto)
        if tipo == "igual":
            parts.append(texto_escaped)
        elif tipo == "removido":
            parts.append(f'<span class="texto-removido">{texto_escaped}</span>')
        elif tipo == "adicionado":
            parts.append(f'<span class="texto-adicionado">{texto_escaped}</span>')
    return "".join(parts)


def _extrair_blocos_texto(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Extrai blocos de texto de elementos `<p>, <li>, <h*>, <td>, <th>`."""
    blocos: list[dict[str, Any]] = []
    for elem in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th"]):
        texto = elem.get_text(separator=" ", strip=True)
        if texto:
            blocos.append({"elemento": elem, "texto": texto, "html": str(elem)})
    return blocos


def _substituir_conteudo_elemento(elem, novo_html: str) -> None:
    """Substitui o conteúdo de um elemento BeautifulSoup preservando a tag."""
    elem.clear()
    novo_soup = BeautifulSoup(novo_html, "html.parser")
    for child in list(novo_soup.children):
        elem.append(child)


# =============================================================================
# Função principal
# =============================================================================
def comparar_atas(ata_original: str, ata_comparar: str) -> ResultadoComparacao:
    """
    Compara duas atas em HTML e retorna o HTML diff colorido + estatísticas.

    PRESERVA a formatação HTML do `ata_comparar` (que é a versão "nova" — a
    versão editada pelo síndico/presidente). Diferenças aparecem como spans
    inline (vermelho riscado / azul negrito) ou divs de bloco quando a
    edição é estrutural.

    Stateless — caller decide se persiste em `atas_versoes`.
    """
    if not ata_original or not ata_comparar:
        return ResultadoComparacao(
            sucesso=False, erro="Ambas as ATAs são obrigatórias."
        )

    try:
        logger.info("[atas/comparacao] iniciando comparação")
        soup_orig = BeautifulSoup(ata_original, "html.parser")
        soup_comp = BeautifulSoup(ata_comparar, "html.parser")

        blocos_orig = _extrair_blocos_texto(soup_orig)
        blocos_comp = _extrair_blocos_texto(soup_comp)
        logger.info(
            f"[atas/comparacao] blocos: original={len(blocos_orig)} comparar={len(blocos_comp)}"
        )

        textos_orig = [b["texto"] for b in blocos_orig]
        textos_comp = [b["texto"] for b in blocos_comp]
        matcher = SequenceMatcher(None, textos_orig, textos_comp)

        # Estatísticas
        palavras_iguais = 0
        palavras_removidas = 0
        palavras_adicionadas = 0

        # Resultado parte do HTML "comparar" — preserva a formatação do
        # editor (síndico/presidente). Marcações inline são adicionadas
        # diretamente nos elementos correspondentes.
        soup_resultado = BeautifulSoup(ata_comparar, "html.parser")
        blocos_resultado = _extrair_blocos_texto(soup_resultado)
        blocos_processados: set[int] = set()

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for idx in range(i1, i2):
                    palavras_iguais += len(blocos_orig[idx]["texto"].split())

            elif tag == "replace":
                # Match interno entre orig_slice e comp_slice via similaridade.
                orig_slice = blocos_orig[i1:i2]
                comp_slice = blocos_comp[j1:j2]
                matched_orig = [False] * len(orig_slice)
                matched_comp = [False] * len(comp_slice)
                matches: list[tuple[int, int, float]] = []

                for idx_o, bloco_o in enumerate(orig_slice):
                    melhor_ratio = 0.3  # threshold mínimo
                    melhor_idx_c = -1
                    for idx_c, bloco_c in enumerate(comp_slice):
                        if matched_comp[idx_c]:
                            continue
                        ratio = SequenceMatcher(
                            None, bloco_o["texto"], bloco_c["texto"]
                        ).ratio()
                        if ratio > melhor_ratio:
                            melhor_ratio = ratio
                            melhor_idx_c = idx_c
                    if melhor_idx_c >= 0:
                        matches.append((idx_o, melhor_idx_c, melhor_ratio))
                        matched_orig[idx_o] = True
                        matched_comp[melhor_idx_c] = True

                # Blocos modificados (com match): diff inline
                for idx_o, idx_c, _ratio in matches:
                    bloco_o = orig_slice[idx_o]
                    bloco_c = comp_slice[idx_c]
                    tokens_orig = _tokenizar_texto(bloco_o["texto"])
                    tokens_comp = _tokenizar_texto(bloco_c["texto"])
                    diferencas = _comparar_tokens_inline(tokens_orig, tokens_comp)

                    for tipo, texto in diferencas:
                        n = len(texto.split())
                        if tipo == "igual":
                            palavras_iguais += n
                        elif tipo == "removido":
                            palavras_removidas += n
                        elif tipo == "adicionado":
                            palavras_adicionadas += n

                    html_diff = _gerar_html_diff_inline(diferencas)
                    idx_resultado = j1 + idx_c
                    if idx_resultado < len(blocos_resultado):
                        elem = blocos_resultado[idx_resultado]["elemento"]
                        if id(elem) not in blocos_processados:
                            _substituir_conteudo_elemento(elem, html_diff)
                            blocos_processados.add(id(elem))

                # Blocos do original sem match (totalmente removidos): insere
                # antes do primeiro bloco da nova versão.
                for idx_o, matched in enumerate(matched_orig):
                    if not matched:
                        bloco_o = orig_slice[idx_o]
                        palavras_removidas += len(bloco_o["texto"].split())
                        texto_removido = (
                            f'<div class="bloco-removido">'
                            f'<span class="texto-removido">{escape(bloco_o["texto"])}</span>'
                            f"</div>"
                        )
                        if j1 < len(blocos_resultado):
                            elem_ref = blocos_resultado[j1]["elemento"]
                            novo_elem = BeautifulSoup(texto_removido, "html.parser")
                            elem_ref.insert_before(novo_elem)

                # Blocos da nova versão sem match (totalmente adicionados):
                # marca como adicionado.
                for idx_c, matched in enumerate(matched_comp):
                    if not matched:
                        bloco_c = comp_slice[idx_c]
                        palavras_adicionadas += len(bloco_c["texto"].split())
                        idx_resultado = j1 + idx_c
                        if idx_resultado < len(blocos_resultado):
                            elem = blocos_resultado[idx_resultado]["elemento"]
                            if id(elem) not in blocos_processados:
                                html_add = (
                                    f'<span class="texto-adicionado">'
                                    f'{escape(bloco_c["texto"])}</span>'
                                )
                                _substituir_conteudo_elemento(elem, html_add)
                                blocos_processados.add(id(elem))

            elif tag == "delete":
                # Blocos do original totalmente removidos (não há novos no slot).
                for idx in range(i1, i2):
                    bloco = blocos_orig[idx]
                    palavras_removidas += len(bloco["texto"].split())
                    texto_removido = (
                        f'<div class="bloco-removido">'
                        f'<span class="texto-removido">{escape(bloco["texto"])}</span>'
                        f"</div>"
                    )
                    if j1 < len(blocos_resultado):
                        elem_ref = blocos_resultado[j1]["elemento"]
                        novo_elem = BeautifulSoup(texto_removido, "html.parser")
                        elem_ref.insert_before(novo_elem)

            elif tag == "insert":
                # Blocos novos (não havia equivalente no original).
                for idx in range(j1, j2):
                    if idx < len(blocos_resultado):
                        bloco = blocos_resultado[idx]
                        palavras_adicionadas += len(bloco["texto"].split())
                        elem = bloco["elemento"]
                        if id(elem) not in blocos_processados:
                            html_add = (
                                f'<span class="texto-adicionado">'
                                f'{escape(bloco["texto"])}</span>'
                            )
                            _substituir_conteudo_elemento(elem, html_add)
                            blocos_processados.add(id(elem))

        html_final = (
            CSS_STYLES
            + '<div class="comparacao-container">'
            + str(soup_resultado)
            + "</div>"
        )

        total = palavras_iguais + palavras_removidas + palavras_adicionadas
        stats = EstatisticasDiff(
            palavras_iguais=palavras_iguais,
            palavras_removidas=palavras_removidas,
            palavras_adicionadas=palavras_adicionadas,
            total_palavras=total,
            percentual_alteracao=round(
                (palavras_removidas + palavras_adicionadas) / max(total, 1) * 100, 2
            ),
        )
        logger.info(
            f"[atas/comparacao] concluído — {stats.percentual_alteracao}% alteração "
            f"({stats.palavras_removidas} rem, {stats.palavras_adicionadas} add)"
        )
        return ResultadoComparacao(
            sucesso=True, html_comparacao=html_final, estatisticas=stats
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[atas/comparacao] falhou: {exc}")
        return ResultadoComparacao(sucesso=False, erro=str(exc))


# =============================================================================
# Background task — usado pelo workflow (Fase 7)
# =============================================================================
async def comparar_em_background(
    *,
    tenant_id: str,
    ata_id,                                # UUID
    versao_base_id,                        # UUID — versão "antes" (que o consultor enviou)
    versao_devolvida_id,                   # UUID — versão "depois" (editada pelo ator externo)
    proximo_status: str,                   # 'revisao_consultor_diff' ou 'revisao_consultor_final'
) -> None:
    """
    Carrega 2 versões do DB, roda o comparador, persiste o resultado como
    nova linha em `atas_versoes(tipo='comparacao')` e move a ata pro
    `proximo_status`. Engole exceções (registra em erro_detalhe).
    """
    import json

    from sqlalchemy import text

    from api.atas import jobs_service
    from api.db import tenant_session

    async with tenant_session(tenant_id) as session:
        v_base = await jobs_service.buscar_versao(session, tenant_id, versao_base_id)
        v_devolvida = await jobs_service.buscar_versao(session, tenant_id, versao_devolvida_id)

    if not v_base or not v_devolvida:
        logger.error(
            f"[atas/comparacao] versão sumiu antes do diff: base={versao_base_id} "
            f"devolvida={versao_devolvida_id}"
        )
        async with tenant_session(tenant_id) as session:
            await session.execute(
                text(
                    "UPDATE atas SET status='falhou', "
                    "erro_detalhe='Versões base/devolvida ausentes pra comparação' "
                    "WHERE id=:aid AND tenant_id=:tid"
                ),
                {"aid": str(ata_id), "tid": tenant_id},
            )
        return

    resultado = comparar_atas(v_base["conteudo_html"], v_devolvida["conteudo_html"])

    async with tenant_session(tenant_id) as session:
        if not resultado.sucesso:
            await session.execute(
                text(
                    "UPDATE atas SET status='falhou', erro_detalhe=:err, updated_at=NOW() "
                    "WHERE id=:aid AND tenant_id=:tid"
                ),
                {"err": (resultado.erro or "")[:1000], "aid": str(ata_id), "tid": tenant_id},
            )
            return

        # Cria linha imutável de comparação.
        meta = {
            "versao_base_id": str(versao_base_id),
            "versao_devolvida_id": str(versao_devolvida_id),
            "estatisticas": resultado.estatisticas.to_dict(),
        }
        row = (await session.execute(
            text(
                """
                INSERT INTO atas_versoes
                    (ata_id, tenant_id, tipo, conteudo_html, metadata_json,
                     criada_por_user_id)
                VALUES (:aid, :tid, 'comparacao', :html, CAST(:meta AS JSONB), NULL)
                RETURNING id
                """
            ),
            {
                "aid": str(ata_id),
                "tid": tenant_id,
                "html": resultado.html_comparacao,
                "meta": json.dumps(meta),
            },
        )).first()
        assert row is not None

        await session.execute(
            text(
                "UPDATE atas SET status=:st, updated_at=NOW() "
                "WHERE id=:aid AND tenant_id=:tid"
            ),
            {"st": proximo_status, "aid": str(ata_id), "tid": tenant_id},
        )

        await jobs_service.registrar_acao(
            session,
            tenant_id=tenant_id,
            ata_id=ata_id,
            ator_user_id=None,
            acao="comparacao_concluida",
            detalhe={
                "versao_diff_id": str(row.id),
                "estatisticas": resultado.estatisticas.to_dict(),
                "proximo_status": proximo_status,
            },
        )

    logger.info(
        f"[atas/comparacao] ata={ata_id} done — diff={row.id} "
        f"alteração={resultado.estatisticas.percentual_alteracao}%"
    )
