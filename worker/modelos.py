"""
Registro de modelos de scoring.

Os modelos (churn, fraude, inadimplência, ISC) existem e operam dentro da
Lello. A plataforma não os treina: ela os expõe com multi-tenancy, contrato de
dados e auditoria. Este módulo é a fronteira onde um modelo real se pluga.

REGRA: não existe modelo de mentira aqui.

Um scorer que devolvesse número plausível enquanto o modelo real não chega
seria pior que endpoint inexistente — a plataforma passaria a gravar score
falso em `capability_scores`, com versão de modelo e carimbo de tempo, e nada
na tela distinguiria isso de resultado verdadeiro. Quando nenhum modelo está
registrado, `obter()` levanta `ModeloNaoRegistrado` e o job de scoring falha
alto, deixando rastro em `scoring_runs.erro`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from loguru import logger


class ModeloNaoRegistrado(RuntimeError):
    """Nenhum scorer registrado para a capacidade pedida."""


@dataclass(frozen=True, slots=True)
class Pontuacao:
    """Resultado do modelo para uma entidade."""

    entidade_id: str
    referencia: str
    score: float
    faixa: str | None = None
    # Contribuição das features, quando o modelo expõe. Vai para
    # `capability_scores.explicacao`.
    explicacao: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.faixa is not None and self.faixa not in ("baixo", "medio", "alto"):
            raise ValueError(
                f"faixa inválida: {self.faixa!r} (esperado baixo|medio|alto)"
            )


@runtime_checkable
class Scorer(Protocol):
    """
    Contrato que um modelo precisa cumprir para rodar na plataforma.

    `feature_set_nome` amarra o modelo ao contrato de dados que ele espera —
    é o que impede rodar um modelo treinado com um conjunto de features sobre
    linhas entregues com outro.
    """

    capability: str
    versao: str
    feature_set_nome: str

    def pontuar(self, linhas: list[dict[str, Any]]) -> list[Pontuacao]:
        """
        Recebe as linhas já validadas contra o contrato e devolve uma
        pontuação por entidade. Cada linha tem `referencia`, `entidade_id` e
        `valores` (dict coluna → valor).
        """
        ...


_REGISTRO: dict[str, Scorer] = {}


def registrar(scorer: Scorer) -> None:
    """
    Registra o scorer de uma capacidade. Chamado no bootstrap do worker,
    quando o modelo da Lello for encapsulado.
    """
    if not isinstance(scorer, Scorer):
        raise TypeError(
            f"{type(scorer).__name__} não cumpre o protocolo Scorer "
            "(precisa de capability, versao, feature_set_nome e pontuar())."
        )
    anterior = _REGISTRO.get(scorer.capability)
    if anterior is not None:
        logger.warning(
            f"Scorer de '{scorer.capability}' substituído: "
            f"{anterior.versao} → {scorer.versao}"
        )
    _REGISTRO[scorer.capability] = scorer
    logger.info(
        f"Scorer registrado: capability={scorer.capability} "
        f"versao={scorer.versao} feature_set={scorer.feature_set_nome}"
    )


def obter(capability: str) -> Scorer:
    """
    Devolve o scorer da capacidade. Levanta `ModeloNaoRegistrado` quando não
    há — de propósito: sem modelo real, o certo é o job falhar e aparecer em
    `scoring_runs`, não gerar número.
    """
    scorer = _REGISTRO.get(capability)
    if scorer is None:
        disponiveis = sorted(_REGISTRO) or ["(nenhum)"]
        raise ModeloNaoRegistrado(
            f"Nenhum modelo registrado para '{capability}'. "
            f"Registrados: {disponiveis}. O modelo real precisa ser "
            "encapsulado e registrado no bootstrap do worker."
        )
    return scorer


def registrados() -> list[str]:
    """Capacidades com modelo disponível — usado por health e diagnóstico."""
    return sorted(_REGISTRO)


def limpar() -> None:
    """Zera o registro. Existe para testes; não usar em runtime."""
    _REGISTRO.clear()
