"""
DataSource — interface abstrata para acesso a dados de documentos por tenant.

Adapter Pattern. Cada implementação concreta (Postgres+pgvector, Databricks
legado, etc) implementa estes métodos. O `core_logic` da aplicação só conhece
esta interface — nunca importa cliente de banco direto.

REGRA CRÍTICA (RULES.md #29, #30): toda implementação concreta DEVE garantir
isolamento por tenant_id. A interface não confia em filtros do chamador.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Optional, Sequence


class DataSource(ABC):
    """
    Acesso a documentos, embeddings e dados estruturados de um tenant específico.

    Toda instância está amarrada a um `tenant_id`. Implementações DEVEM aplicar
    o filtro de tenant em TODA query, mesmo quando rodando atrás de RLS — defesa
    em profundidade.
    """

    tenant_id: str

    # -------------------------------------------------------------------------
    # Busca por similaridade (RAG principal)
    # -------------------------------------------------------------------------
    @abstractmethod
    async def busca_similaridade(
        self,
        referencia: str,
        query_embedding: Sequence[float],
        top_k: int = 8,
        threshold: float = 0.30,
        file_pattern_include: Optional[str] = None,
        file_pattern_exclude: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Retorna os top-K parágrafos mais similares ao `query_embedding` para
        a `referencia` (condomínio) deste tenant.

        Args:
            referencia: id do condomínio na administradora.
            query_embedding: vetor da pergunta (mesma dimensão do modelo).
            top_k: número máximo de resultados.
            threshold: similaridade mínima (cosine). Resultados abaixo são descartados.
            file_pattern_include: padrão SQL LIKE para `file_name` (case-insensitive).
                Ex: "%edital%". None = não filtra.
            file_pattern_exclude: padrão SQL LIKE para EXCLUIR `file_name`.

        Returns:
            Lista de dicts com chaves: `record_id`, `file_name`, `paragraph`,
            `data_valida`, `similarity`. Ordenado por `similarity` desc.
        """
        ...

    # -------------------------------------------------------------------------
    # Busca de parágrafos por padrão (sem embeddings — categorias 51, 65, 68)
    # -------------------------------------------------------------------------
    @abstractmethod
    async def buscar_paragrafos_por_pattern(
        self,
        referencia: str,
        file_pattern_include: Optional[str] = None,
        file_pattern_exclude: Optional[str] = None,
        regex_pattern: Optional[str] = None,
        only_latest_date: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Retorna parágrafos de documentos filtrados por padrão de `file_name`,
        sem precisar de embeddings (queries diretas, mais rápidas).

        Args:
            referencia: id do condomínio.
            file_pattern_include: SQL LIKE para incluir.
            file_pattern_exclude: SQL LIKE para excluir.
            regex_pattern: regex POSIX adicional (ex: AGE/AGO/ATA).
            only_latest_date: se True, retorna só os parágrafos do documento
                com `data_valida` mais recente entre os matches.

        Returns:
            Lista de dicts: `file_name`, `paragraph`, `data_valida`, `record_id`.
        """
        ...

    # -------------------------------------------------------------------------
    # Data mais recente (categoria 67)
    # -------------------------------------------------------------------------
    @abstractmethod
    async def buscar_data_mais_recente(
        self,
        referencia: str,
        file_pattern_include: str,
    ) -> Optional[date]:
        """
        Retorna a `MAX(data_valida)` entre documentos que batem o pattern.
        None se não houver documento.
        """
        ...

    # -------------------------------------------------------------------------
    # Dados estruturados (categorias 0, 42)
    # -------------------------------------------------------------------------
    @abstractmethod
    async def buscar_dados_estruturados(
        self,
        schema_key: str,
        referencia: str,
    ) -> list[dict[str, Any]]:
        """
        Lê uma tabela estruturada nomeada (resolvida via `tenant_config.schemas_estruturados`).

        Args:
            schema_key: chave lógica (ex: "condominios", "areas").
            referencia: id do condomínio.

        Returns:
            Lista de dicts com colunas da tabela. Vazia se não houver registro.

        Raises:
            ValueError: se `schema_key` não está mapeado para o tenant.
        """
        ...

    # -------------------------------------------------------------------------
    # Health check
    # -------------------------------------------------------------------------
    @abstractmethod
    async def health(self) -> bool:
        """Testa conectividade com a fonte de dados. True = OK."""
        ...
