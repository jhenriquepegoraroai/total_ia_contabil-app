"""
Mascaramento de PII para logs (RULES.md #6).

Padrão geral: 3 primeiros + 2 últimos caracteres visíveis. Todo o resto vira `*`.
Strings curtas (<= 5 chars) viram totalmente mascaradas.

Funções idempotentes — aplicar 2x produz o mesmo resultado.
"""

import re

_EMAIL_RE = re.compile(r"^([^@]+)@(.+)$")
_CPF_RE = re.compile(r"^\D*(\d{3})\D*(\d{3})\D*(\d{3})\D*(\d{2})\D*$")
_FONE_RE = re.compile(r"^\D*(\d{2})\D*(\d{4,5})\D*(\d{4})\D*$")


def mascarar(valor: str | None, *, visiveis_inicio: int = 3, visiveis_fim: int = 2) -> str:
    """Mascaramento genérico — útil para campos não estruturados."""
    if not valor:
        return ""
    if len(valor) <= visiveis_inicio + visiveis_fim:
        return "*" * len(valor)
    inicio = valor[:visiveis_inicio]
    fim = valor[-visiveis_fim:]
    meio = "*" * (len(valor) - visiveis_inicio - visiveis_fim)
    return f"{inicio}{meio}{fim}"


def mascarar_email(email: str | None) -> str:
    """`joao.silva@gmail.com` → `joa***@gmail.com`."""
    if not email:
        return ""
    m = _EMAIL_RE.match(email)
    if not m:
        return mascarar(email)
    local, dominio = m.group(1), m.group(2)
    local_masc = (
        "*" * len(local) if len(local) <= 3 else local[:3] + "*" * (len(local) - 3)
    )
    return f"{local_masc}@{dominio}"


def mascarar_cpf(cpf: str | None) -> str:
    """`123.456.789-10` → `123.***.**9-10` (3 primeiros + 2 últimos visíveis)."""
    if not cpf:
        return ""
    m = _CPF_RE.match(cpf)
    if not m:
        return mascarar(cpf)
    return f"{m.group(1)}.***.**{m.group(3)[-1]}-{m.group(4)}"


def mascarar_telefone(fone: str | None) -> str:
    """`(11) 91234-5678` → `(11) 9****-5678`."""
    if not fone:
        return ""
    m = _FONE_RE.match(fone)
    if not m:
        return mascarar(fone)
    ddd, meio, fim = m.group(1), m.group(2), m.group(3)
    meio_masc = meio[:1] + "*" * (len(meio) - 1)
    return f"({ddd}) {meio_masc}-{fim}"


def mascarar_referencia(ref: str | None) -> str:
    """
    Referência de condomínio é dado interno mas pode ser sensível em log público.
    Mascaramento parcial: `12345` → `12***45` (mantém ordem de grandeza visível).
    Para referências curtas (<=4), mascara tudo.
    """
    if not ref:
        return ""
    if len(ref) <= 4:
        return "*" * len(ref)
    return ref[:2] + "*" * (len(ref) - 4) + ref[-2:]
