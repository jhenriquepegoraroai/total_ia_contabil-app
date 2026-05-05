"""
TenantConfig — modelo de configuração de um tenant (administradora).

Cada tenant tem um arquivo JSON em `api/tenants/configs/<tenant_id>.json`
que é validado contra este schema no boot da aplicação.

Estrutura geral:
    - Identificação (tenant_id, nome_empresa, nome_assistente, enabled)
    - Contatos da empresa (telefone, whatsapp, e-mail)
    - URLs públicas (app, portal)
    - Datasource (adapter Pattern — onde estão os dados deste tenant)
    - Theme (identidade visual — sobrescreve o tema Lello padrão)
    - Prompts customizados (categorias, principal, formatação, esclarecimento)
    - Respostas padrão por categoria
    - Mensagens de fallback
    - Configurações de RAG (top_k, threshold)
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from api.tenants.modulos import MODULO_SLUGS


# =============================================================================
# Datasource — Adapter Pattern
# =============================================================================
class DataSourceConfigPostgres(BaseModel):
    """Configuração para o adapter postgres_pgvector (default)."""

    type: Literal["postgres_pgvector"] = "postgres_pgvector"
    # Para o adapter default, usamos a connection string global da aplicação
    # e os dados ficam segregados por tenant_id+RLS no mesmo banco.
    # Tenants que precisem de banco dedicado podem subir variante futura
    # `postgres_pgvector_dedicated` que aceita `database_url_secret`.


class DataSourceConfigDatabricks(BaseModel):
    """Configuração para o adapter databricks (legado Lello)."""

    type: Literal["databricks"] = "databricks"
    server_hostname_secret: str = Field(..., description="Nome do secret no Secrets Manager")
    http_path_secret: str
    access_token_secret: str
    cluster_id_secret: str
    table_embeddings: str
    table_condominios: str
    table_areas: str


DataSourceConfig = DataSourceConfigPostgres | DataSourceConfigDatabricks


# =============================================================================
# Theme — identidade visual por tenant
# =============================================================================
class TenantTheme(BaseModel):
    """Sobrescreve o tema Lello padrão. Hex codes em formato `#RRGGBB`."""

    primary: str = "#CB1D40"
    primary_foreground: str = "#FFFFFF"
    secondary: str = "#5D0E1F"
    secondary_foreground: str = "#FFFFFF"
    accent: str = "#F5B79E"
    accent_foreground: str = "#0E0E0E"
    ink: str = "#0E0E0E"
    muted: str = "#EDEDED"
    background: str = "#FFFFFF"
    logo_url: str = "/themes/lello/logo.svg"
    favicon_url: str = "/themes/lello/favicon.ico"
    font_family: str = "Inter, sans-serif"

    @field_validator(
        "primary",
        "primary_foreground",
        "secondary",
        "secondary_foreground",
        "accent",
        "accent_foreground",
        "ink",
        "muted",
        "background",
    )
    @classmethod
    def validar_hex(cls, v: str) -> str:
        v_clean = v.strip()
        if not v_clean.startswith("#") or len(v_clean) not in (4, 7, 9):
            raise ValueError(f"Cor deve ser hex (#RGB, #RRGGBB ou #RRGGBBAA), recebi: {v!r}")
        return v_clean.upper()


# =============================================================================
# Contatos / URLs
# =============================================================================
class TenantContatos(BaseModel):
    telefone: str
    whatsapp: str
    whatsapp_link: str
    email: str
    horario_atendimento: str = "Segunda a Sexta, das 8h30 às 19h."


class TenantURLs(BaseModel):
    app_moradores: str
    portal_resolva_facil: str
    prestacao_contas: str | None = None
    cadastro_inquilino: str | None = None


# =============================================================================
# Integração OpenAI — chave própria do cliente OU compartilhada da Lello
# =============================================================================
class TenantOpenAIConfig(BaseModel):
    """
    Configuração da chave OpenAI usada pelo tenant.

    - mode='lello': usa a chave global OPEN_AI_KEY do env (default).
    - mode='custom': usa a chave do próprio cliente (`api_key` obrigatória).
                     Útil quando o cliente quer billing separado da Lello.

    Em produção, valores sensíveis devem ir pra Secrets Manager via
    `secret_name`. Por ora, aceitamos `api_key` direto no JSON para DEV.
    """

    mode: Literal["lello", "custom"] = "lello"
    api_key: str | None = None
    secret_name: str | None = None

    @field_validator("api_key")
    @classmethod
    def validar_api_key(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip()
        # Heurística: chaves OpenAI atuais começam com 'sk-'.
        if not v.startswith("sk-"):
            raise ValueError(
                "api_key não parece uma chave OpenAI válida (deve começar com 'sk-')."
            )
        return v


# =============================================================================
# Bella Atas — configuração por tenant
# =============================================================================
class TenantAtasConfig(BaseModel):
    """
    Configuração específica do módulo `atas` deste tenant.

    Hoje só armazena overrides de modelo. No futuro pode receber prompts
    customizados por administradora (ex: terminologia jurídica específica),
    formato preferido de exportação (DOCX/PDF), etc.

    A chave OpenAI usada vem do `TenantOpenAIConfig` agregador — segue o
    mesmo padrão do Bella Chat: ou usa a chave da Lello (mode='lello'),
    ou a do próprio cliente (mode='custom').
    """

    # Modelo OpenAI usado nas 3 chamadas (geração, revisão, correção).
    # String livre — não validamos contra catálogo da OpenAI porque modelos
    # mudam mais rápido que esta validação.
    openai_model: str = "gpt-5.4"

    # Modelo Whisper para STT do áudio da assembleia.
    whisper_model: str = "whisper-1"

    # Tom/temperature do gerador. Defaults conservadores (texto formal).
    temperature_geracao: float = 0.2
    temperature_correcao: float = 0.1

    @field_validator("temperature_geracao", "temperature_correcao")
    @classmethod
    def validar_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError(f"temperature deve estar em [0.0, 2.0], recebi: {v}")
        return v


# =============================================================================
# Bella Cobranças — credenciais Google Document AI por tenant
# =============================================================================
class TenantCobrancasConfig(BaseModel):
    """
    Credenciais e parâmetros do Google Document AI usados pelo módulo
    Bella Cobranças deste tenant.

    O service account JSON inteiro fica em `gcp_credentials_json` (JSONB
    no banco). O super admin sobe o arquivo via UI; o backend valida
    estrutura e mascara `private_key` em todos os GETs.

    `gcs_bucket` é opcional — só necessário para PDFs grandes (>15 páginas)
    que vão pro pipeline batch.

    Em prod, `gcp_credentials_json` migrará para Secrets Manager via
    `secret_name` (mesmo padrão da chave OpenAI).
    """

    gcp_credentials_json: dict[str, Any] | None = None
    gcp_project_id: str | None = None
    gcp_location: str = "us"
    processor_id: str | None = None
    gcs_bucket: str | None = None
    secret_name: str | None = None

    @field_validator("gcp_credentials_json")
    @classmethod
    def validar_service_account(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return None
        # Aceita dict mascarado vindo do GET (private_key contém '***') —
        # o router preserva a chave salva no DB nesse caso.
        pk = v.get("private_key", "")
        if isinstance(pk, str) and "***" in pk:
            return v
        obrigatorios = {"type", "project_id", "client_email", "private_key"}
        faltam = obrigatorios - set(v.keys())
        if faltam:
            raise ValueError(
                f"service account JSON faltando campos obrigatórios: {sorted(faltam)}"
            )
        if v.get("type") != "service_account":
            raise ValueError(
                f"campo 'type' deve ser 'service_account', recebi: {v.get('type')!r}"
            )
        return v


# =============================================================================
# Configuração de RAG / Busca
# =============================================================================
class TenantRAGConfig(BaseModel):
    """Defaults de RAG por tenant. Aplicação cai nestes valores se não vier override."""

    top_k: int = 8
    similarity_threshold: float = 0.30
    completion_temperature: float = 0.2

    @field_validator("similarity_threshold")
    @classmethod
    def validar_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"similarity_threshold deve estar em [0.0, 1.0], recebi: {v}")
        return v

    @field_validator("top_k")
    @classmethod
    def validar_top_k(cls, v: int) -> int:
        if not 1 <= v <= 50:
            raise ValueError(f"top_k deve estar em [1, 50], recebi: {v}")
        return v


# =============================================================================
# TenantConfig — agregado
# =============================================================================
class TenantConfig(BaseModel):
    """
    Configuração completa de um tenant. Carregada do JSON em `tenants/configs/`.

    O campo `tenant_id` é a chave única usada em toda a aplicação (queries,
    cache, RLS). Convenção: snake-lower, curto (ex: `lello`, `apsa`).
    """

    schema_version: str = Field(default="2.0", description="Versão do schema desta config")
    tenant_id: str = Field(..., description="ID único do tenant", min_length=2, max_length=32)
    nome_empresa: str
    nome_assistente: str
    enabled: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # E-mail do admin/representante da administradora — aparece como From
    # e Reply-To em todos os e-mails enviados pelo sistema em nome deste
    # tenant (módulo Bella Atas envia notificação pro síndico/presidente
    # com FROM = email_admin do tenant). Opcional pra retrocompat dos
    # tenants existentes; obrigatório quando o módulo `atas` é contratado
    # — validado em tempo de uso, não aqui.
    email_admin: EmailStr | None = None

    contatos: TenantContatos
    urls: TenantURLs
    datasource: DataSourceConfig = Field(..., discriminator="type")
    theme: TenantTheme = Field(default_factory=TenantTheme)
    rag: TenantRAGConfig = Field(default_factory=TenantRAGConfig)
    openai: TenantOpenAIConfig = Field(default_factory=TenantOpenAIConfig)

    # Prompts customizados — cada tenant ajusta o tom e as regras do assistente.
    prompt_principal: str
    prompt_formatacao: str
    prompt_esclarecimento: str
    categorias_prompt: str

    # Prompts opcionais por categoria (nem todo tenant tem cat 0/42).
    prompts_por_categoria: dict[int, str] = Field(default_factory=dict)

    # Respostas padrão por categoria (atalho — cai aqui antes de embeddings).
    respostas_padrao: dict[int, str] = Field(default_factory=dict)

    # Mensagens de fallback.
    resposta_sem_documento: str
    mensagem_nao_encontrada: str

    # Regras textuais opcionais (concorrentes, leis, etc).
    regra_concorrentes: str = ""
    leis_referencia: str = ""

    # Schemas estruturados que o tenant expõe (cat 0 e 42 da Lello, por exemplo).
    # Chave = nome lógico ("condominios", "areas"); valor = nome real da tabela
    # ou view no banco do tenant. O adapter resolve.
    schemas_estruturados: dict[str, str] = Field(default_factory=dict)

    # Módulos contratados pelo tenant (slug → ativo). Slugs válidos vêm do
    # catálogo em `api/tenants/modulos.py`. Default vazio: a contratação é
    # explícita — o super admin marca via UI no cadastro.
    modulos_contratados: dict[str, bool] = Field(default_factory=dict)

    # Configuração específica do módulo `atas`. Opcional — só relevante se
    # o tenant contratou esse módulo.
    atas: TenantAtasConfig | None = None

    # Credenciais Google Document AI — relevantes só quando o módulo
    # `cobrancas` está contratado. Opcional pra permitir cadastro do
    # tenant antes do JSON estar disponível.
    cobrancas: TenantCobrancasConfig | None = None

    @field_validator("modulos_contratados")
    @classmethod
    def validar_modulos(cls, v: dict[str, bool]) -> dict[str, bool]:
        invalidos = set(v.keys()) - MODULO_SLUGS
        if invalidos:
            raise ValueError(
                f"Módulos desconhecidos: {sorted(invalidos)}. "
                f"Disponíveis: {sorted(MODULO_SLUGS)}"
            )
        return v

    @field_validator("tenant_id")
    @classmethod
    def validar_tenant_id(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if not v_clean.replace("_", "").isalnum():
            raise ValueError(
                f"tenant_id deve conter apenas letras, números e underscore, recebi: {v!r}"
            )
        return v_clean

    def to_audit_dict(self) -> dict[str, Any]:
        """Versão segura para log/audit — sem prompts longos nem secrets."""
        return {
            "tenant_id": self.tenant_id,
            "nome_empresa": self.nome_empresa,
            "enabled": self.enabled,
            "datasource_type": self.datasource.type,
            "openai_mode": self.openai.mode,
            "schema_version": self.schema_version,
        }

    def to_admin_dict(self) -> dict[str, Any]:
        """
        Versão segura para a UI de admin — mascara a api_key da OpenAI
        e a private_key do service account Google. Mantém o resto inalterado.
        """
        d = self.model_dump(mode="json")
        api_key = d.get("openai", {}).get("api_key")
        if api_key:
            d["openai"]["api_key"] = mascarar_openai_key(api_key)
        creds = (d.get("cobrancas") or {}).get("gcp_credentials_json")
        if creds:
            d["cobrancas"]["gcp_credentials_json"] = mascarar_gcp_credentials(creds)
        return d


def mascarar_openai_key(key: str) -> str:
    """
    Mascara chave OpenAI mostrando só os 7 primeiros e 4 últimos caracteres.
    Ex: 'sk-proj-abcdef...wxyz'.
    """
    if not key:
        return ""
    if len(key) <= 11:
        return "*" * len(key)
    return f"{key[:7]}...{key[-4:]}"


def mascarar_gcp_credentials(creds: dict[str, Any]) -> dict[str, Any]:
    """
    Mascara `private_key` num service account JSON. Mantém os outros campos
    (project_id, client_email, etc.) intactos pra UI poder mostrar resumo.

    O preview da chave preserva só o header BEGIN/END pra deixar visível
    que é uma chave válida, sem expor o conteúdo.
    """
    out = dict(creds)
    pk = out.get("private_key")
    if isinstance(pk, str) and pk:
        out["private_key"] = "-----BEGIN PRIVATE KEY-----\n***\n-----END PRIVATE KEY-----\n"
    return out
