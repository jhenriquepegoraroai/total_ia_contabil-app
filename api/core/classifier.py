"""
Classificador de pergunta → categoria.

Cada tenant define o prompt de categorias no JSON (`categorias_prompt`).
O classificador chama GPT com `temperature=0` e parseia o número da categoria
da resposta. Se não conseguir parsear, retorna `None` (cai em busca por
embeddings — fluxo default).
"""

import re

from loguru import logger

from api.llm import LLMClient
from api.tenants.models import TenantConfig

# Captura o primeiro número (com sinal opcional) na resposta — `12`, `-1`, `cat 51` → 51.
_NUMERO_RE = re.compile(r"-?\d+")


async def classificar_pergunta(
    pergunta: str,
    tenant_config: TenantConfig,
    llm: LLMClient,
) -> int | None:
    """
    Retorna o número da categoria, ou `None` se não conseguir classificar.

    Caller deve tratar `None` como "categoria default" (busca por embeddings).
    """
    if not pergunta or not pergunta.strip():
        return None

    raw = await llm.classificar(
        system_prompt=tenant_config.categorias_prompt,
        pergunta=pergunta,
    )

    match = _NUMERO_RE.search(raw)
    if not match:
        logger.warning(
            f"[{tenant_config.tenant_id}] classificador retornou string sem número: {raw!r}"
        )
        return None

    try:
        return int(match.group(0))
    except ValueError:
        logger.warning(f"[{tenant_config.tenant_id}] não conseguiu parsear: {raw!r}")
        return None
