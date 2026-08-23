"""
Adapter default — Postgres + pgvector.

Embeddings ficam na tabela `documents_embeddings` (ver db/migrations/001_init.sql),
particionados logicamente por `tenant_id` com RLS forçado. A busca de similaridade
acontece server-side via operador `<=>` do pgvector (cosine distance).

Isolamento (defesa em profundidade):
  1. Toda query inclui `WHERE tenant_id = :tid` (mesmo com RLS).
  2. A `tenant_session` setou `app.current_tenant`, RLS bloqueia ainda assim.
  3. O construtor amarra `self.tenant_id` — métodos não aceitam tenant variável.
"""

from collections.abc import Sequence
from datetime import date
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .base import DataSource


class PostgresPgvectorDataSource(DataSource):
    """Implementação default. Lê de `documents_embeddings` + tabelas estruturadas."""

    def __init__(
        self,
        tenant_id: str,
        session: AsyncSession,
        schemas_estruturados: dict[str, str] | None = None,
    ):
        if not tenant_id:
            raise ValueError("tenant_id obrigatório")
        self.tenant_id = tenant_id
        self._session = session
        # Mapa de chave lógica → nome real da tabela. Default é a tabela genérica
        # do schema multi-tenant (ex: "condominios" → "condominios").
        self._schemas = schemas_estruturados or {
            "condominios": "condominios",
            "areas": "condominio_areas",
        }

    # =========================================================================
    # Busca por similaridade
    # =========================================================================
    async def busca_similaridade(
        self,
        referencia: str,
        query_embedding: Sequence[float],
        top_k: int = 8,
        threshold: float = 0.30,
        file_pattern_include: str | None = None,
        file_pattern_exclude: str | None = None,
    ) -> list[dict[str, Any]]:
        # pgvector: `<=>` é distância cosine (0 = idêntico, 2 = oposto).
        # similarity = 1 - distance, mas a maioria dos casos práticos cosine_distance ∈ [0, 1].
        # Filtramos por similarity >= threshold via subquery.
        sql_parts = [
            "WITH ranked AS (",
            "  SELECT",
            "    record_id, file_name, paragraph, data_valida,",
            "    1 - (embedding <=> CAST(:qe AS vector)) AS similarity",
            "  FROM documents_embeddings",
            "  WHERE tenant_id = :tid",
            "    AND referencia = :ref",
        ]
        params: dict[str, Any] = {
            "qe": _vector_literal(query_embedding),
            "tid": self.tenant_id,
            "ref": referencia,
            "k": top_k,
            "th": threshold,
        }

        if file_pattern_include:
            sql_parts.append("    AND lower(file_name) LIKE lower(:pat_inc)")
            params["pat_inc"] = file_pattern_include
        if file_pattern_exclude:
            sql_parts.append("    AND lower(file_name) NOT LIKE lower(:pat_exc)")
            params["pat_exc"] = file_pattern_exclude

        sql_parts += [
            ")",
            "SELECT * FROM ranked",
            "WHERE similarity >= :th",
            "ORDER BY similarity DESC",
            "LIMIT :k",
        ]
        sql = "\n".join(sql_parts)

        result = await self._session.execute(text(sql), params)
        rows = result.mappings().all()
        logger.debug(
            f"[{self.tenant_id}] busca_similaridade ref={referencia} top_k={top_k} "
            f"threshold={threshold} → {len(rows)} chunks"
        )
        return [dict(r) for r in rows]

    # =========================================================================
    # Busca por similaridade na carteira inteira (cross-condomínio)
    # =========================================================================
    async def busca_similaridade_carteira(
        self,
        query_embedding: Sequence[float],
        top_k: int = 24,
        threshold: float = 0.30,
        file_pattern_include: str | None = None,
        file_pattern_exclude: str | None = None,
    ) -> list[dict[str, Any]]:
        # Igual a `busca_similaridade`, mas SEM `AND referencia = :ref`. O filtro
        # por tenant_id permanece (defesa em profundidade + RLS). O SELECT expõe
        # `referencia` para o chamador agregar por condomínio.
        sql_parts = [
            "WITH ranked AS (",
            "  SELECT",
            "    referencia, record_id, file_name, paragraph, data_valida,",
            "    1 - (embedding <=> CAST(:qe AS vector)) AS similarity",
            "  FROM documents_embeddings",
            "  WHERE tenant_id = :tid",
        ]
        params: dict[str, Any] = {
            "qe": _vector_literal(query_embedding),
            "tid": self.tenant_id,
            "k": top_k,
            "th": threshold,
        }

        if file_pattern_include:
            sql_parts.append("    AND lower(file_name) LIKE lower(:pat_inc)")
            params["pat_inc"] = file_pattern_include
        if file_pattern_exclude:
            sql_parts.append("    AND lower(file_name) NOT LIKE lower(:pat_exc)")
            params["pat_exc"] = file_pattern_exclude

        sql_parts += [
            ")",
            "SELECT * FROM ranked",
            "WHERE similarity >= :th",
            "ORDER BY similarity DESC",
            "LIMIT :k",
        ]
        sql = "\n".join(sql_parts)

        result = await self._session.execute(text(sql), params)
        rows = result.mappings().all()
        logger.debug(
            f"[{self.tenant_id}] busca_similaridade_carteira top_k={top_k} "
            f"threshold={threshold} → {len(rows)} chunks"
        )
        return [dict(r) for r in rows]

    # =========================================================================
    # Parágrafos por pattern (sem embeddings)
    # =========================================================================
    async def buscar_paragrafos_por_pattern(
        self,
        referencia: str,
        file_pattern_include: str | None = None,
        file_pattern_exclude: str | None = None,
        regex_pattern: str | None = None,
        only_latest_date: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"tid": self.tenant_id, "ref": referencia}
        where = ["tenant_id = :tid", "referencia = :ref"]

        if file_pattern_include:
            where.append("lower(file_name) LIKE lower(:pat_inc)")
            params["pat_inc"] = file_pattern_include
        if file_pattern_exclude:
            where.append("lower(file_name) NOT LIKE lower(:pat_exc)")
            params["pat_exc"] = file_pattern_exclude
        if regex_pattern:
            # POSIX regex case-insensitive
            where.append("lower(file_name) ~ :rx")
            params["rx"] = regex_pattern

        where_clause = " AND ".join(where)

        if only_latest_date:
            sql = f"""
                WITH matches AS (
                    SELECT record_id, file_name, paragraph, data_valida
                    FROM documents_embeddings
                    WHERE {where_clause}
                ),
                latest AS (
                    SELECT MAX(data_valida) AS max_data FROM matches
                )
                SELECT m.record_id, m.file_name, m.paragraph, m.data_valida
                FROM matches m
                JOIN latest l ON m.data_valida = l.max_data
                ORDER BY m.file_name, m.record_id
            """
        else:
            sql = f"""
                SELECT record_id, file_name, paragraph, data_valida
                FROM documents_embeddings
                WHERE {where_clause}
                ORDER BY data_valida DESC NULLS LAST, file_name, record_id
            """

        result = await self._session.execute(text(sql), params)
        rows = result.mappings().all()
        logger.debug(
            f"[{self.tenant_id}] buscar_paragrafos_por_pattern ref={referencia} "
            f"only_latest={only_latest_date} → {len(rows)} parágrafos"
        )
        return [dict(r) for r in rows]

    # =========================================================================
    # Data mais recente
    # =========================================================================
    async def buscar_data_mais_recente(
        self,
        referencia: str,
        file_pattern_include: str,
    ) -> date | None:
        sql = """
            SELECT MAX(data_valida) AS max_data
            FROM documents_embeddings
            WHERE tenant_id = :tid
              AND referencia = :ref
              AND lower(file_name) LIKE lower(:pat)
              AND data_valida IS NOT NULL
        """
        result = await self._session.execute(
            text(sql),
            {"tid": self.tenant_id, "ref": referencia, "pat": file_pattern_include},
        )
        row = result.mappings().first()
        return row["max_data"] if row else None

    # =========================================================================
    # Dados estruturados
    # =========================================================================
    async def buscar_dados_estruturados(
        self,
        schema_key: str,
        referencia: str,
    ) -> list[dict[str, Any]]:
        if schema_key not in self._schemas:
            raise ValueError(
                f"Tenant '{self.tenant_id}' não tem schema_key '{schema_key}'. "
                f"Disponíveis: {list(self._schemas.keys())}"
            )
        table = self._schemas[schema_key]
        # Validação anti-injection: tabela tem que estar no whitelist (já está no _schemas)
        # mas garantimos que é um identificador SQL válido.
        if not _is_safe_identifier(table):
            raise ValueError(f"Nome de tabela inválido: {table!r}")

        # Identifier não pode ser parametrizado em SQLAlchemy text() — interpolamos
        # após validação. tenant_id e referencia continuam parametrizados.
        sql = f"""
            SELECT *
            FROM {table}
            WHERE tenant_id = :tid AND referencia = :ref
        """
        result = await self._session.execute(
            text(sql),
            {"tid": self.tenant_id, "ref": referencia},
        )
        rows = result.mappings().all()
        return [dict(r) for r in rows]

    # =========================================================================
    # Health
    # =========================================================================
    async def health(self) -> bool:
        try:
            result = await self._session.execute(text("SELECT 1"))
            return result.scalar_one() == 1
        except Exception:
            logger.exception(f"[{self.tenant_id}] health check falhou")
            return False


# =============================================================================
# Helpers
# =============================================================================
def _vector_literal(embedding: Sequence[float]) -> str:
    """
    Serializa um vetor Python para o literal aceito pelo pgvector via CAST().
    Formato: '[v1,v2,v3,...]'.

    Não usa `array_to_vector` — é mais lento que o cast direto de string.
    """
    return "[" + ",".join(f"{float(x):.7f}" for x in embedding) + "]"


def _is_safe_identifier(name: str) -> bool:
    """Permite só [a-zA-Z_][a-zA-Z0-9_]* — sem dot, sem espaço, sem schema-prefix."""
    if not name or not (name[0].isalpha() or name[0] == "_"):
        return False
    return all(c.isalnum() or c == "_" for c in name)
