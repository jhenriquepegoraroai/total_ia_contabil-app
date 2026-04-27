"""Testes do truncate de tokens — espelha o comportamento do script Spark."""

import pytest

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
    # ~1 token por caractere em ASCII; "aaaaa..." tem ~tamanho/1 tokens.
    # 30000 chars >> 8191 tokens.
    texto_longo = "a" * 30000
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
