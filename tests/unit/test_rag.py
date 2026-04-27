"""
Testes do orquestrador RAG (com LLM e DataSource mockados).

Cobre os caminhos:
  - resposta padrão (atalho)
  - esclarecimento
  - dados estruturados (cat 0)
  - pattern (cat 51, 65, 67)
  - busca por embeddings (default)
  - sem documento → mensagem_nao_encontrada
"""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from api.core.rag import responder


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.classificar.return_value = "0"
    llm.gerar_resposta.return_value = "Resposta gerada pelo GPT."
    llm.embed_query.return_value = [0.1] * 3072
    llm.reformular_pergunta.return_value = "pergunta reformulada"
    return llm


@pytest.fixture
def mock_datasource():
    ds = AsyncMock()
    ds.tenant_id = "test_tenant"
    ds.busca_similaridade.return_value = []
    ds.buscar_paragrafos_por_pattern.return_value = []
    ds.buscar_dados_estruturados.return_value = []
    ds.buscar_data_mais_recente.return_value = None
    return ds


# =============================================================================
# Atalhos: resposta padrão e esclarecimento
# =============================================================================
@pytest.mark.asyncio
async def test_resposta_padrao_atalho(tenant_config_factory, mock_llm, mock_datasource):
    config = tenant_config_factory(
        respostas_padrao={5: "Resposta fixa pra cat 5."},
    )
    mock_llm.classificar.return_value = "5"

    resp = await responder(
        pergunta="qualquer",
        referencia="111",
        tenant_config=config,
        datasource=mock_datasource,
        llm=mock_llm,
    )
    assert resp.resposta == "Resposta fixa pra cat 5."
    assert resp.via == "resposta_padrao"
    # Não deve chamar GPT nem datasource quando há atalho.
    mock_llm.gerar_resposta.assert_not_called()
    mock_datasource.busca_similaridade.assert_not_called()


@pytest.mark.asyncio
async def test_esclarecimento(tenant_config_factory, mock_llm, mock_datasource):
    config = tenant_config_factory(
        prompt_esclarecimento="Por favor, especifique melhor sua pergunta.",
    )
    mock_llm.classificar.return_value = "-1"

    resp = await responder(
        pergunta="vaga",
        referencia="111",
        tenant_config=config,
        datasource=mock_datasource,
        llm=mock_llm,
    )
    assert resp.resposta == "Por favor, especifique melhor sua pergunta."
    assert resp.via == "esclarecimento"


# =============================================================================
# Dados estruturados
# =============================================================================
@pytest.mark.asyncio
async def test_dados_estruturados_cat_0(tenant_config_factory, mock_llm, mock_datasource):
    config = tenant_config_factory(
        schemas_estruturados={"condominios": "condominios", "areas": "condominio_areas"},
        prompts_por_categoria={0: "Use os dados cadastrais."},
    )
    mock_llm.classificar.return_value = "0"
    mock_datasource.buscar_dados_estruturados.return_value = [
        {"tenant_id": "x", "referencia": "111", "nome": "Cond Teste", "cnpj": "12345678901234"}
    ]

    resp = await responder(
        pergunta="qual o cnpj?",
        referencia="111",
        tenant_config=config,
        datasource=mock_datasource,
        llm=mock_llm,
    )
    assert resp.via == "estruturado"
    assert resp.categoria == 0
    mock_datasource.buscar_dados_estruturados.assert_awaited_once_with("condominios", "111")
    mock_llm.gerar_resposta.assert_awaited_once()


@pytest.mark.asyncio
async def test_dados_estruturados_vazio_retorna_resposta_sem_documento(
    tenant_config_factory, mock_llm, mock_datasource
):
    config = tenant_config_factory(
        schemas_estruturados={"condominios": "condominios"},
        resposta_sem_documento="Sem dados pra essa referência.",
    )
    mock_llm.classificar.return_value = "0"
    mock_datasource.buscar_dados_estruturados.return_value = []

    resp = await responder(
        pergunta="x",
        referencia="111",
        tenant_config=config,
        datasource=mock_datasource,
        llm=mock_llm,
    )
    assert resp.resposta == "Sem dados pra essa referência."
    mock_llm.gerar_resposta.assert_not_called()


