"""
Schema de destino do Bella Cobranças — preenchido pelo GPT-4o a partir
do output do Google Document AI.

Mantemos o `TARGET_SCHEMA` (dict puro) compatível com o que o LLM espera
ver no prompt; e oferecemos modelos Pydantic pra validação ao parsear
a resposta.
"""

from typing import Any

from pydantic import BaseModel, Field

# Schema enviado ao LLM no prompt (formato esperado de resposta).
TARGET_SCHEMA: dict[str, Any] = {
    "registros": [
        {
            "CONDOMINIO": "Nome ou código do condomínio",
            "UNIDADE": "Número da unidade/apartamento",
            "PRIMEIRO_VENCTO": "Data do primeiro vencimento (DD/MM/YYYY)",
            "MULTA": "Valor da multa (se houver)",
            "EMISSAO": "Data ou código de emissão",
            "NR_DO_RECIBO": "Número do recibo/boleto",
            "REGISTRO_EMISSAO": "Registro de emissão (se houver)",
            "SITUACAO": "Situação: Normal, Jurídico (J), Protesto (P), Acordo (A), etc.",
            "CONTA": "Código da conta contábil",
            "HISTORICO": "Descrição/histórico da cobrança",
            "VALOR_ORIGINAL": "Valor original da cobrança (número)",
        }
    ],
    "metadata": {
        "total_registros": 0,
        "total_valor": 0.0,
        "periodo": "",
        "data_emissao_relatorio": "",
    },
}


class RegistroCobranca(BaseModel):
    """Linha individual de cobrança extraída do relatório."""

    CONDOMINIO: str | None = None
    UNIDADE: str | None = None
    PRIMEIRO_VENCTO: str | None = None
    MULTA: float | None = None
    EMISSAO: str | None = None
    NR_DO_RECIBO: str | None = None
    REGISTRO_EMISSAO: str | None = None
    SITUACAO: str | None = None
    CONTA: str | None = None
    HISTORICO: str | None = None
    VALOR_ORIGINAL: float | None = None


class CobrancaMetadata(BaseModel):
    total_registros: int = 0
    total_valor: float = 0.0
    periodo: str = ""
    data_emissao_relatorio: str = ""


class CobrancaResultado(BaseModel):
    """Resposta estruturada do pipeline pra um PDF."""

    registros: list[RegistroCobranca] = Field(default_factory=list)
    metadata: CobrancaMetadata = Field(default_factory=CobrancaMetadata)
