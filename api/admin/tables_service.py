"""
Service de Tabelas — read-only browser do DB para superadmin.

Permite o superadmin inspecionar o conteúdo das tabelas multi-tenant
de um cliente sem precisar de psql. Útil para debugar 'por que esse
cond não responde X'.

REGRAS CRÍTICAS:
  - Apenas tabelas em `WHITELIST` são acessíveis (defesa anti-injeção
    por nome de tabela).
  - Apenas colunas em `COLUNAS_VISIVEIS` são retornadas — campos pesados
    (vetor `embedding` de 3072 dim, `content_hash`) ficam fora.
  - Toda query tem `WHERE tenant_id = :tid` — defesa em profundidade.
  - Read-only: nenhum INSERT/UPDATE/DELETE exposto.
  - Filtros (`referencia`, `q`) são parametrizados; usuário NUNCA injeta SQL.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# =============================================================================
# Whitelist
# =============================================================================
# Cada tabela é declarada com:
#   - colunas_select: o que aparece no grid (ordem importa)
#   - coluna_referencia: nome da coluna que filtra por condomínio (None se não tem)
#   - colunas_busca: campos onde o ?q= bate (ILIKE) — None desabilita busca
#   - order_by: ORDER BY default
WHITELIST: dict[str, dict[str, Any]] = {
    "condominios": {
        "label": "Condomínios",
        "descricao": "Dados cadastrais (síndico, áreas, datas de assembleia, etc).",
        "colunas_select": [
            "referencia", "nome", "cnpj", "endereco",
            "numero_blocos", "quantidade_apartamentos",
            "nome_sindico", "apartamento_sindico", "final_mandato_sindico",
            "vencimento_cota",
            "data_ultima_assembleia_ordinaria",
            "data_proxima_assembleia_ordinaria",
            "updated_at",
        ],
        "coluna_referencia": "referencia",
        "colunas_busca": ["nome", "cnpj", "endereco", "nome_sindico"],
        "order_by": "referencia ASC",
    },
    "condominio_areas": {
        "label": "Áreas comuns",
        "descricao": "Salão, churrasqueira, piscina — regras de reserva e cobrança.",
        "colunas_select": [
            "referencia", "nome", "capacidade_pessoas",
            "horario_permitido", "periodo_padrao",
            "taxa_utilizacao", "area_paga",
            "limite_reservas", "dias_semana_permitidos",
            "updated_at",
        ],
        "coluna_referencia": "referencia",
        "colunas_busca": ["nome", "horario_permitido", "restricoes"],
        "order_by": "referencia ASC, nome ASC",
    },
    "documents": {
        "label": "Documentos (metadados)",
        "descricao": "PDFs/arquivos indexados — nome, data e quantos parágrafos.",
        "colunas_select": [
            "id", "referencia", "file_name", "data_valida",
            "mime_type", "qtde_paragrafos", "created_at", "updated_at",
        ],
        "coluna_referencia": "referencia",
        "colunas_busca": ["file_name"],
        "order_by": "created_at DESC",
    },
    "documents_embeddings": {
        "label": "Chunks de embeddings",
        "descricao": "Cada parágrafo virou um chunk indexado. O vetor (3072 dim) não é exibido.",
        "colunas_select": [
            "id", "referencia", "file_name", "record_id",
            "paragraph", "data_valida", "created_at",
        ],
        "coluna_referencia": "referencia",
        "colunas_busca": ["paragraph", "file_name"],
        "order_by": "created_at DESC",
    },
    "embeddings_audit": {
        "label": "Auditoria de ingestão",
        "descricao": "Cada execução do pipeline de embeddings (chunks, erros, duração).",
        "colunas_select": [
            "contador", "referencia", "connector",
            "started_at", "finished_at",
            "qtde_chunks_origem", "qtde_processada",
            "qtde_skipped", "qtde_erros",
            "duracao_segundos",
        ],
        "coluna_referencia": "referencia",
        "colunas_busca": None,
        "order_by": "started_at DESC NULLS LAST",
    },
}


def _validar_tabela(tabela: str) -> dict[str, Any]:
    """Levanta ValueError se tabela não está na whitelist."""
    if tabela not in WHITELIST:
        raise ValueError(
            f"Tabela '{tabela}' não disponível. "
            f"Disponíveis: {sorted(WHITELIST.keys())}"
        )
    return WHITELIST[tabela]


# =============================================================================
# Listagem de tabelas disponíveis (com count)
# =============================================================================
async def listar_tabelas(
    session: AsyncSession, tenant_id: str
) -> list[dict[str, Any]]:
    """Para cada tabela da whitelist, devolve metadata + count(*) do tenant."""
    out = []
    for nome, meta in WHITELIST.items():
        # COUNT(*) — usa hardcoded `nome` da whitelist (seguro contra injeção
        # porque nome veio de WHITELIST.keys() e foi validado pelo caller).
        sql = text(f"SELECT COUNT(*)::int AS n FROM {nome} WHERE tenant_id = :tid")
        n = (await session.execute(sql, {"tid": tenant_id})).scalar_one()
        out.append({
            "name": nome,
            "label": meta["label"],
            "descricao": meta["descricao"],
            "qtde_linhas": int(n),
            "colunas": meta["colunas_select"],
        })
    return out


# =============================================================================
# Listagem paginada de linhas
# =============================================================================
async def listar_rows(
    session: AsyncSession,
    tenant_id: str,
    tabela: str,
    *,
    referencia: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Retorna `{columns: [...], rows: [{...}], total: N}`.

    Filtros opcionais:
      - referencia: WHERE coluna_referencia = :ref
      - q: WHERE qualquer coluna_busca ILIKE %q%
    """
    meta = _validar_tabela(tabela)

    # Limit / offset sanidade.
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))

    cols = meta["colunas_select"]
    cols_sql = ", ".join(cols)

    where_clauses = ["tenant_id = :tid"]
    params: dict[str, Any] = {"tid": tenant_id}

    if referencia and meta.get("coluna_referencia"):
        # Prefix match — usa o índice B-tree (tenant_id, referencia) que já
        # existe nas tabelas multi-tenant. Permite filtrar progressivamente
        # ('9' → '99' → '999' → '99999') sem custo extra.
        # Escapa wildcards do usuário pra evitar comportamento esquisito
        # ('a%b' precisa virar 'a\%b%').
        ref_escaped = referencia.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        where_clauses.append(
            f"{meta['coluna_referencia']} LIKE :ref ESCAPE '\\'"
        )
        params["ref"] = f"{ref_escaped}%"

    if q and meta.get("colunas_busca"):
        ors = []
        for i, col in enumerate(meta["colunas_busca"]):
            key = f"q{i}"
            ors.append(f"{col} ILIKE :{key}")
            params[key] = f"%{q}%"
        where_clauses.append(f"({' OR '.join(ors)})")

    where_sql = " AND ".join(where_clauses)

    # COUNT total (para paginação).
    count_sql = text(f"SELECT COUNT(*)::int FROM {tabela} WHERE {where_sql}")
    total = (await session.execute(count_sql, params)).scalar_one()

    # Linhas.
    sql = text(
        f"SELECT {cols_sql} FROM {tabela} "
        f"WHERE {where_sql} "
        f"ORDER BY {meta['order_by']} "
        f"LIMIT :limit OFFSET :offset"
    )
    params["limit"] = limit
    params["offset"] = offset

    rows = (await session.execute(sql, params)).mappings().all()

    # Normaliza tipos não-JSON (datetime, date, UUID, Decimal).
    rows_normalizadas = [_normalizar_row(dict(r)) for r in rows]

    return {
        "table": tabela,
        "label": meta["label"],
        "descricao": meta["descricao"],
        "columns": cols,
        "rows": rows_normalizadas,
        "total": int(total),
        "offset": offset,
        "limit": limit,
    }


def _normalizar_row(row: dict[str, Any]) -> dict[str, Any]:
    """Converte tipos do asyncpg/sqlalchemy para algo serializável em JSON."""
    from datetime import date, datetime
    from decimal import Decimal
    from uuid import UUID

    out = {}
    for k, v in row.items():
        if v is None:
            out[k] = None
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif isinstance(v, UUID):
            out[k] = str(v)
        elif isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, str) and len(v) > 500:
            # Trunca paragraphs muito longos para o grid não explodir.
            out[k] = v[:500] + "…"
        else:
            out[k] = v
    return out
