"""
Fixtures pytest compartilhadas.

Testes de unidade rodam sem Postgres. Testes marcados com `@pytest.mark.integration`
requerem Postgres acessível (rodar `docker-compose up -d postgres` antes).

Variáveis de ambiente necessárias para integration tests:
  - DATABASE_URL (conexão com banco de teste — separado da aplicação!)
  - OPEN_AI_KEY (qualquer string válida — testes não chamam API real)
  - SECRET_KEY_JWT (idem)
"""

import os
import sys
from pathlib import Path

import pytest

# Permite `from api.tenants...` em testes sem instalar o pacote.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Defaults para que os testes unit rodem sem .env real.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://avc:avc_dev@localhost:5432/assistente_condominios_test")
os.environ.setdefault("OPEN_AI_KEY", "sk-test-fake")
os.environ.setdefault("SECRET_KEY_JWT", "test-secret-key-not-for-production")


@pytest.fixture
def configs_dir(tmp_path: Path) -> Path:
    """Diretório temporário para JSONs de tenant nos testes."""
    d = tmp_path / "configs"
    d.mkdir()
    return d


@pytest.fixture
def tenant_config_factory():
    """Factory de TenantConfig com defaults sensatos para testes."""
    from api.tenants.models import TenantConfig

    def _make(**overrides) -> TenantConfig:
        defaults = {
            "tenant_id": "test_tenant",
            "nome_empresa": "Tenant de Teste",
            "nome_assistente": "TestBot",
            "enabled": True,
            "contatos": {
                "telefone": "11 1234-5678",
                "whatsapp": "11 91234-5678",
                "whatsapp_link": "https://wa.me/5511912345678",
                "email": "test@example.com",
            },
            "urls": {
                "app_moradores": "https://app.test.com",
                "portal_resolva_facil": "https://portal.test.com",
            },
            "datasource": {"type": "postgres_pgvector"},
            "prompt_principal": "Test prompt",
            "prompt_formatacao": "Test format",
            "prompt_esclarecimento": "Test clarify",
            "categorias_prompt": "Test categories",
            "resposta_sem_documento": "Sem documento.",
            "mensagem_nao_encontrada": "Não encontrado.",
        }
        defaults.update(overrides)
        return TenantConfig(**defaults)

    return _make
