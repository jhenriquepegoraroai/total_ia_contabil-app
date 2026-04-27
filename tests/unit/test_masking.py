"""Testes do módulo de mascaramento de PII (RULES.md #6)."""

from api.utils.masking import (
    mascarar,
    mascarar_cpf,
    mascarar_email,
    mascarar_referencia,
    mascarar_telefone,
)


# =============================================================================
# Genérico
# =============================================================================
def test_mascarar_string_curta_oculta_tudo():
    assert mascarar("ab") == "**"
    assert mascarar("abcde") == "*****"


def test_mascarar_string_longa_mantem_inicio_e_fim():
    assert mascarar("abcdefghij") == "abc*****ij"


def test_mascarar_vazio_e_none():
    assert mascarar("") == ""
    assert mascarar(None) == ""


# =============================================================================
# Email
# =============================================================================
def test_mascarar_email_padrao():
    assert mascarar_email("joao.silva@gmail.com") == "joa*******@gmail.com"


def test_mascarar_email_local_curto():
    assert mascarar_email("ab@x.com") == "**@x.com"
    assert mascarar_email("abc@x.com") == "***@x.com"


def test_mascarar_email_invalido_cai_no_genérico():
    assert "*" in mascarar_email("isso_nao_e_email")


def test_mascarar_email_vazio():
    assert mascarar_email(None) == ""
    assert mascarar_email("") == ""


# =============================================================================
# CPF
# =============================================================================
def test_mascarar_cpf_formatado():
    # 123.456.789-10 → 123.***.**9-10
    out = mascarar_cpf("123.456.789-10")
    assert out.startswith("123.")
    assert out.endswith("-10")
    assert "*" in out


def test_mascarar_cpf_sem_formato():
    out = mascarar_cpf("12345678910")
    assert "*" in out
    assert out.startswith("123")
    assert out.endswith("10")


def test_mascarar_cpf_invalido_cai_no_genérico():
    assert "*" in mascarar_cpf("nao_e_cpf")


# =============================================================================
# Telefone
# =============================================================================
def test_mascarar_telefone_celular():
    # (11) 91234-5678 → (11) 9****-5678
    out = mascarar_telefone("(11) 91234-5678")
    assert out == "(11) 9****-5678"


def test_mascarar_telefone_fixo():
    # 11 2797-7585 → (11) 2***-7585
    out = mascarar_telefone("(XX) XXXXX-XXXX")
    assert out == "(11) 2***-7585"


# =============================================================================
# Referência
# =============================================================================
def test_mascarar_referencia_curta():
    assert mascarar_referencia("12") == "**"
    assert mascarar_referencia("1234") == "****"


def test_mascarar_referencia_longa():
    # 12345 → 12*45 (2 inicio, 2 fim, * no meio)
    out = mascarar_referencia("12345")
    assert out.startswith("12")
    assert out.endswith("45")
    assert "*" in out


# =============================================================================
# Idempotência
# =============================================================================
def test_mascarar_idempotente_em_string_curta():
    """Se aplicarmos 2x, mantém o mesmo (string já mascarada)."""
    a = mascarar("ab")
    b = mascarar(a)
    assert a == b == "**"
