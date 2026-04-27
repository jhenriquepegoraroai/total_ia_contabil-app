"""Testes do RawChunk, factory e dos connectors concretos.

Connectors testados em isolamento (sem DB / sem rede):
  - PdfFolderConnector: extração de data
  - PostgresConnector: validação anti-injeção, build_query, row mapping
  - CsvFolderConnector: leitura de arquivo, encoding, default ref, datas
  - ExcelFolderConnector: leitura via openpyxl

Não cobre `_read_async` do Postgres nem `read()` do S3/Azure — esses
exigem DB / cloud reais e ficam para integration tests.
"""

import csv as csv_mod
from datetime import date

import pytest

from ingestion.connectors import criar_connector
from ingestion.connectors.base import RawChunk
from ingestion.connectors.csv_files import CsvFolderConnector
from ingestion.connectors.pdf_folder import _extrair_data_do_nome
from ingestion.connectors.postgres import PostgresConnector


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
# Extração de data do nome (PdfFolder)
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


def test_factory_postgres_aceita_config_completa():
    """Postgres já implementado: factory só constrói (sem conectar)."""
    conn = criar_connector(
        "postgres",
        host="db.cliente.com",
        port=5432,
        database="docs",
        user="leitor",
        password="x",
        table="documentos",
        coluna_texto="conteudo",
    )
    assert conn.describe() == "postgres:public.documentos"


def test_factory_desconhecido_levanta_value_error():
    with pytest.raises(ValueError, match="desconhecido"):
        criar_connector("ftp", path="x")


# =============================================================================
# PostgresConnector — validação anti-injeção em identificadores
# =============================================================================
class TestPostgresValidacaoIdent:
    """Identificadores SQL (table/coluna) NÃO podem ser parametrizados via
    asyncpg, então o connector valida com regex restrita. Esse guard é a
    única defesa contra `; DROP TABLE` em casos onde o admin cola um
    nome malicioso vindo da UI."""

    BASE = dict(
        host="h",
        port=5432,
        database="d",
        user="u",
        password="p",
        coluna_texto="texto",
    )

    @pytest.mark.parametrize(
        "valor_ruim",
        [
            "documentos; DROP TABLE users",
            "doc'umentos",
            'doc"umentos',
            "documentos--",
            "1documentos",  # começa com dígito
            "-doc",
            "doc com espaço",
        ],
    )
    def test_table_invalida_e_rejeitada(self, valor_ruim):
        with pytest.raises(ValueError, match="Identificador SQL inválido"):
            PostgresConnector(table=valor_ruim, **self.BASE)

    def test_table_e_custom_query_ambos_vazios_levanta_outro_erro(self):
        # Sem nenhum dos dois → guard diferente (não-ident) dispara primeiro.
        with pytest.raises(ValueError, match="custom_query"):
            PostgresConnector(host="h", port=5432, database="d",
                              user="u", password="p")

    @pytest.mark.parametrize("valor_ruim", ["col;ruim", "1coluna", "col-erro"])
    def test_coluna_referencia_invalida_e_rejeitada(self, valor_ruim):
        with pytest.raises(ValueError, match="Identificador SQL inválido"):
            PostgresConnector(table="ok", coluna_referencia=valor_ruim, **self.BASE)

    def test_schema_invalido_e_rejeitado(self):
        with pytest.raises(ValueError, match="Identificador SQL inválido"):
            PostgresConnector(table="ok", schema_name="public; DROP", **self.BASE)

    def test_aceita_identificadores_validos(self):
        conn = PostgresConnector(
            table="documentos_clientes",
            schema_name="dados",
            coluna_referencia="cond_id",
            coluna_data="data_doc",
            **self.BASE,
        )
        assert conn.describe() == "postgres:dados.documentos_clientes"


# =============================================================================
# PostgresConnector — modos de query
# =============================================================================
class TestPostgresBuildQuery:
    BASE = dict(host="h", port=5432, database="d", user="u", password="p")

    def test_modo_tabela_monta_select_com_aliases(self):
        conn = PostgresConnector(
            table="documentos",
            coluna_texto="conteudo",
            coluna_referencia="cond_id",
            coluna_data="data_doc",
            **self.BASE,
        )
        sql, _ = conn._build_query()
        assert '"conteudo" AS paragraph' in sql
        assert '"cond_id" AS referencia' in sql
        assert '"data_doc" AS data_valida' in sql
        assert 'FROM "public"."documentos"' in sql

    def test_modo_tabela_so_texto_obrigatorio(self):
        conn = PostgresConnector(table="docs", coluna_texto="t", **self.BASE)
        sql, _ = conn._build_query()
        assert '"t" AS paragraph' in sql
        # sem refs/data se não foram passadas
        assert "AS referencia" not in sql
        assert "AS data_valida" not in sql

    def test_modo_custom_query_passa_sql_intacto(self):
        custom = "SELECT id AS record_id, condominio_id AS referencia, txt AS paragraph FROM v"
        conn = PostgresConnector(custom_query=custom, **self.BASE)
        sql, cols = conn._build_query()
        assert sql == custom
        assert cols["record_id"] == "record_id"
        assert cols["referencia"] == "referencia"

    def test_falta_table_e_custom_levanta(self):
        with pytest.raises(ValueError, match="custom_query"):
            PostgresConnector(**self.BASE)


