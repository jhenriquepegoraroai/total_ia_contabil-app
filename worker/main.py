"""
Entrypoint do worker de batch.

Processo separado da API — é o que conserta o problema herdado do
`ingestion_service`, onde o job rodava com `asyncio.create_task` dentro do
processo da API: restart no meio derrubava o job e deixava o registro em
'running' para sempre.

Rodar:
    python -m worker.main

Em Railway, este é um serviço próprio, apontando para o mesmo Redis da API.

Registro de modelos: o bootstrap abaixo é onde o modelo real da Lello entra.
Enquanto nenhum estiver registrado, o worker sobe normalmente e cada job de
scoring falha com `ModeloNaoRegistrado`, deixando o motivo em
`scoring_runs.erro`. É deliberado — ver `worker/modelos.py`.
"""

from __future__ import annotations

import sys

from loguru import logger
from redis import Redis
from rq import Queue, Worker

from api import config
from api.utils.logging import configurar_logging

from . import modelos

# Nome da fila. A API enfileira aqui; o worker consome daqui.
FILA_SCORING = "scoring"


def registrar_modelos() -> None:
    """
    Ponto de extensão: registrar aqui os scorers reais.

        from lello_ml.churn import ChurnScorer
        modelos.registrar(ChurnScorer())

    Mantido vazio de propósito. Um scorer de mentira aqui gravaria score falso
    em `capability_scores`, com versão e carimbo de tempo, indistinguível de
    resultado verdadeiro na tela.
    """


def main() -> int:
    configurar_logging()
    registrar_modelos()

    disponiveis = modelos.registrados()
    if disponiveis:
        logger.info(f"Modelos registrados: {disponiveis}")
    else:
        logger.warning(
            "Nenhum modelo registrado. O worker sobe e consome a fila, mas "
            "todo job de scoring vai falhar com ModeloNaoRegistrado até que um "
            "scorer real seja registrado em registrar_modelos()."
        )

    logger.info(f"Conectando no Redis: {_mascarar(config.REDIS_URL)}")
    conexao = Redis.from_url(config.REDIS_URL)

    fila = Queue(FILA_SCORING, connection=conexao)
    logger.info(f"Worker escutando a fila '{FILA_SCORING}' (pendentes: {len(fila)})")

    Worker([fila], connection=conexao).work(with_scheduler=True)
    return 0


def _mascarar(url: str) -> str:
    """Esconde credencial da URL do Redis antes de logar."""
    if "@" not in url:
        return url
    esquema, resto = url.split("://", 1)
    return f"{esquema}://***@{resto.split('@', 1)[1]}"


if __name__ == "__main__":
    sys.exit(main())
