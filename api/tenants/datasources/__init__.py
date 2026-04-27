"""DataSource adapters — Adapter Pattern para origem de dados por tenant."""

from .base import DataSource
from .factory import criar_datasource
from .postgres_pgvector import PostgresPgvectorDataSource

__all__ = ["DataSource", "PostgresPgvectorDataSource", "criar_datasource"]
