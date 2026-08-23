"""Testes do truncate de tokens — espelha o comportamento do script Spark."""


from ingestion.chunking import (
    EMBEDDING_MAX_TOKENS,
    contar_tokens,
    truncar_para_limite_tokens,
)


def test_texto_curto_nao_e_truncado():
    texto = "Olá mundo, isto é um teste."
    assert truncar_para_limite_tokens(texto) == texto


def test_texto_vazio_retorna_vazio():
    assert truncar_para_limite_tokens("") == ""


def test_texto_extremamente_longo_e_truncado():
    # NÃO usar "a" * N: o BPE do text-embedding-3-large compacta repetições
    # (30000 'a's vira ~3750 tokens). Precisa texto diverso para exceder
    # EMBEDDING_MAX_TOKENS (8191).
    import random
    import string

    random.seed(0)
    palavras = [
        "".join(random.choices(string.ascii_lowercase, k=5))
        for _ in range(15000)
    ]
    texto_longo = " ".join(palavras)
    assert contar_tokens(texto_longo) > EMBEDDING_MAX_TOKENS  # sanidade

    truncado = truncar_para_limite_tokens(texto_longo)

    assert len(truncado) < len(texto_longo)
    assert contar_tokens(truncado) <= EMBEDDING_MAX_TOKENS


def test_boundary_exato_no_limite():
    """Texto com EMBEDDING_MAX_TOKENS tokens exatos NÃO deve ser truncado."""
    # Construir um texto controlado: repetimos uma palavra simples até atingir
    # exatamente o limite.
    palavra = "teste "  # ~2 tokens
    texto = palavra * 5000  # mais que 8191 tokens
    truncado = truncar_para_limite_tokens(texto, max_tokens=EMBEDDING_MAX_TOKENS)
    assert contar_tokens(truncado) <= EMBEDDING_MAX_TOKENS


def test_max_tokens_customizado():
    texto = "Bom dia, esta é uma frase de exemplo razoavelmente longa para testar."
    truncado = truncar_para_limite_tokens(texto, max_tokens=5)
    assert contar_tokens(truncado) <= 5


def test_idempotente_quando_dentro_do_limite():
    texto = "Frase pequena."
    a = truncar_para_limite_tokens(texto)
    b = truncar_para_limite_tokens(a)
    assert a == b == texto
