"""
Zona de features — o caminho de dado tabular da plataforma.

Enquanto `ingestion/` transforma documento em vetor para as capacidades de
linguagem, este pacote cuida do dado transacional que alimenta os modelos de
ML (churn, fraude, inadimplência, ISC).

O contrato declarado em `feature_sets.schema_json` é validado aqui — ver
`instrucao/contrato_features.md`.
"""

from .contrato import (
    ContratoInvalido,
    ErroValidacao,
    validar_schema,
    validar_valores,
)

__all__ = [
    "ContratoInvalido",
    "ErroValidacao",
    "validar_schema",
    "validar_valores",
]
