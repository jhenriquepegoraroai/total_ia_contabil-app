"""
Validação do contrato de features.

O caso que mais importa aqui não é o dado obviamente errado — é o dado
plausível e errado: `0` onde deveria vir `NULL`, `True` onde deveria vir
número, texto onde deveria vir data. Um modelo global calibrado na carteira
da Lello aceita tudo isso sem reclamar e devolve score que ninguém confere.
"""

import datetime

import pytest

from api.features import (
    ContratoInvalido,
    ErroValidacao,
    validar_schema,
    validar_valores,
)

SCHEMA_CHURN = {
    "atraso_medio_dias": {
        "tipo": "number",
        "obrigatorio": True,
        "descricao": "Média de dias de atraso em 12 meses.",
    },
    "qtde_atrasos_12m": {
        "tipo": "integer",
        "obrigatorio": True,
        "descricao": "Vencimentos pagos com atraso.",
    },
    "houve_acordo_12m": {
        "tipo": "boolean",
        "obrigatorio": False,
        "descricao": "Houve renegociação.",
    },
    "primeira_cobranca_em": {
        "tipo": "date",
        "obrigatorio": False,
        "descricao": "Data da primeira cobrança.",
    },
}


def _colunas(erros: list[ErroValidacao]) -> set[str]:
    return {e.coluna for e in erros}


# =============================================================================
# Contrato bem formado
# =============================================================================
def test_lote_completo_e_valido_nao_gera_erro():
    valores = {
        "atraso_medio_dias": 12.4,
        "qtde_atrasos_12m": 3,
        "houve_acordo_12m": False,
        "primeira_cobranca_em": "2024-03-01",
    }
    assert validar_valores(SCHEMA_CHURN, valores) == []


def test_opcional_ausente_e_aceito():
    valores = {"atraso_medio_dias": 0.0, "qtde_atrasos_12m": 0}
    assert validar_valores(SCHEMA_CHURN, valores) == []


def test_opcional_nulo_e_aceito():
    valores = {
        "atraso_medio_dias": 1.0,
        "qtde_atrasos_12m": 1,
        "houve_acordo_12m": None,
    }
    assert validar_valores(SCHEMA_CHURN, valores) == []


def test_date_aceita_objeto_date_alem_de_iso():
    valores = {
        "atraso_medio_dias": 1.0,
        "qtde_atrasos_12m": 1,
        "primeira_cobranca_em": datetime.date(2024, 3, 1),
    }
    assert validar_valores(SCHEMA_CHURN, valores) == []


# =============================================================================
# Os erros que importam
# =============================================================================
def test_obrigatorio_ausente_e_reportado():
    erros = validar_valores(SCHEMA_CHURN, {"qtde_atrasos_12m": 2})
    assert _colunas(erros) == {"atraso_medio_dias"}
    assert "obrigat" in erros[0].problema


def test_obrigatorio_nulo_explica_o_caminho_correto():
    """
    Nulo em coluna obrigatória é o erro de integração mais caro: o parceiro
    costuma trocar por 0, e aí vira 'pagou em dia'.
    """
    erros = validar_valores(
        SCHEMA_CHURN, {"atraso_medio_dias": None, "qtde_atrasos_12m": 1}
    )
    assert _colunas(erros) == {"atraso_medio_dias"}
    assert "nulo_significa" in erros[0].problema


def test_booleano_nao_passa_como_numero():
    """
    `bool` é subclasse de `int` em Python: sem checagem explícita, True
    entraria como 1 e o modelo leria um dia de atraso.
    """
    erros = validar_valores(
        SCHEMA_CHURN, {"atraso_medio_dias": True, "qtde_atrasos_12m": 1}
    )
    assert _colunas(erros) == {"atraso_medio_dias"}
    assert "boolean" in erros[0].problema.lower()


def test_numero_nao_passa_como_booleano():
    erros = validar_valores(
        SCHEMA_CHURN,
        {"atraso_medio_dias": 1.0, "qtde_atrasos_12m": 1, "houve_acordo_12m": 1},
    )
    assert _colunas(erros) == {"houve_acordo_12m"}


def test_inteiro_aceita_float_redondo_e_rejeita_fracionario():
    ok = validar_valores(
        SCHEMA_CHURN, {"atraso_medio_dias": 1.0, "qtde_atrasos_12m": 3.0}
    )
    assert ok == []

    erros = validar_valores(
        SCHEMA_CHURN, {"atraso_medio_dias": 1.0, "qtde_atrasos_12m": 3.5}
    )
    assert _colunas(erros) == {"qtde_atrasos_12m"}


def test_data_fora_de_iso_e_rejeitada():
    erros = validar_valores(
        SCHEMA_CHURN,
        {
            "atraso_medio_dias": 1.0,
            "qtde_atrasos_12m": 1,
            "primeira_cobranca_em": "01/03/2024",
        },
    )
    assert _colunas(erros) == {"primeira_cobranca_em"}
    assert "ISO" in erros[0].problema


def test_coluna_fora_do_contrato_e_erro():
    """
    Ignorar campo não declarado faria o parceiro acreditar que ele está sendo
    usado pelo modelo.
    """
    erros = validar_valores(
        SCHEMA_CHURN,
        {"atraso_medio_dias": 1.0, "qtde_atrasos_12m": 1, "score_interno": 0.9},
    )
    assert _colunas(erros) == {"score_interno"}
    assert "não declarada" in erros[0].problema


def test_reporta_todos_os_problemas_de_uma_vez():
    """Parar no primeiro erro transformaria o onboarding em ida e volta."""
    erros = validar_valores(
        SCHEMA_CHURN,
        {"qtde_atrasos_12m": "três", "houve_acordo_12m": "sim", "extra": 1},
    )
    assert _colunas(erros) == {
        "atraso_medio_dias",  # obrigatória ausente
        "qtde_atrasos_12m",  # texto onde é inteiro
        "houve_acordo_12m",  # texto onde é booleano
        "extra",  # não declarada
    }


# =============================================================================
# Contrato malformado — erro do operador, não do parceiro
# =============================================================================
def test_schema_vazio_e_contrato_invalido():
    with pytest.raises(ContratoInvalido):
        validar_schema({})


def test_tipo_desconhecido_e_contrato_invalido():
    with pytest.raises(ContratoInvalido) as exc:
        validar_schema({"x": {"tipo": "dinheiro", "obrigatorio": True}})
    assert "dinheiro" in str(exc.value)


def test_obrigatorio_precisa_ser_booleano_explicito():
    with pytest.raises(ContratoInvalido):
        validar_schema({"x": {"tipo": "number", "obrigatorio": "sim"}})


def test_declaracao_de_coluna_precisa_ser_objeto():
    with pytest.raises(ContratoInvalido):
        validar_schema({"x": "number"})
