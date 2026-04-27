"""
Factory — resolve o adapter de DataSource a partir do TenantConfig.

Padrão: `core_logic` chama `criar_datasource(tenant_config, session)` no início
da request e usa o adapter retornado durante toda aquela request. Os métodos
do adapter executam dentro da transação da `session`.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from api.tenants.models import TenantConfig
from .base import DataSource
from .postgres_pgvector import PostgresPgvectorDataSource


def criar_datasource(tenant_config: TenantConfig, session: AsyncSession) -> DataSource:
    """
    Constrói o adapter de DataSource correto para o tenant.

    O `tenant_config.datasource.type` é discriminado (Pydantic). Adicionar um
    novo adapter = adicionar um modelo em `tenants/models.py` e um branch aqui.
    """
    ds_type = tenant_config.datasource.type

    if ds_type == "postgres_pgvector":
        return PostgresPgvectorDataSource(
            tenant_id=tenant_config.tenant_id,
            session=session,
            schemas_estruturados=tenant_config.schemas_estruturados or None,
        )

    if ds_type == "databricks":
        # Adapter Databricks legado da Lello — não implementado nesta fase.
        # Quando entrar, vai em `databricks.py` deste mesmo diretório.
        raise NotImplementedError(
            f"Adapter 'databricks' não está implementado nesta fase. "
            f"Tenant '{tenant_config.tenant_id}' precisa migrar para 'postgres_pgvector' "
            f"ou aguardar a Fase futura de adapter legado."
        )

    raise ValueError(f"Tipo de datasource desconhecido: {ds_type!r}")
