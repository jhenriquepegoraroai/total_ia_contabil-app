"""
Wrapper OpenAI — embedding de query (single) + chat completion.

Para o pipeline de ingestão (batch), ver `ingestion/embeddings.py`.
Aqui é só o caminho da request HTTP — single embedding por pergunta,
single completion por resposta.

REGRA CRÍTICA (RULES.md #16): classificação usa `temperature=0` e `top_p=1`.
Geração pode usar temperature configurável por tenant (default 0.2).

NOTA — gpt-5.2 e outros modelos novos da OpenAI:
  • param renomeado de `max_tokens` para `max_completion_tokens`
  • `temperature` aceita apenas o default (1) — qualquer outro valor é erro
  • `top_p` aceita apenas o default (1)
Por isso esta classe detecta se o modelo é "moderno" (gpt-5.x, o-series, gpt-4.1+)
e ajusta a chamada. Para modelos antigos (gpt-4o, gpt-4-turbo etc), continua
mandando `max_tokens` + `temperature` + `top_p`.
"""

from functools import lru_cache

from loguru import logger
from openai import AsyncOpenAI

from api import config


def _modelo_moderno(model: str) -> bool:
    """
    Detecta se o modelo exige a API nova (max_completion_tokens, sem temperature
    customizada). Heurística: gpt-5.x, o1/o3/o4 (reasoning), gpt-4.1+.
    Lista cresce — em caso de novos modelos, basta adicionar prefixos aqui.
    """
    m = (model or "").lower()
    if m.startswith(("gpt-5", "o1", "o3", "o4")):
        return True
    if m.startswith("gpt-4.") and not m.startswith("gpt-4.0"):
        # gpt-4.1, 4.5, etc — todos modernos.
        return True
    return False


class LLMClient:
    """Wrapper assíncrono — uma instância por processo (singleton via lru_cache)."""

    def __init__(self, api_key: str, *, embedding_model: str, completion_model: str):
        self._client = AsyncOpenAI(api_key=api_key, timeout=30)
        self._embedding_model = embedding_model
        self._completion_model = completion_model
        self._modelo_moderno = _modelo_moderno(completion_model)

    async def embed_query(self, texto: str) -> list[float]:
        """Embedding de uma única pergunta. Trunca texto vazio e levanta."""
        if not texto or not texto.strip():
            raise ValueError("texto vazio")
        resp = await self._client.embeddings.create(
            model=self._embedding_model,
            input=[texto.strip()],
        )
        return resp.data[0].embedding

    def _kwargs_completion(
        self,
        *,
        max_tokens: int,
        temperature: float | None,
    ) -> dict:
        """Monta kwargs corretos conforme a geração do modelo."""
        kwargs: dict = {"model": self._completion_model}
        if self._modelo_moderno:
            kwargs["max_completion_tokens"] = max_tokens
            # Modelos modernos só aceitam temperature=1 (default).
            # Não enviamos para evitar erro 400.
        else:
            kwargs["max_tokens"] = max_tokens
            if temperature is not None:
                kwargs["temperature"] = temperature
            kwargs["top_p"] = 1.0
        return kwargs

    async def classificar(
        self,
        *,
        system_prompt: str,
        pergunta: str,
        max_tokens: int = 16,
    ) -> str:
        """
        Classificação. Em modelos antigos é determinística (temperature=0).
        Em modelos modernos (gpt-5+), `temperature` é fixo em 1 — ainda assim
        a probabilidade do número da categoria sair certo é alta com
        max_completion_tokens=16.
        """
        kwargs = self._kwargs_completion(max_tokens=max_tokens, temperature=0.0)
        resp = await self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pergunta},
            ],
            **kwargs,
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
        """Geração com contexto RAG. Temperature aplicada apenas em modelos antigos."""
        kwargs = self._kwargs_completion(max_tokens=max_tokens, temperature=temperature)
        resp = await self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"CONTEXTO:\n{contexto}\n\nPERGUNTA:\n{pergunta}",
                },
            ],
            **kwargs,
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
        kwargs = self._kwargs_completion(max_tokens=max_tokens, temperature=0.0)
        resp = await self._client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pergunta},
            ],
            **kwargs,
        )
        return (resp.choices[0].message.content or pergunta).strip()

    @property
    def async_client(self):
        """
        Acesso ao `AsyncOpenAI` interno, para casos que precisam chamar
        endpoints que não estão no wrapper (ex: pipelines de atas que usam
        modelos diferentes do completion_model padrão, ou Whisper).
        """
        return self._client

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
    """
    cfg = getattr(tenant_config, "openai", None)
    if cfg is not None and cfg.mode == "custom" and cfg.api_key:
        return _get_llm_client_for_key(cfg.api_key)
    return get_llm_client()
