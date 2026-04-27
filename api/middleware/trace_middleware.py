"""
Middleware de trace_id — RULES.md #32.

Para cada request:
  1. Gera (ou propaga) um `X-Trace-Id` no formato `avc_<tenant>_<ts>_<uuid8>`
  2. Coloca em `request.state.trace_id`
  3. Injeta no contexto do loguru pela duração da request
  4. Devolve no header da response
"""

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from api.utils.trace import gerar_trace_id


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Tenant_id ainda não foi resolvido aqui (auth roda depois).
        # Geramos com `anon` e o handler atualiza o tenant na chamada do RAG.
        trace_id = request.headers.get("x-trace-id") or gerar_trace_id("anon")
        request.state.trace_id = trace_id

        with logger.contextualize(trace_id=trace_id):
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("Erro não tratado na request")
                raise

        response.headers["X-Trace-Id"] = trace_id
        return response