# =============================================================================
# PostgresConnector — mapeamento linha → RawChunk
# =============================================================================
class TestPostgresRowToChunk:
    """`_row_to_chunk` aceita dict-like (asyncpg.Record é convertido para
    dict). Testar o mapeamento sem precisar de DB."""

    def _make_conn(self):
        return PostgresConnector(
            host="h", port=5432, database="d", user="u", password="p",
            table="docs", coluna_texto="t",
        )

    def test_modo_tabela_usa_table_como_file_name(self):
        conn = self._make_conn()
        cols = {
            "paragraph": "paragraph", "referencia": "referencia",
            "data_valida": "data_valida", "file_name": None, "record_id": None,
        }
        chunk = conn._row_to_chunk(
            {"paragraph": "texto", "referencia": "12345", "data_valida": date(2024, 1, 1)},
            index=0, cols=cols,
        )
        assert chunk is not None
        assert chunk.paragraph == "texto"
        assert chunk.referencia == "12345"
        assert chunk.data_valida == date(2024, 1, 1)
        assert chunk.file_name == "public.docs"
        assert chunk.record_id == "row0"

    def test_paragraph_vazio_devolve_none(self):
        conn = self._make_conn()
        cols = {
            "paragraph": "paragraph", "referencia": None,
            "data_valida": None, "file_name": None, "record_id": None,
        }
        assert conn._row_to_chunk({"paragraph": "   "}, 0, cols) is None
        assert conn._row_to_chunk({"paragraph": None}, 0, cols) is None

    def test_custom_query_usa_record_id_e_file_name_da_query(self):
        conn = PostgresConnector(
            host="h", port=5432, database="d", user="u", password="p",
            custom_query="SELECT ...",
        )
        cols = {
            "paragraph": "paragraph", "referencia": "referencia",
            "data_valida": "data_valida",
            "file_name": "file_name", "record_id": "record_id",
        }
        chunk = conn._row_to_chunk(
            {
                "paragraph": "conteudo", "referencia": "999",
                "data_valida": None, "file_name": "doc-X.pdf", "record_id": "abc-42",
            },
            index=5, cols=cols,
        )
        assert chunk is not None
        assert chunk.file_name == "doc-X.pdf"
        assert chunk.record_id == "abc-42"


