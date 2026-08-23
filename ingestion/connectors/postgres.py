"""
PostgresConnector — lê linhas de uma tabela ou query do banco do cliente
e produz `RawChunk`s para o pipeline.

Use cases típicos:
  - Cliente tem tabela `documentos_condominios(condominio_id, texto, data, ...)`
    e quer indexar `texto` agrupado por `condominio_id`.
  - Cliente tem view custom — passa `custom_query` que retorna colunas
    `referencia, texto, data_valida (opcional), file_name (opcional),
    record_id (opcional)`.

Modos:
  - **Tabela** (`table` + `coluna_*`): connector monta o SELECT genérico
    `SELECT <colunas mapeadas> FROM <schema>.<table>` e mapeia.
  - **Custom query** (`custom_query`): connector usa o SQL do usuário.
    Schema esperado: `referencia` (text), `paragraph` ou `texto` (text),
    e opcionalmente `data_valida`, `file_name`, `record_id`.

Conexão sob demanda — abre conexão asyncpg só quando `read()` é chamado;
fecha ao fim. Pipeline chama `read()` dentro de `asyncio.run` em thread
separada (não há event loop ativo nessa thread), então `asyncio.run` é OK.
"""

import asyncio
import re
from collections.abc import Iterator
from datetime import date, datetime
from typing import Any

from loguru import logger

from .base import Connector, RawChunk

# Identificadores SQL seguros — letras/números/underscore. Evita injeção.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PostgresConnector(Connector):
    """
    Lê linhas do Postgres do cliente. Usa asyncpg (já em requirements
    para o nosso próprio Postgres).

    NUNCA passa identificadores (table/coluna) por bind — o asyncpg só
    parametriza valores. Por isso o `_validar_ident` é crítico.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        ssl_mode: str = "require",
        # Modo tabela
        table: str | None = None,
        schema_name: str | None = "public",
        coluna_referencia: str | None = None,
        coluna_texto: str | None = None,
        coluna_data: str | None = None,
        # Modo query custom
        custom_query: str | None = None,
    ):
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._ssl = ssl_mode != "disable"

        if custom_query:
            self._custom_query = custom_query.strip()
            self._table = None
        else:
            if not table or not coluna_texto:
                raise ValueError(
                    "PostgresConnector exige 'custom_query' OU "
                    "'table' + 'coluna_texto'."
                )
            self._validar_ident(table, "table")
            if schema_name:
                self._validar_ident(schema_name, "schema_name")
            self._validar_ident(coluna_texto, "coluna_texto")
            if coluna_referencia:
                self._validar_ident(coluna_referencia, "coluna_referencia")
            if coluna_data:
                self._validar_ident(coluna_data, "coluna_data")
            self._table = table
            self._schema = schema_name or "public"
            self._col_ref = coluna_referencia
            self._col_texto = coluna_texto
            self._col_data = coluna_data
            self._custom_query = None

    @staticmethod
    def _validar_ident(value: str, field: str) -> None:
        if not _IDENT_RE.match(value):
            raise ValueError(
                f"Identificador SQL inválido em '{field}': {value!r}. "
                f"Use [A-Za-z_][A-Za-z0-9_]*"
            )

    def describe(self) -> str:
        if self._custom_query:
            preview = self._custom_query[:60].replace("\n", " ")
            return f"postgres:custom({preview}...)"
        return f"postgres:{self._schema}.{self._table}"

    def read(self) -> Iterator[RawChunk]:
        return iter(asyncio.run(self._read_async()))

    async def _read_async(self) -> list[RawChunk]:
        import asyncpg

        try:
            conn = await asyncpg.connect(
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._database,
                ssl=self._ssl,
                timeout=15,
            )
        except Exception as exc:
            logger.exception(f"PostgresConnector falhou ao conectar: {exc}")
            raise

        try:
            sql, columns_meta = self._build_query()
            logger.info(f"[postgres_connector] executando: {sql[:120]}")
            rows = await conn.fetch(sql)
        finally:
            await conn.close()

        chunks: list[RawChunk] = []
        for i, row in enumerate(rows):
            try:
                chunk = self._row_to_chunk(row, i, columns_meta)
                if chunk:
                    chunks.append(chunk)
            except Exception as exc:
                logger.warning(f"linha {i} ignorada: {exc}")
                continue

        logger.info(f"[postgres_connector] {len(chunks)} chunks gerados de {len(rows)} linhas")
        return chunks

    def _build_query(self) -> tuple[str, dict[str, str | None]]:
        """Retorna (sql, mapeamento de colunas → keys do RawChunk)."""
        if self._custom_query:
            # Custom query: deixamos o usuário definir os aliases.
            # Esperamos colunas: referencia, paragraph (ou texto), data_valida,
            # file_name (opcional), record_id (opcional).
            return self._custom_query, {
                "referencia": "referencia",
                "paragraph": "paragraph",  # ou 'texto' — ver _row_to_chunk
                "data_valida": "data_valida",
                "file_name": "file_name",
                "record_id": "record_id",
            }

        # Modo tabela: monta SELECT explícito com aliases.
        cols = []
        cols.append(f'"{self._col_texto}" AS paragraph')
        if self._col_ref:
            cols.append(f'"{self._col_ref}" AS referencia')
        if self._col_data:
            cols.append(f'"{self._col_data}" AS data_valida')
        sql = f'SELECT {", ".join(cols)} FROM "{self._schema}"."{self._table}"'
        return sql, {
            "referencia": "referencia",
            "paragraph": "paragraph",
            "data_valida": "data_valida",
            "file_name": None,
            "record_id": None,
        }

    def _row_to_chunk(
        self,
        row: Any,
        index: int,
        cols: dict[str, str | None],
    ) -> RawChunk | None:
        # asyncpg.Record suporta acesso por nome — convertemos pra dict.
        d = dict(row)

        paragraph = d.get(cols["paragraph"]) if cols["paragraph"] else None
        # custom_query pode usar 'texto' em vez de 'paragraph'
        if paragraph is None:
            paragraph = d.get("texto")
        if paragraph is None:
            return None
        paragraph = str(paragraph).strip()
        if not paragraph:
            return None

        referencia = None
        if cols["referencia"] and d.get(cols["referencia"]) is not None:
            referencia = str(d[cols["referencia"]])

        data_valida: date | None = None
        if cols["data_valida"] and d.get(cols["data_valida"]) is not None:
            v = d[cols["data_valida"]]
            if isinstance(v, datetime):
                data_valida = v.date()
            elif isinstance(v, date):
                data_valida = v

        file_name = None
        if cols["file_name"] and d.get(cols["file_name"]):
            file_name = str(d[cols["file_name"]])
        if not file_name:
            file_name = (
                f"{self._schema}.{self._table}" if self._table else "postgres_query"
            )

        record_id = None
        if cols["record_id"] and d.get(cols["record_id"]):
            record_id = str(d[cols["record_id"]])
        if not record_id:
            record_id = f"row{index}"

        return RawChunk(
            file_name=file_name,
            record_id=record_id,
            paragraph=paragraph,
            data_valida=data_valida,
            referencia=referencia,
        )
