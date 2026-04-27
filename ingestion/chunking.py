"""
Truncate de tokens para o modelo de embeddings.

Espelha exatamente a função `corta_para_limite_tokens` do script Spark
original da Lello:

    encoding = tiktoken.encoding_for_model("text-embedding-3-large")
    MAX_TOKENS = 8191

    def corta_para_limite_tokens(texto, encoding, max_tokens):
        tokens = encoding.encode(texto)
        if len(tokens) > max_tokens:
            tokens = tokens[:max_tokens]
            return encoding.decode(tokens)
        return texto

A nossa versão é igual em comportamento, com cache do encoder e type hints.
"""

from functools import lru_cache

import tiktoken

# Limite oficial do modelo `text-embedding-3-large`.
EMBEDDING_MAX_TOKENS = 8191
EMBEDDING_MODEL = "text-embedding-3-large"


@lru_cache(maxsize=4)
def _get_encoding(model: str = EMBEDDING_MODEL):
    """Cache do encoder — `tiktoken.encoding_for_model` é caro pra criar."""
    return tiktoken.encoding_for_model(model)


def truncar_para_limite_tokens(
    texto: str,
    max_tokens: int = EMBEDDING_MAX_TOKENS,
    model: str = EMBEDDING_MODEL,
) -> str:
    """
    Trunca o texto para `max_tokens` tokens. Se já está abaixo, retorna inalterado.

    Não loga. Não levanta. Texto vazio retorna vazio.
    """
    if not texto:
        return ""

    encoding = _get_encoding(model)
    tokens = encoding.encode(texto)
    if len(tokens) <= max_tokens:
        return texto

    truncado = tokens[:max_tokens]
    return encoding.decode(truncado)


def contar_tokens(texto: str, model: str = EMBEDDING_MODEL) -> int:
    """Quantos tokens tem um texto. Útil para logging/cost estimation."""
    if not texto:
        return 0
    return len(_get_encoding(model).encode(texto))
