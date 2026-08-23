"""
Validação de dados de feature contra o contrato do tenant.

O contrato vive em `feature_sets.schema_json` (migration 015) e declara, por
coluna: tipo, obrigatoriedade, descrição e — quando `NULL` tem significado de
negócio — o que ele significa.

Por que validar na entrada, e não deixar o modelo lidar: um modelo global
calibrado na carteira da Lello não tem como perceber que o parceiro mandou
`0` onde a Lello manda `NULL`. Ele lê "pagou em dia" onde o correto era "não
há histórico", devolve um número plausível e ninguém percebe. Erro de
integração precisa aparecer na carga, não no score.

Módulo puro: sem FastAPI, sem banco, sem I/O — dá para testar sozinho e é
usado tanto pela ingestão quanto pela API.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any

# Tipos aceitos na declaração de uma coluna do contrato.
TIPOS_SUPORTADOS: frozenset[str] = frozenset(
    {"number", "integer", "string", "boolean", "date"}
)


class ContratoInvalido(ValueError):
    """O `schema_json` em si está malformado — não é erro do dado entregue."""


@dataclass(frozen=True, slots=True)
class ErroValidacao:
    """Um problema em uma coluna do lote entregue."""

    coluna: str
    problema: str

    def __str__(self) -> str:  # pragma: no cover - conveniência de log
        return f"{self.coluna}: {self.problema}"


def validar_schema(schema_json: Any) -> None:
    """
    Valida a declaração do contrato. Levanta `ContratoInvalido` com mensagem
    específica — este erro é do operador que cadastrou o feature_set, não do
    parceiro que entregou dado, e as duas coisas não podem se confundir.
    """
    if not isinstance(schema_json, dict) or not schema_json:
        raise ContratoInvalido(
            "schema_json deve ser um objeto não-vazio de coluna → declaração."
        )

    for coluna, decl in schema_json.items():
        if not isinstance(coluna, str) or not coluna:
            raise ContratoInvalido(f"Nome de coluna inválido: {coluna!r}")
        if not isinstance(decl, dict):
            raise ContratoInvalido(
                f"Declaração da coluna '{coluna}' deve ser objeto, veio {type(decl).__name__}."
            )

        tipo = decl.get("tipo")
        if tipo not in TIPOS_SUPORTADOS:
            raise ContratoInvalido(
                f"Coluna '{coluna}': tipo {tipo!r} não suportado. "
                f"Use um de {sorted(TIPOS_SUPORTADOS)}."
            )

        obrigatorio = decl.get("obrigatorio")
        if not isinstance(obrigatorio, bool):
            raise ContratoInvalido(
                f"Coluna '{coluna}': 'obrigatorio' deve ser booleano explícito."
            )


def validar_valores(
    schema_json: dict[str, Any], valores: dict[str, Any]
) -> list[ErroValidacao]:
    """
    Compara um lote de valores com o contrato. Devolve a lista completa de
    problemas — não para no primeiro: quem está integrando precisa ver tudo
    de uma vez, senão o onboarding vira uma ida e volta por coluna.

    Lista vazia significa lote aceito.
    """
    validar_schema(schema_json)

    if not isinstance(valores, dict):
        return [ErroValidacao("<lote>", "valores deve ser um objeto coluna → valor.")]

    erros: list[ErroValidacao] = []

    for coluna, decl in schema_json.items():
        obrigatorio: bool = decl["obrigatorio"]
        presente = coluna in valores

        if not presente:
            if obrigatorio:
                erros.append(ErroValidacao(coluna, "coluna obrigatória ausente"))
            continue

        valor = valores[coluna]
        if valor is None:
            if obrigatorio:
                erros.append(
                    ErroValidacao(
                        coluna,
                        "coluna obrigatória veio nula — se nulo é um estado "
                        "válido do negócio, declare 'obrigatorio': false e "
                        "documente em 'nulo_significa'",
                    )
                )
            continue

        problema = _conferir_tipo(decl["tipo"], valor)
        if problema:
            erros.append(ErroValidacao(coluna, problema))

    # Coluna fora do contrato é erro, não ruído: o parceiro que envia um campo
    # não declarado acredita que ele está sendo usado, e não está.
    for coluna in valores:
        if coluna not in schema_json:
            erros.append(ErroValidacao(coluna, "coluna não declarada no contrato"))

    return erros


def _conferir_tipo(tipo: str, valor: Any) -> str | None:
    """Retorna a descrição do problema, ou None se o valor serve."""
    # `bool` é subclasse de `int` em Python: sem esta checagem primeiro, True
    # passaria como number/integer válido e viraria 1 silenciosamente.
    if isinstance(valor, bool):
        if tipo != "boolean":
            return f"esperado {tipo}, veio booleano"
        return None

    if tipo == "boolean":
        return f"esperado booleano, veio {type(valor).__name__}"

    if tipo == "integer":
        if isinstance(valor, int):
            return None
        if isinstance(valor, float) and valor.is_integer():
            # 12.0 vindo de planilha é inteiro na prática; 12.5 não é.
            return None
        return f"esperado inteiro, veio {type(valor).__name__}"

    if tipo == "number":
        if isinstance(valor, (int, float)):
            return None
        return f"esperado número, veio {type(valor).__name__}"

    if tipo == "string":
        if isinstance(valor, str):
            return None
        return f"esperado texto, veio {type(valor).__name__}"

    if tipo == "date":
        if isinstance(valor, _dt.date):
            return None
        if isinstance(valor, str):
            try:
                _dt.date.fromisoformat(valor)
            except ValueError:
                return f"data deve estar em ISO (AAAA-MM-DD), veio {valor!r}"
            return None
        return f"esperada data, veio {type(valor).__name__}"

    # Inalcançável: validar_schema já rejeitou tipo fora da lista.
    return f"tipo {tipo!r} não suportado"
