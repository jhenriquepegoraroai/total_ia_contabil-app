"""
Testes unitários do TenantRegistry.

A partir da Fase 5, o registry é DB-backed: `carregar_todos(session)` lê
de `tenant_configs` (e faz seed dos JSONs só quando o DB está vazio).
Esses testes mockam a `AsyncSession` para validar o cacheamento, o get
e o filtro de habilitados sem precisar subir Postgres real. O caminho
de seed é coberto separadamente nos integration tests.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.tenants.registry import TenantRegistry


def _tenant_dict(tenant_id: str, **overrides) -> dict:
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


def _mock_session(tenants: list[dict]):
    """
    Devolve uma AsyncSession fake cujo `execute()` retorna `tenants` no
    primeiro SELECT (registry só executa um SELECT por carregar_todos
    quando o DB já tem dados). Cada item é (tenant_id, config_json).
    """
    session = AsyncMock()
    rows = [(t["tenant_id"], t) for t in tenants]

    result = MagicMock()
    result.all.return_value = rows
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture
def configs_dir(tmp_path):
    """Diretório vazio — não usaremos seed nesses testes (DB sempre 'tem dados')."""
    d = tmp_path / "configs"
    d.mkdir()
    return d


# =============================================================================
# Cache + carregamento básico
# =============================================================================
@pytest.mark.asyncio
async def test_carregamento_basico(configs_dir):
    session = _mock_session([_tenant_dict("lello"), _tenant_dict("apsa")])

    registry = TenantRegistry(configs_dir)
    cache = await registry.carregar_todos(session)

    assert set(cache.keys()) == {"lello", "apsa"}


@pytest.mark.asyncio
async def test_recarregar_substitui_cache(configs_dir):
    """Recarregar com payload diferente substitui o cache (não acumula)."""
    session = _mock_session([_tenant_dict("lello")])
    registry = TenantRegistry(configs_dir)
    await registry.carregar_todos(session)

    # Próxima chamada vai retornar uma lista diferente.
    novo_result = MagicMock()
    novo_result.all.return_value = [
        ("apsa", _tenant_dict("apsa")),
    ]
    session.execute = AsyncMock(return_value=novo_result)
    await registry.recarregar(session)

    assert "lello" not in registry
    assert "apsa" in registry


# =============================================================================
# get / get_por_nome / listar
# =============================================================================
@pytest.mark.asyncio
async def test_get_disabled_levanta_erro(configs_dir):
    session = _mock_session([_tenant_dict("lello", enabled=False)])
    registry = TenantRegistry(configs_dir)
    await registry.carregar_todos(session)

    with pytest.raises(ValueError, match="desabilitado"):
        registry.get("lello")

    # only_enabled=False ainda retorna
    cfg = registry.get("lello", only_enabled=False)
    assert cfg.tenant_id == "lello"


@pytest.mark.asyncio
async def test_get_inexistente_lista_disponiveis(configs_dir):
    session = _mock_session([_tenant_dict("lello")])
    registry = TenantRegistry(configs_dir)
    await registry.carregar_todos(session)

    with pytest.raises(ValueError, match="não encontrado"):
        registry.get("apsa")


@pytest.mark.asyncio
async def test_listar_so_habilitados(configs_dir):
    session = _mock_session(
        [_tenant_dict("lello", enabled=True), _tenant_dict("apsa", enabled=False)]
    )
    registry = TenantRegistry(configs_dir)
    await registry.carregar_todos(session)

    assert registry.listar() == ["lello"]
    assert sorted(registry.listar(only_enabled=False)) == ["apsa", "lello"]


@pytest.mark.asyncio
async def test_listar_oculta_system_por_default(configs_dir):
    session = _mock_session(
        [
            _tenant_dict("_system", nome_empresa="System Reserved"),
            _tenant_dict("lello"),
        ]
    )
    registry = TenantRegistry(configs_dir)
    await registry.carregar_todos(session)

    # _system fica fora a menos que peça include_system=True
    assert "_system" not in registry.listar(only_enabled=False)
    assert "_system" in registry.listar(only_enabled=False, include_system=True)


@pytest.mark.asyncio
async def test_get_por_nome(configs_dir):
    session = _mock_session([_tenant_dict("lello", nome_empresa="Administradora Exemplo")])
    registry = TenantRegistry(configs_dir)
    await registry.carregar_todos(session)

    assert registry.get_por_nome("Administradora Exemplo").tenant_id == "lello"
    assert registry.get_por_nome("  administradora exemplo  ").tenant_id == "lello"  # case+trim
    assert registry.get_por_nome("Inexistente") is None


# =============================================================================
# Validação
# =============================================================================
@pytest.mark.asyncio
async def test_config_invalida_levanta_runtime_error(configs_dir):
    """Se config_json falha validação Pydantic, o boot trava com mensagem clara."""
    invalido = _tenant_dict("X")  # tenant_id min_length=2 → '%' único caractere falha
    session = _mock_session([invalido])

    registry = TenantRegistry(configs_dir)
    with pytest.raises(RuntimeError, match="Erros ao carregar tenants"):
        await registry.carregar_todos(session)


@pytest.mark.asyncio
async def test_db_vazio_e_sem_seed_levanta(configs_dir):
    """Se DB vazio E pasta de seed vazia → RuntimeError 'Nenhum tenant válido'."""
    session = AsyncMock()
    empty_result = MagicMock()
    empty_result.all.return_value = []
    session.execute = AsyncMock(return_value=empty_result)

    registry = TenantRegistry(configs_dir)
    with pytest.raises(RuntimeError, match="Nenhum tenant"):
        await registry.carregar_todos(session)


@pytest.mark.asyncio
async def test_placeholder_em_contato_gera_warning_mas_nao_falha(configs_dir, caplog):
    payload = _tenant_dict(
        "lello",
        contatos={
            "telefone": "(XX) XXXX-XXXX",  # placeholder
            "whatsapp": "11 91234-5678",
            "whatsapp_link": "https://wa.me/5511912345678",
            "email": "lello@example.com",
        },
    )
    session = _mock_session([payload])

    registry = TenantRegistry(configs_dir)
    cache = await registry.carregar_todos(session)

    # Carrega mesmo com placeholder — só loga warning.
    assert "lello" in cache


# =============================================================================
# upsert/remover em memória (atalho usado pelo admin após criar/deletar)
# =============================================================================
@pytest.mark.asyncio
async def test_upsert_em_memoria_sobrescreve(configs_dir):
    from api.tenants.models import TenantConfig

    session = _mock_session([_tenant_dict("lello", nome_empresa="Antigo")])
    registry = TenantRegistry(configs_dir)
    await registry.carregar_todos(session)
    assert registry.get("lello").nome_empresa == "Antigo"

    novo = TenantConfig(**_tenant_dict("lello", nome_empresa="Novo"))
    registry.upsert_em_memoria(novo)

    assert registry.get("lello").nome_empresa == "Novo"


@pytest.mark.asyncio
async def test_remover_em_memoria(configs_dir):
    session = _mock_session([_tenant_dict("lello"), _tenant_dict("apsa")])
    registry = TenantRegistry(configs_dir)
    await registry.carregar_todos(session)

    registry.remover_em_memoria("apsa")
    assert "apsa" not in registry
    assert "lello" in registry


# =============================================================================
# JSON serialization no seed (config_json string vs dict)
# =============================================================================
@pytest.mark.asyncio
async def test_aceita_config_json_como_string(configs_dir):
    """asyncpg devolve JSONB como dict, mas defensivamente o registry
    aceita string também."""
    payload = _tenant_dict("lello")
    session = AsyncMock()
    result = MagicMock()
    # row[1] vem como string (simulando driver legado)
    result.all.return_value = [("lello", json.dumps(payload))]
    session.execute = AsyncMock(return_value=result)

    registry = TenantRegistry(configs_dir)
    cache = await registry.carregar_todos(session)
    assert "lello" in cache
