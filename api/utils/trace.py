"""
Trace ID — formato `avc_<tenant>_<timestamp>_<uuid8>` (RULES.md #32).

Gerado pelo middleware no início da request, propagado em logs via
`logger.contextualize(trace_id=...)` e devolvido no header `X-Trace-Id`
da resposta.
"""

import uuid
from datetime import datetime


def gerar_trace_id(tenant_id: str = "anon") -> str:
    """`avc_lello_20260427T143005_a1b2c3d4`"""
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    return f"avc_{tenant_id}_{ts}_{short_uuid}"
