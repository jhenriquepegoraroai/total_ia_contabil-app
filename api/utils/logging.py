"""
Configuração do loguru.

JSON estruturado em produção; formato humano em dev. Trace ID é injetado
via context (`logger.contextualize(trace_id=...)`) pelo middleware de trace.
"""

import sys

from loguru import logger

from api import config


def configurar_logging() -> None:
    """Reconfigura o sink padrão do loguru de acordo com APP_ENV."""
    logger.remove()

    if config.IS_PRODUCTION:
        logger.add(
            sys.stdout,
            level=config.LOG_LEVEL,
            serialize=True,  # JSON estruturado
            backtrace=False,
            diagnose=False,
        )
    else:
        logger.add(
            sys.stderr,
            level=config.LOG_LEVEL,
            colorize=True,
            backtrace=True,
            diagnose=True,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
                "<level>{level: <8}</level> "
                "<cyan>{extra[trace_id]:<24}</cyan> "
                "<level>{message}</level>"
            ),
        )

    # Bind default para que mensagens sem contexto não quebrem o formato.
    logger.configure(extra={"trace_id": "-"})
