"""
Testes do TenantCobrancasConfig (Pydantic) e do mascaramento de credenciais
Google. O cliente Document AI em si (chamada de rede) é coberto por testes
de integração — aqui só validamos schema e helpers puros.
"""

import pytest
from pydantic import ValidationError

from api.tenants.models import (
    TenantCobrancasConfig,
    mascarar_gcp_credentials,
)

# Service account válido mínimo, usado em vários testes.
VALID_SA = {
    "type": "service_account",
    "project_id": "meu-projeto",
    "client_email": "sa@meu-projeto.iam.gserviceaccount.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...fake...\n-----END PRIVATE KEY-----\n",
}


# =============================================================================
# Validator
# =============================================================================
def test_aceita_service_account_valido():
    cfg = TenantCobrancasConfig(
        gcp_credentials_json=VALID_SA,
        gcp_project_id="meu-projeto",
        processor_id="proc123",
    )
    assert cfg.gcp_credentials_json["project_id"] == "meu-projeto"
    assert cfg.gcp_location == "us"  # default


def test_default_eh_tudo_none_exceto_location():
    cfg = TenantCobrancasConfig()
    assert cfg.gcp_credentials_json is None
    assert cfg.gcp_project_id is None
    assert cfg.processor_id is None
    assert cfg.gcs_bucket is None
    assert cfg.gcp_location == "us"


def test_rejeita_json_sem_campos_obrigatorios():
    incompleto = {"type": "service_account", "project_id": "x"}
    with pytest.raises(ValidationError) as exc:
        TenantCobrancasConfig(gcp_credentials_json=incompleto)
    msg = str(exc.value)
    assert "client_email" in msg
    assert "private_key" in msg


def test_rejeita_type_diferente_de_service_account():
    inv = {**VALID_SA, "type": "user"}
    with pytest.raises(ValidationError) as exc:
        TenantCobrancasConfig(gcp_credentials_json=inv)
    assert "service_account" in str(exc.value)


def test_aceita_credenciais_mascaradas_vindas_do_get():
    """
    Quando o frontend faz PUT sem re-subir o JSON, ele devolve a private_key
    mascarada (`***`) que o backend mandou no GET. O validador precisa aceitar
    essa forma — o router substitui pela chave salva antes de gravar no DB.
    """
    mascarado = {
        **VALID_SA,
        "private_key": "-----BEGIN PRIVATE KEY-----\n***\n-----END PRIVATE KEY-----\n",
    }
    cfg = TenantCobrancasConfig(gcp_credentials_json=mascarado)
    assert "***" in cfg.gcp_credentials_json["private_key"]


# =============================================================================
# mascarar_gcp_credentials
# =============================================================================
def test_mascara_apenas_private_key():
    out = mascarar_gcp_credentials(VALID_SA)
    assert out["project_id"] == "meu-projeto"
    assert out["client_email"] == "sa@meu-projeto.iam.gserviceaccount.com"
    assert out["type"] == "service_account"
    assert "***" in out["private_key"]
    assert "MIIE" not in out["private_key"]  # chave real escondida


def test_mascarar_nao_muta_o_dict_original():
    creds = dict(VALID_SA)
    pk_original = creds["private_key"]
    _ = mascarar_gcp_credentials(creds)
    assert creds["private_key"] == pk_original  # não vazou pelo lado


def test_mascarar_lida_com_private_key_ausente():
    sem_pk = {k: v for k, v in VALID_SA.items() if k != "private_key"}
    out = mascarar_gcp_credentials(sem_pk)
    assert "private_key" not in out


# =============================================================================
# Integração com TenantConfig (to_admin_dict)
# =============================================================================
def test_to_admin_dict_mascara_private_key(tenant_config_factory):
    cfg = tenant_config_factory(
        cobrancas={
            "gcp_credentials_json": VALID_SA,
            "gcp_project_id": "meu-projeto",
            "processor_id": "proc123",
        }
    )
    out = cfg.to_admin_dict()
    pk = out["cobrancas"]["gcp_credentials_json"]["private_key"]
    assert "***" in pk
    assert "MIIE" not in pk
    # outros campos preservados
    assert out["cobrancas"]["gcp_project_id"] == "meu-projeto"
    assert out["cobrancas"]["processor_id"] == "proc123"


def test_to_admin_dict_sem_cobrancas_nao_quebra(tenant_config_factory):
    cfg = tenant_config_factory()
    out = cfg.to_admin_dict()
    assert out.get("cobrancas") is None
