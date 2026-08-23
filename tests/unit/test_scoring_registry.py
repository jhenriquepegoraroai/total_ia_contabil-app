"""
Registro de modelos de scoring e o guard de capacidade.

A propriedade que estes testes protegem: **não existe caminho pelo qual a
plataforma produza um score sem um modelo real registrado**. A tentação óbvia
— um scorer provisório devolvendo número plausível — gravaria linha em
`capability_scores` com versão de modelo e carimbo de tempo, indistinguível
de resultado verdadeiro para quem lê a tela.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers.scores import capability_contratada
from worker import modelos
from worker.modelos import ModeloNaoRegistrado, Pontuacao


class ScorerFalso:
    """Só existe dentro deste teste — nunca é registrado em runtime."""

    capability = "churn"
    versao = "teste-0.1"
    feature_set_nome = "churn_unidade"

    def pontuar(self, linhas):
        return [
            Pontuacao(
                entidade_id=linha["entidade_id"],
                referencia=linha["referencia"],
                score=0.5,
            )
            for linha in linhas
        ]


@pytest.fixture(autouse=True)
def registro_limpo():
    modelos.limpar()
    yield
    modelos.limpar()


# =============================================================================
# Registro
# =============================================================================
def test_sem_modelo_registrado_obter_falha_alto():
    with pytest.raises(ModeloNaoRegistrado) as exc:
        modelos.obter("churn")
    # A mensagem tem que dizer o que fazer, não só que faltou.
    assert "encapsulado" in str(exc.value)


def test_registro_comeca_vazio():
    """
    O bootstrap do worker não registra nada por padrão. Se algum dia alguém
    plugar um scorer de conveniência ali, este teste quebra.
    """
    assert modelos.registrados() == []


def test_registrar_e_obter():
    scorer = ScorerFalso()
    modelos.registrar(scorer)
    assert modelos.registrados() == ["churn"]
    assert modelos.obter("churn") is scorer


def test_objeto_fora_do_protocolo_e_recusado():
    class SemPontuar:
        capability = "churn"
        versao = "x"
        feature_set_nome = "y"

    with pytest.raises(TypeError):
        modelos.registrar(SemPontuar())


def test_faixa_invalida_e_recusada_na_construcao():
    with pytest.raises(ValueError):
        Pontuacao(entidade_id="u1", referencia="111", score=0.9, faixa="altissimo")


def test_faixa_valida_e_opcional():
    assert Pontuacao(entidade_id="u1", referencia="111", score=0.9).faixa is None
    assert (
        Pontuacao(entidade_id="u1", referencia="111", score=0.9, faixa="alto").faixa
        == "alto"
    )


# =============================================================================
# Guard de capacidade do endpoint de leitura
# =============================================================================
def _request_com(tenant_config):
    """Request mínimo com o registry que o guard consulta."""

    class RegistryFake:
        def get(self, tenant_id, only_enabled=True):
            if tenant_config is None:
                raise ValueError(f"Tenant '{tenant_id}' não encontrado.")
            return tenant_config

    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        tenant_registry=RegistryFake()
    )))


def _user(tenant_id="t1", is_superadmin=False):
    return SimpleNamespace(
        tenant_id=tenant_id, user_id="u1", role="admin", is_superadmin=is_superadmin
    )


@pytest.mark.asyncio
async def test_capacidade_fora_do_catalogo_da_404(tenant_config_factory):
    cfg = tenant_config_factory(modulos_contratados={"churn": True})
    with pytest.raises(HTTPException) as exc:
        await capability_contratada("telepatia", _request_com(cfg), _user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_capacidade_nao_contratada_da_403(tenant_config_factory):
    cfg = tenant_config_factory(modulos_contratados={"chat": True})
    with pytest.raises(HTTPException) as exc:
        await capability_contratada("churn", _request_com(cfg), _user())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_capacidade_contratada_passa(tenant_config_factory):
    cfg = tenant_config_factory(modulos_contratados={"churn": True})
    user = _user()
    assert await capability_contratada("churn", _request_com(cfg), user) is user


@pytest.mark.asyncio
async def test_superadmin_passa_sem_contratar(tenant_config_factory):
    """Superadmin opera fora dos módulos — mesmo comportamento do require_module."""
    user = _user(is_superadmin=True)
    assert await capability_contratada("churn", _request_com(None), user) is user
