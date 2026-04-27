"""Testes do classificador (com LLM mockado — não chama OpenAI de verdade)."""

from unittest.mock import AsyncMock

import pytest

from api.core.classifier import classificar_pergunta


@pytest.mark.asyncio
async def test_extrai_numero_simples(tenant_config_factory):
    config = tenant_config_factory()
    llm = AsyncMock()
    llm.classificar.return_value = "0"

    cat = await classificar_pergunta("qual o nome do síndico?", config, llm)
    assert cat == 0


@pytest.mark.asyncio
async def test_extrai_numero_em_texto(tenant_config_factory):
    config = tenant_config_factory()
    llm = AsyncMock()
    llm.classificar.return_value = "Categoria 51"

    cat = await classificar_pergunta("qual a última assembleia?", config, llm)
    assert cat == 51


@pytest.mark.asyncio
async def test_extrai_numero_negativo(tenant_config_factory):
    config = tenant_config_factory()
    llm = AsyncMock()
    llm.classificar.return_value = "-1"

    cat = await classificar_pergunta("uma pergunta vaga", config, llm)
    assert cat == -1


@pytest.mark.asyncio
async def test_resposta_sem_numero_retorna_none(tenant_config_factory):
    config = tenant_config_factory()
    llm = AsyncMock()
    llm.classificar.return_value = "não sei"

    cat = await classificar_pergunta("qualquer coisa", config, llm)
    assert cat is None


@pytest.mark.asyncio
async def test_pergunta_vazia_retorna_none(tenant_config_factory):
    config = tenant_config_factory()
    llm = AsyncMock()

    cat = await classificar_pergunta("", config, llm)
    assert cat is None
    # Não deve nem chamar o LLM com pergunta vazia.
    llm.classificar.assert_not_called()


@pytest.mark.asyncio
async def test_classificador_usa_temperature_zero(tenant_config_factory):
    """O wrapper LLM já força temperature=0 — verificamos que classificar_pergunta
    chama `llm.classificar` (não `gerar_resposta` nem `embed_query`)."""
    config = tenant_config_factory()
    llm = AsyncMock()
    llm.classificar.return_value = "0"

    await classificar_pergunta("teste", config, llm)
    llm.classificar.assert_called_once()
    llm.gerar_resposta.assert_not_called()
