"""
Referência de condomínio na ingestão.

O bug que estes testes fecham: um job de fonte PDF disparado sem referência
gravava todos os embeddings sob o condomínio literal `"0"`
(`referencia or "0"`). Não havia erro nem aviso — o job terminava 'done' e os
documentos ficavam invisíveis para qualquer pergunta, porque o chat filtra
pela referência real do usuário.

A falha ficava escondida por dois motivos que se somam: nenhum connector de
PDF preenche `referencia` no chunk, e o `PdfUploadConfig` documenta extração
da referência pelo nome do arquivo que nunca foi implementada.
"""

import pytest

from api.admin.ingestion_service import _exige_referencia_no_job


# =============================================================================
# Fontes de PDF — nunca resolvem referência sozinhas
# =============================================================================
@pytest.mark.parametrize("tipo", ["pdf_upload", "s3", "azure_blob"])
def test_fontes_de_pdf_sempre_exigem_referencia(tipo):
    """
    Nem `PdfFolderConnector` nem `StoragePdfConnector` preenchem `referencia`
    no chunk. Para eles o valor só pode vir do disparo do job.
    """
    assert _exige_referencia_no_job(tipo, {}) is True


def test_pdf_upload_com_referencia_default_ainda_exige():
    """
    `PdfUploadConfig.referencia_default` existe na config e NÃO é consumido
    pelo caminho de PDF — só chega aos connectors de Excel e CSV. Confiar
    nele aqui reintroduziria o bug por outro caminho.
    """
    assert _exige_referencia_no_job("pdf_upload", {"referencia_default": "12345"}) is True


# =============================================================================
# Fontes tabulares — resolvem por linha ou por default da fonte
# =============================================================================
def test_coluna_referencia_dispensa_referencia_no_job():
    config = {"coluna_texto": "texto", "coluna_referencia": "cod_condominio"}
    assert _exige_referencia_no_job("excel_upload", config) is False


def test_referencia_default_da_fonte_dispensa():
    config = {"coluna_texto": "texto", "referencia_default": "12345"}
    assert _exige_referencia_no_job("csv_upload", config) is False


def test_postgres_sem_nenhuma_das_duas_ainda_exige():
    assert _exige_referencia_no_job("postgres", {"table": "docs"}) is True


# =============================================================================
# Config vinda como texto — defesa contra driver legado
# =============================================================================
def test_config_json_como_string_e_interpretada():
    assert _exige_referencia_no_job("excel_upload", '{"coluna_referencia": "cod"}') is False


def test_config_json_invalida_cai_para_o_lado_seguro():
    """Na dúvida, exigir referência: o custo de pedir é uma mensagem de erro."""
    assert _exige_referencia_no_job("excel_upload", "{isso nao e json") is True
    assert _exige_referencia_no_job("excel_upload", None) is True
