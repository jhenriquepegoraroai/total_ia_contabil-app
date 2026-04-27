"""Testes unitários do TenantConfig (Pydantic v2)."""

import pytest
from pydantic import ValidationError


def test_tenant_config_minimo_valido(tenant_config_factory):
    config = tenant_config_factory()
    assert config.tenant_id == "test_tenant"
    assert config.datasource.type == "postgres_pgvector"
    assert config.theme.primary == "#CB1D40"  # default Lello
    assert config.rag.top_k == 8
    assert config.rag.similarity_threshold == 0.30


def test_tenant_id_normaliza_para_lowercase(tenant_config_factory):
    config = tenant_config_factory(tenant_id="MyTenant_123")
    assert config.tenant_id == "mytenant_123"


def test_tenant_id_rejeita_caracteres_invalidos(tenant_config_factory):
    with pytest.raises(ValidationError):
        tenant_config_factory(tenant_id="my-tenant!")


def test_theme_normaliza_hex_para_uppercase(tenant_config_factory):
    config = tenant_config_factory(theme={"primary": "#cb1d40"})
    assert config.theme.primary == "#CB1D40"


def test_theme_rejeita_hex_invalido(tenant_config_factory):
    with pytest.raises(ValidationError):
        tenant_config_factory(theme={"primary": "vermelho"})


def test_rag_threshold_aceita_zero_a_um(tenant_config_factory):
    config = tenant_config_factory(rag={"similarity_threshold": 0.0})
    assert config.rag.similarity_threshold == 0.0
    config = tenant_config_factory(rag={"similarity_threshold": 1.0})
    assert config.rag.similarity_threshold == 1.0


def test_rag_threshold_rejeita_fora_do_intervalo(tenant_config_factory):
    with pytest.raises(ValidationError):
        tenant_config_factory(rag={"similarity_threshold": 1.5})
    with pytest.raises(ValidationError):
        tenant_config_factory(rag={"similarity_threshold": -0.1})


def test_rag_top_k_rejeita_valores_extremos(tenant_config_factory):
    with pytest.raises(ValidationError):
        tenant_config_factory(rag={"top_k": 0})
    with pytest.raises(ValidationError):
        tenant_config_factory(rag={"top_k": 100})


def test_datasource_discriminado_por_type(tenant_config_factory):
    """Pydantic deve usar o discriminador `type` para escolher o subtipo."""
    config = tenant_config_factory(datasource={"type": "postgres_pgvector"})
    assert config.datasource.type == "postgres_pgvector"


def test_datasource_databricks_requer_secrets(tenant_config_factory):
    with pytest.raises(ValidationError):
        tenant_config_factory(datasource={"type": "databricks"})  # faltam secrets


def test_to_audit_dict_nao_vaza_prompts(tenant_config_factory):
    config = tenant_config_factory()
    audit = config.to_audit_dict()
    # Campos seguros devem estar presentes
    assert "tenant_id" in audit
    assert "datasource_type" in audit
    # Prompts não devem vazar
    assert "prompt_principal" not in audit
    assert "categorias_prompt" not in audit