# =============================================================================
# CsvFolderConnector
# =============================================================================
class TestCsvFolder:
    def _escrever_csv(self, path, rows, fieldnames, delimiter=","):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv_mod.DictWriter(f, fieldnames=fieldnames, delimiter=delimiter)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    def test_le_csv_basico_com_todas_as_colunas(self, tmp_path):
        arq = tmp_path / "faq.csv"
        self._escrever_csv(
            arq,
            [
                {"texto": "Pergunta 1", "cond": "111", "data": "2024-03-15"},
                {"texto": "Pergunta 2", "cond": "222", "data": "15/03/2024"},
            ],
            ["texto", "cond", "data"],
        )
        conn = CsvFolderConnector(
            path=str(tmp_path), coluna_texto="texto",
            coluna_referencia="cond", coluna_data="data",
        )
        chunks = list(conn.read())
        assert len(chunks) == 2
        assert chunks[0].paragraph == "Pergunta 1"
        assert chunks[0].referencia == "111"
        assert chunks[0].data_valida == date(2024, 3, 15)
        assert chunks[1].data_valida == date(2024, 3, 15)  # formato BR
        assert chunks[0].record_id == "row2"
        assert chunks[1].record_id == "row3"

    def test_pula_linhas_com_texto_vazio(self, tmp_path):
        arq = tmp_path / "f.csv"
        self._escrever_csv(
            arq,
            [
                {"texto": "ok", "cond": "1"},
                {"texto": "", "cond": "2"},
                {"texto": "   ", "cond": "3"},
                {"texto": "ok2", "cond": "4"},
            ],
            ["texto", "cond"],
        )
        conn = CsvFolderConnector(
            path=str(tmp_path), coluna_texto="texto", coluna_referencia="cond"
        )
        chunks = list(conn.read())
        assert [c.paragraph for c in chunks] == ["ok", "ok2"]

    def test_referencia_default_aplicada_quando_coluna_vazia(self, tmp_path):
        arq = tmp_path / "f.csv"
        self._escrever_csv(
            arq,
            [{"texto": "a", "cond": ""}, {"texto": "b", "cond": "999"}],
            ["texto", "cond"],
        )
        conn = CsvFolderConnector(
            path=str(tmp_path),
            coluna_texto="texto",
            coluna_referencia="cond",
            referencia_default="DEFAULT",
        )
        chunks = list(conn.read())
        assert chunks[0].referencia == "DEFAULT"
        assert chunks[1].referencia == "999"

    def test_delimitador_customizado(self, tmp_path):
        arq = tmp_path / "br.csv"
        with open(arq, "w", encoding="utf-8", newline="") as f:
            f.write("texto;cond\nUm;111\nDois;222\n")
        conn = CsvFolderConnector(
            path=str(tmp_path), coluna_texto="texto",
            coluna_referencia="cond", delimiter=";",
        )
        chunks = list(conn.read())
        assert len(chunks) == 2
        assert chunks[1].referencia == "222"

    def test_coluna_texto_ausente_devolve_zero_chunks(self, tmp_path):
        arq = tmp_path / "f.csv"
        self._escrever_csv(arq, [{"resp": "x"}], ["resp"])
        conn = CsvFolderConnector(path=str(tmp_path), coluna_texto="texto")
        assert list(conn.read()) == []

    def test_pasta_inexistente_levanta(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            CsvFolderConnector(path=str(tmp_path / "nope"), coluna_texto="t")

    def test_coluna_texto_obrigatoria(self, tmp_path):
        with pytest.raises(ValueError):
            CsvFolderConnector(path=str(tmp_path), coluna_texto="")

    def test_data_em_formato_desconhecido_vira_none(self, tmp_path):
        arq = tmp_path / "f.csv"
        self._escrever_csv(
            arq,
            [{"texto": "x", "data": "ontem"}],
            ["texto", "data"],
        )
        conn = CsvFolderConnector(
            path=str(tmp_path), coluna_texto="texto", coluna_data="data"
        )
        chunks = list(conn.read())
        assert chunks[0].data_valida is None


# =============================================================================
# ExcelFolderConnector
# =============================================================================
class TestExcelFolder:
    def _escrever_xlsx(self, path, header, rows):
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(header)
        for r in rows:
            ws.append(r)
        wb.save(str(path))

    def test_le_xlsx_basico(self, tmp_path):
        from ingestion.connectors.excel import ExcelFolderConnector

        arq = tmp_path / "faq.xlsx"
        self._escrever_xlsx(
            arq,
            ["pergunta", "cond", "data"],
            [
                ["Como pagar?", "111", date(2024, 3, 15)],
                ["Onde reclamar?", "222", date(2024, 4, 10)],
            ],
        )
        conn = ExcelFolderConnector(
            path=str(tmp_path),
            coluna_texto="pergunta",
            coluna_referencia="cond",
            coluna_data="data",
        )
        chunks = list(conn.read())
        assert len(chunks) == 2
        assert chunks[0].paragraph == "Como pagar?"
        assert chunks[0].referencia == "111"
        assert chunks[0].data_valida == date(2024, 3, 15)
        assert chunks[0].record_id == "row2"
        assert chunks[1].record_id == "row3"

    def test_pula_linhas_vazias_e_texto_vazio(self, tmp_path):
        from ingestion.connectors.excel import ExcelFolderConnector

        arq = tmp_path / "f.xlsx"
        self._escrever_xlsx(
            arq,
            ["texto", "cond"],
            [
                ["válido", "1"],
                [None, "2"],
                ["   ", "3"],
                ["outro", "4"],
            ],
        )
        conn = ExcelFolderConnector(
            path=str(tmp_path), coluna_texto="texto", coluna_referencia="cond"
        )
        chunks = list(conn.read())
        assert [c.paragraph for c in chunks] == ["válido", "outro"]

    def test_referencia_default_quando_celula_vazia(self, tmp_path):
        from ingestion.connectors.excel import ExcelFolderConnector

        arq = tmp_path / "f.xlsx"
        self._escrever_xlsx(
            arq, ["texto", "cond"], [["a", None], ["b", "999"]]
        )
        conn = ExcelFolderConnector(
            path=str(tmp_path), coluna_texto="texto",
            coluna_referencia="cond", referencia_default="DEFAULT",
        )
        chunks = list(conn.read())
        assert chunks[0].referencia == "DEFAULT"
        assert chunks[1].referencia == "999"

    def test_coluna_texto_ausente_devolve_zero_chunks(self, tmp_path):
        from ingestion.connectors.excel import ExcelFolderConnector

        arq = tmp_path / "f.xlsx"
        self._escrever_xlsx(arq, ["resp"], [["x"]])
        conn = ExcelFolderConnector(path=str(tmp_path), coluna_texto="texto")
        assert list(conn.read()) == []

    def test_pasta_inexistente_levanta(self, tmp_path):
        from ingestion.connectors.excel import ExcelFolderConnector

        with pytest.raises(FileNotFoundError):
            ExcelFolderConnector(path=str(tmp_path / "nope"), coluna_texto="t")

    def test_coluna_texto_obrigatoria(self, tmp_path):
        from ingestion.connectors.excel import ExcelFolderConnector

        with pytest.raises(ValueError):
            ExcelFolderConnector(path=str(tmp_path), coluna_texto="")
