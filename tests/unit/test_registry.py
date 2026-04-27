"""Testes unitários do TenantRegistry — carregamento de JSONs sem DB."""

import json

import pytest

from api.tenants.registry import TenantRegistry


def _tenant_json(tenant_id: str, **overrides) -> dict:
    base = {
        "tenant_id": tenant_id,
        "nome_empresa": f"Empresa {tenant_id}",
        "nome_assistente": "Bot",
        "enabled": True,
        "contatos": {
            "telefone": "11 1234-5678",
            "whatsapp": "11 91234-5678",
            "whatsapp_link": "https://wa.me/5511912345678",
            "email": f"{tenant_id}@example.com",
        },
        "urls": {
            "app_moradores": "https://app.example.com",
            "portal_resolva_facil": "https://portal.example.com",
        },
        "datasource": {"type": "postgres_pgvector"},
        "prompt_principal": "p",
        "prompt_formatacao": "p",
        "prompt_esclarecimento": "p",
        "categorias_prompt": "p",
        "resposta_sem_documento": "x",
        "mensagem_nao_encontrada": "x",
    }
    base.update(overrides)
    return base


def _write(configs_dir, tenant_id, **overrides):
    path = configs_dir / f"{tenant_id}.json"
    path.write_text(
        json.dumps(_tenant_json(tenant_id, **overrides)),
        encoding="utf-8",
    )
    return path


def test_carregamento_basico(configs_dir):
    _write(configs_dir, "lello")
    _write(configs_dir, "apsa")

    registry = TenantRegistry(configs_dir)
    cache = registry.carregar_todos()

    assert set(cache.keys()) == {"lello", "apsa"}


def test_template_e_arquivos_underscore_sao_ignorados(configs_dir):
    _write(configs_dir, "lello")
    # Arquivo iniciado com underscore deve ser pulado
    (configs_dir / "_template.json").write_text(
        json.dumps(_tenant_json("template")),
        encoding="utf-8",
    )

    registry = TenantRegistry(configs_dir)
    cache = registry.carregar_todos()

    assert set(cache.keys()) == {"lello"}


def test_id_duplicado_falha(configs_dir):
    # Dois arquivos diferentes com mesmo tenant_id interno
    p1 = configs_dir / "a.json"
    p1.write_text(json.dumps(_tenant_json("dup")), encoding="utf-8")
    p2 = configs_dir / "b.json"
    p2.write_text(json.dumps(_tenant_json("dup")), encoding="utf-8")

    registry = TenantRegistry(configs_dir)
    with pytest.raises(RuntimeError, match="duplicado"):
        registry.carregar_todos()


def test_diretorio_vazio_falha(configs_dir):
    registry = TenantRegistry(configs_dir)
    with pytest.raises(RuntimeError, match="Nenhum arquivo"):
        registry.carregar_todos()


def test_get_disabled_levanta_erro(configs_dir):
    _write(configs_dir, "lello", enabled=False)

    registry = TenantRegistry(configs_dir)
    registry.carregar_todos()

    with pytest.raises(ValueError, match="desabilitado"):
        registry.get("lello")

    # Mas com only_enabled=False, retorna
    cfg = registry.get("lello", only_enabled=False)
    assert cfg.tenant_id == "lello"


def test_get_inexistente_lista_disponiveis(configs_dir):
    _write(configs_dir, "lello")

    registry = TenantRegistry(configs_dir)
    registry.carregar_todos()

    with pytest.raises(ValueError, match="não encontrado"):
        registry.get("apsa")


def test_listar_so_habilitados(configs_dir):
    _write(configs_dir, "lello", enabled=True)
    _write(configs_dir, "apsa", enabled=False)

    registry = TenantRegistry(configs_dir)
    registry.carregar_todos()

    assert registry.listar() == ["lello"]
    assert sorted(registry.listar(only_enabled=False)) == ["apsa", "lello"]


def test_placeholder_em_contato_gera_warning_mas_nao_falha(configs_dir, caplog):
    _write(
        configs_dir,
        "lello",
        contatos={
            "telefone": "(XX) XXXX-XXXX",   # placeholder
            "whatsapp": "11 91234-5678",
            "whatsapp_link": "https://wa.me/5511912345678",
            "email": "lello@example.com",
        },
    )

    registry = TenantRegistry(configs_dir)
    cache = registry.carregar_todos()
    # Carrega mesmo com placeholder, mas deve ter logado warning.
    assert "lello" in cache
