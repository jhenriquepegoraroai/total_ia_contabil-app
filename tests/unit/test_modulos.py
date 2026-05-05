"""
Testes do catálogo de módulos, do validator em TenantConfig e da factory
`require_module`. A aplicação real da dependency em rotas é coberta por
testes de integração na Fase 3.
"""

import pytest
from pydantic import ValidationError

from api.tenants.modulos import (
    MODULO_SLUGS,
    MODULOS_DISPONIVEIS,
    tenant_tem_modulo,
)


# =============================================================================
# Catálogo
# =============================================================================
def test_catalogo_tem_chat_e_cobrancas():
    assert "chat" in MODULOS_DISPONIVEIS
    assert "cobrancas" in MODULOS_DISPONIVEIS
    assert MODULOS_DISPONIVEIS["chat"].label == "Bella Chat"
    assert MODULOS_DISPONIVEIS["cobrancas"].label == "Bella Cobranças"


def test_modulo_slugs_bate_com_dicionario():
    assert MODULO_SLUGS == frozenset(MODULOS_DISPONIVEIS.keys())


def test_slugs_sao_snake_lower_ascii():
    """Slugs vão pra JSONB; renomear depois custa migration. Disciplina aqui."""
    for slug in MODULO_SLUGS:
        assert slug == slug.lower(), f"Slug não-lowercase: {slug!r}"
        assert slug.replace("_", "").isalnum(), f"Slug não snake-friendly: {slug!r}"
        assert slug.isascii(), f"Slug com não-ASCII: {slug!r}"


# =============================================================================
# tenant_tem_modulo
# =============================================================================
def test_tenant_tem_modulo_true_quando_marcado(tenant_config_factory):
    cfg = tenant_config_factory(modulos_contratados={"chat": True})
    assert tenant_tem_modulo(cfg, "chat") is True


def test_tenant_tem_modulo_false_quando_marcado_false(tenant_config_factory):
    cfg = tenant_config_factory(modulos_contratados={"chat": False})
    assert tenant_tem_modulo(cfg, "chat") is False


def test_tenant_tem_modulo_false_quando_ausente(tenant_config_factory):
    cfg = tenant_config_factory(modulos_contratados={})
    assert tenant_tem_modulo(cfg, "chat") is False
    assert tenant_tem_modulo(cfg, "cobrancas") is False


def test_tenant_tem_modulo_independente_por_slug(tenant_config_factory):
    cfg = tenant_config_factory(modulos_contratados={"chat": True, "cobrancas": False})
    assert tenant_tem_modulo(cfg, "chat") is True
    assert tenant_tem_modulo(cfg, "cobrancas") is False


# =============================================================================
# Validator do TenantConfig
# =============================================================================
def test_modulos_contratados_default_e_dict_vazio(tenant_config_factory):
    cfg = tenant_config_factory()
    assert cfg.modulos_contratados == {}


def test_modulos_contratados_aceita_slugs_do_catalogo(tenant_config_factory):
    cfg = tenant_config_factory(modulos_contratados={"chat": True, "cobrancas": True})
    assert cfg.modulos_contratados == {"chat": True, "cobrancas": True}


def test_modulos_contratados_rejeita_slug_desconhecido(tenant_config_factory):
    with pytest.raises(ValidationError) as exc_info:
        tenant_config_factory(modulos_contratados={"chatt": True})
    assert "chatt" in str(exc_info.value)


def test_modulos_contratados_rejeita_slug_desconhecido_misturado(tenant_config_factory):
    """Mesmo com um slug válido junto, qualquer inválido derruba."""
    with pytest.raises(ValidationError):
        tenant_config_factory(modulos_contratados={"chat": True, "foo": True})


# =============================================================================
# require_module — validação na construção (sem rede)
# Importado lazy: o módulo `deps` puxa FastAPI/jose, que pode não estar
# instalado em todo ambiente de dev. Pulamos com mensagem clara se faltar.
# =============================================================================
def test_require_module_rejeita_slug_invalido_na_factory():
    """Erro deve estourar na construção da dependency, não no request."""
    deps = pytest.importorskip("api.tenants.deps")
    with pytest.raises(ValueError):
        deps.require_module("modulo_que_nao_existe")


def test_require_module_aceita_slug_valido_na_factory():
    deps = pytest.importorskip("api.tenants.deps")
    dep = deps.require_module("chat")
    assert callable(dep)
    assert dep.__name__ == "require_module_chat"
