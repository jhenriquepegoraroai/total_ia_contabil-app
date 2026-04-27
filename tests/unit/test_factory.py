"""Testes do factory de DataSource."""

from unittest.mock import MagicMock

import pytest

from api.tenants.datasources import criar_datasource
from api.tenants.datasources.postgres_pgvector import PostgresPgvectorDataSource


def test_factory_resolve_postgres_pgvector(tenant_config_factory):
    config = tenant_config_factory(datasource={"type": "postgres_pgvector"})
    session = MagicMock()
    ds = criar_datasource(config, session)
    assert isinstance(ds, PostgresPgvectorDataSource)
    assert ds.tenant_id == config.tenant_id


def test_factory_databricks_levanta_not_implemented(tenant_config_factory):
    config = tenant_config_factory(
        datasource={
            "type": "databricks",
            "server_hostname_secret": "x",
            "http_path_secret": "x",
            "access_token_secret": "x",
            "cluster_id_secret": "x",
            "table_embeddings": "x.y.z",
            "table_condominios": "x.y.c",
            "table_areas": "x.y.a",
        }
    )
    session = MagicMock()
    with pytest.raises(NotImplementedError, match="databricks"):
        criar_datasource(config, session)


def test_postgres_adapter_amarrado_ao_tenant(tenant_config_factory):
    config = tenant_config_factory(tenant_id="lello")
    session = MagicMock()
    ds = criar_datasource(config, session)
    # Não há setter público para tenant_id — ele é fixo na construção.
    assert ds.tenant_id == "lello"
