"""
Geração de embeddings via OpenAI — batch + retry com backoff exponencial.

Estratégia (espelha o script Spark da Lello em comportamento):
  - Cada chamada à API processa um batch de 100 chunks (input array).
  - Em 429 (rate limit), pausa global de 60s e re-tenta o batch.
  - Em outros erros, faz até 3 retries com backoff exponencial.
  - Após esgotar retries, cai em modo per-chunk: tenta cada chunk individualmente
    para isolar o que de fato é problemático e não perder o batch inteiro.
  - Chunks que continuam falhando são marcados com `embedding=None` e o pipeline
    os contabiliza em `qtde_erros` da auditoria.

A API `text-embedding-3-large` aceita até 2048 inputs por chamada e até 8191
tokens por input (já garantido pelo `chunking.truncar_para_limite_tokens`).
"""

import asyncio
from dataclasses import dataclass

from loguru import logger
from openai import AsyncOpenAI, APIStatusError, RateLimitError

from api import config


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Resultado de uma geração — index original + vetor (None se falhou)."""

    index: int
    embedding: list[float] | None
    erro: str | None = None


class EmbeddingClient:
    """Cliente OpenAI assíncrono com batch + retry."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "text-embedding-3-large",
        max_retries: int = 3,
        timeout_seconds: int = 30,
        rate_limit_pause_seconds: int = 60,
    ):
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._max_retries = max_retries
        self._rate_limit_pause = rate_limit_pause_seconds

    async def embed_batch(self, paragraphs: list[str]) -> list[EmbeddingResult]:
        """
        Gera embeddings para um batch.

        Em sucesso: retorna lista de mesmo tamanho com vetores.
        Em falha total: retorna lista com `embedding=None` e `erro` preenchido.

        A função NÃO levanta — sempre retorna uma lista, para que o pipeline
        possa contabilizar erros e seguir.
        """
        if not paragraphs:
            return []

        # 1. Tentativa em batch único.
        for tentativa in range(1, self._max_retries + 1):
            try:
                resp = await self._client.embeddings.create(
                    model=self._model,
                    input=paragraphs,
                )
                vetores = [d.embedding for d in resp.data]
                return [EmbeddingResult(i, vetores[i]) for i in range(len(paragraphs))]

            except RateLimitError as exc:
                logger.warning(
                    f"OpenAI rate limit (tentativa {tentativa}/{self._max_retries}). "
                    f"Pausando {self._rate_limit_pause}s. Detalhe: {exc}"
                )
                await asyncio.sleep(self._rate_limit_pause)

            except APIStatusError as exc:
                # 5xx servidor; 4xx (não-429) provavelmente é input ruim → cair pra per-chunk
                if 500 <= exc.status_code < 600 and tentativa < self._max_retries:
                    backoff = 2**tentativa
                    logger.warning(
                        f"OpenAI {exc.status_code} (tentativa {tentativa}/{self._max_retries}). "
                        f"Backoff {backoff}s."
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error(
                        f"OpenAI {exc.status_code} permanente. Caindo em modo per-chunk. "
                        f"Detalhe: {exc}"
                    )
                    break

            except Exception as exc:
                if tentativa < self._max_retries:
                    backoff = 2**tentativa
                    logger.warning(
                        f"Erro OpenAI (tentativa {tentativa}/{self._max_retries}): {exc}. "
                        f"Backoff {backoff}s."
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.exception(f"Erro OpenAI esgotou retries. Caindo em per-chunk: {exc}")
                    break
        else:
            # for-else: rate limit estourou todas as tentativas
            return self._falha_total(paragraphs, "rate_limit_esgotado")

        # 2. Fallback per-chunk — isola o(s) problemático(s).
        return await self._embed_per_chunk(paragraphs)

    async def _embed_per_chunk(self, paragraphs: list[str]) -> list[EmbeddingResult]:
        """Última tentativa: 1 chunk por chamada. Os que falharem ficam None."""
        resultados: list[EmbeddingResult] = []
        for i, p in enumerate(paragraphs):
            try:
                resp = await self._client.embeddings.create(
                    model=self._model,
                    input=[p],
                )
                resultados.append(EmbeddingResult(i, resp.data[0].embedding))
            except Exception as exc:
                logger.warning(f"Chunk {i} falhou em per-chunk: {exc}")
                resultados.append(EmbeddingResult(i, None, erro=str(exc)))
        return resultados

    @staticmethod
    def _falha_total(paragraphs: list[str], motivo: str) -> list[EmbeddingResult]:
        return [EmbeddingResult(i, None, erro=motivo) for i in range(len(paragraphs))]

    async def aclose(self) -> None:
        await self._client.close()


def cliente_padrao(api_key: str | None = None) -> EmbeddingClient:
    """
    Constrói EmbeddingClient. Se `api_key` for passado, usa essa chave
    (caso de tenant com chave própria). Senão, usa a OPEN_AI_KEY do env
    (chave da Lello).
    """
    return EmbeddingClient(
        api_key=api_key or config.OPEN_AI_KEY,
        model=config.EMBEDDING_MODEL,
        max_retries=config.INGESTION_OPENAI_MAX_RETRIES,
        timeout_seconds=config.INGESTION_OPENAI_TIMEOUT,
    )
