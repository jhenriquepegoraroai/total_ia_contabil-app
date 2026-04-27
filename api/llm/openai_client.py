"""
Wrapper OpenAI — embedding de query (single) + chat completion.

Para o pipeline de ingestão (batch), ver `ingestion/embeddings.py`.
Aqui é só o caminho da request HTTP — single embedding por pergunta,
single completion por resposta.

REGRA CRÍTICA (RULES.md #16): classificação usa `temperature=0` e `top_p=1`.
Geração pode usar temperature configurável por tenant (default 0.2).
"""

from functools import lru_cache

from loguru import logger
from openai import AsyncOpenAI

from api import config


class LLMClient:
    """Wrapper assíncrono — uma instância por processo (singleton via lru_cache)."""

    def __init__(self, api_key: str, *, embedding_model: str, completion_model: str):
        self._client = AsyncOpenAI(api_key=api_key, timeout=30)
        self._embedding_model = embedding_model
        self._completion_model = completion_model

    async def embed_query(self, texto: str) -> list[float]:
        """Embedding de uma única pergunta. Trunca texto vazio e levanta."""
        if not texto or not texto.strip():
            raise ValueError("texto vazio")
        resp = await self._client.embeddings.create(
            model=self._embedding_model,
            input=[texto.strip()],
        )
        return resp.data[0].embedding

    async def classificar(
        self,
        *,
        system_prompt: str,
        pergunta: str,
        max_tokens: int = 16,
    ) -> str:
        """
        Classificação determinística (temperature=0, top_p=1).
        Retorna a string crua de saída — quem chama parseia para int/categoria.
        """
        resp = await self._client.chat.completions.create(
            model=self._completion_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pergunta},
            ],
            temperature=0.0,
            top_p=1.0,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    async def gerar_resposta(
        self,
        *,
        system_prompt: str,
        contexto: str,
        pergunta: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> str:
        """Geração com contexto RAG. Temperature configurável por tenant."""
        resp = await self._client.chat.completions.create(
            model=self._completion_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"CONTEXTO:\n{contexto}\n\nPERGUNTA:\n{pergunta}",
                },
            ],
            temperature=temperature,
            top_p=1.0,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    async def reformular_pergunta(
        self,
        *,
        system_prompt: str,
        pergunta: str,
        max_tokens: int = 100,
    ) -> str:
        """Reformula a pergunta original para melhorar a busca vetorial."""
        resp = await self._client.chat.completions.create(
            model=self._completion_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pergunta},
            ],
            temperature=0.0,
            top_p=1.0,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or pergunta).strip()

    async def aclose(self) -> None:
        await self._client.close()


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    """Cliente default — usa OPEN_AI_KEY do env (chave da Lello)."""
    logger.info(
        f"Inicializando LLMClient default (embedding={config.EMBEDDING_MODEL}, "
        f"completion={config.COMPLETION_MODEL})"
    )
    return LLMClient(
        api_key=config.OPEN_AI_KEY,
        embedding_model=config.EMBEDDING_MODEL,
        completion_model=config.COMPLETION_MODEL,
    )


# Cache de clientes por chave (clientes com chave própria).
# Usa hash da chave como key para não vazar a chave nos logs/repr do cache.
@lru_cache(maxsize=64)
def _get_llm_client_for_key(api_key: str) -> LLMClient:
    logger.info(
        f"Inicializando LLMClient com chave OpenAI dedicada (hash="
        f"{hash(api_key) & 0xFFFF:04x}, embedding={config.EMBEDDING_MODEL})"
    )
    return LLMClient(
        api_key=api_key,
        embedding_model=config.EMBEDDING_MODEL,
        completion_model=config.COMPLETION_MODEL,
    )


def get_llm_client_for_tenant(tenant_config) -> LLMClient:
    """
    Resolve o cliente LLM apropriado para um tenant.

    - Se `tenant_config.openai.mode == 'custom'` e há `api_key`, usa a
      chave do cliente (cliente paga o consumo).
    - Senão, cai no cliente default (chave da Lello).

    O parâmetro `tenant_config` não é tipado para evitar import circular
    (TenantConfig importaria api.llm que importaria api.tenants.models).
    """
    cfg = getattr(tenant_config, "openai", None)
    if cfg is not None and cfg.mode == "custom" and cfg.api_key:
        return _get_llm_client_for_key(cfg.api_key)
    return get_llm_client()