# =============================================================================
# Pattern (assembleia, edital)
# =============================================================================
@pytest.mark.asyncio
async def test_categoria_assembleia_usa_pattern(
    tenant_config_factory, mock_llm, mock_datasource
):
    config = tenant_config_factory()
    mock_llm.classificar.return_value = "51"
    mock_datasource.buscar_paragrafos_por_pattern.return_value = [
        {
            "file_name": "ATA_2024-03-15.pdf",
            "record_id": "p1_b1",
            "paragraph": "Pauta da assembleia: bla bla.",
            "data_valida": date(2024, 3, 15),
        }
    ]

    resp = await responder(
        pergunta="resumo da última assembleia",
        referencia="111",
        tenant_config=config,
        datasource=mock_datasource,
        llm=mock_llm,
    )
    assert resp.via == "pattern"
    assert resp.categoria == 51
    assert len(resp.citacoes) == 1
    assert resp.citacoes[0].file_name == "ATA_2024-03-15.pdf"
    mock_datasource.buscar_paragrafos_por_pattern.assert_awaited_once()


@pytest.mark.asyncio
async def test_categoria_edital_data_pula_geracao(
    tenant_config_factory, mock_llm, mock_datasource
):
    config = tenant_config_factory()
    mock_llm.classificar.return_value = "67"
    mock_datasource.buscar_data_mais_recente.return_value = date(2024, 3, 15)

    resp = await responder(
        pergunta="quando é o próximo edital?",
        referencia="111",
        tenant_config=config,
        datasource=mock_datasource,
        llm=mock_llm,
    )
    assert "15/03/2024" in resp.resposta
    assert resp.via == "pattern"
    # Não chamou geração de resposta — é determinístico.
    mock_llm.gerar_resposta.assert_not_called()


# =============================================================================
# Embeddings (default)
# =============================================================================
@pytest.mark.asyncio
async def test_busca_embeddings_default(tenant_config_factory, mock_llm, mock_datasource):
    config = tenant_config_factory()
    # Categoria desconhecida (123) cai no default.
    mock_llm.classificar.return_value = "123"
    mock_datasource.busca_similaridade.return_value = [
        {
            "file_name": "regulamento.pdf",
            "record_id": "p2_b3",
            "paragraph": "Animais permitidos com guia...",
            "data_valida": date(2023, 1, 10),
            "similarity": 0.87,
        }
    ]

    resp = await responder(
        pergunta="posso ter cachorro?",
        referencia="111",
        tenant_config=config,
        datasource=mock_datasource,
        llm=mock_llm,
    )
    assert resp.via == "embeddings"
    assert resp.categoria == 123
    assert len(resp.citacoes) == 1
    mock_llm.embed_query.assert_awaited_once()


@pytest.mark.asyncio
async def test_embeddings_zero_resultados_retorna_nao_encontrada(
    tenant_config_factory, mock_llm, mock_datasource
):
    config = tenant_config_factory(
        mensagem_nao_encontrada="Não achei essa informação.",
    )
    mock_llm.classificar.return_value = "999"
    mock_datasource.busca_similaridade.return_value = []

    resp = await responder(
        pergunta="qualquer coisa",
        referencia="111",
        tenant_config=config,
        datasource=mock_datasource,
        llm=mock_llm,
    )
    assert resp.resposta == "Não achei essa informação."
    mock_llm.gerar_resposta.assert_not_called()


# =============================================================================
# Pergunta vazia
# =============================================================================
@pytest.mark.asyncio
async def test_pergunta_vazia(tenant_config_factory, mock_llm, mock_datasource):
    config = tenant_config_factory(mensagem_nao_encontrada="msg")

    resp = await responder(
        pergunta="   ",
        referencia="111",
        tenant_config=config,
        datasource=mock_datasource,
        llm=mock_llm,
    )
    assert resp.resposta == "msg"
    mock_llm.classificar.assert_not_called()
