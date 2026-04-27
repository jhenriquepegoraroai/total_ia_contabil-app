"""Testes do RawChunk e da factory de connectors."""

from datetime import date

import pytest

from ingestion.connectors import criar_connector
from ingestion.connectors.base import RawChunk
from ingestion.connectors.pdf_folder import _extrair_data_do_nome


# =============================================================================
# RawChunk
# =============================================================================
def test_raw_chunk_aceita_dados_validos():
    chunk = RawChunk(
        file_name="ata.pdf",
        record_id="p1_b1",
        paragraph="Texto do parágrafo.",
        data_valida=date(2024, 3, 15),
    )
    assert chunk.file_name == "ata.pdf"
    assert chunk.data_valida == date(2024, 3, 15)


def test_raw_chunk_rejeita_paragraph_vazio():
    with pytest.raises(ValueError):
        RawChunk(file_name="x.pdf", record_id="r", paragraph="")


def test_raw_chunk_rejeita_paragraph_so_espacos():
    with pytest.raises(ValueError):
        RawChunk(file_name="x.pdf", record_id="r", paragraph="   \n  ")


def test_raw_chunk_rejeita_file_name_vazio():
    with pytest.raises(ValueError):
        RawChunk(file_name="", record_id="r", paragraph="x")


def test_raw_chunk_rejeita_record_id_vazio():
    with pytest.raises(ValueError):
        RawChunk(file_name="x.pdf", record_id="", paragraph="x")


def test_raw_chunk_e_imutavel():
    chunk = RawChunk(file_name="x.pdf", record_id="r", paragraph="t")
    with pytest.raises((AttributeError, TypeError)):
        chunk.file_name = "y.pdf"  # type: ignore[misc]


# =============================================================================
# Extração de data do nome
# =============================================================================
def test_extrai_data_iso():
    assert _extrair_data_do_nome("ATA_2024-03-15.pdf") == date(2024, 3, 15)


def test_extrai_data_com_underscore():
    assert _extrair_data_do_nome("ATA_2024_03_15.pdf") == date(2024, 3, 15)


def test_extrai_data_brasileira():
    assert _extrair_data_do_nome("Edital-15-03-2024.pdf") == date(2024, 3, 15)


def test_data_ausente_retorna_none():
    assert _extrair_data_do_nome("Documento_sem_data.pdf") is None


# =============================================================================
# Factory
# =============================================================================
def test_factory_pdf_folder_requer_pasta_existente(tmp_path):
    pasta = tmp_path / "vazia"
    pasta.mkdir()
    conn = criar_connector("pdf_folder", path=str(pasta))
    assert conn.describe().startswith("pdf_folder:")


def test_factory_pdf_folder_falha_se_pasta_nao_existe(tmp_path):
    with pytest.raises(FileNotFoundError):
        criar_connector("pdf_folder", path=str(tmp_path / "nao_existe"))


def test_factory_postgres_levanta_not_implemented():
    with pytest.raises(NotImplementedError):
        criar_connector("postgres", connection_string="postgresql://x")


def test_factory_desconhecido_levanta_value_error():
    with pytest.raises(ValueError, match="desconhecido"):
        criar_connector("ftp", path="x")
