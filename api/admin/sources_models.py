"""
Modelos Pydantic das fontes de dados de tenants.

Cada `type` tem schema próprio; os campos sensíveis são marcados como
opcionais aqui e devem ser populados via `secret_name` (referência ao
Secrets Manager) em produção. Para DEV/local, podem vir no payload
mas avisamos no log.

Tipos suportados nesta fase (6.1):
    pdf_upload    — upload manual de PDFs (storage local em dev, S3 em prod)
    excel_upload  — upload manual de Excel/CSV (stub estrutural)
    csv_upload    — alias de excel_upload (parser diferente)
    s3            — bucket S3 do cliente (Fase 6.2)
    azure_blob    — Azure Blob Storage do cliente (Fase 6.2)
    postgres      — Postgres do cliente (Fase 6.2)
    sqlserver     — SQL Server do cliente (Fase 6.2)
    databricks    — Databricks workspace (legado Lello, Fase futura)
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# =============================================================================
# Configurações por tipo
# =============================================================================
class PdfUploadConfig(BaseModel):
    """Upload manual de PDFs. Arquivos vão pro storage configurado."""

    type: Literal["pdf_upload"] = "pdf_upload"
    referencia_default: str | None = Field(
        default=None,
        description="Se setado, todo PDF subido é associado a este condomínio. "
                    "Se None, espera-se que o nome do arquivo carregue a referência.",
    )


class ExcelUploadConfig(BaseModel):
    """Upload de Excel — estrutural, processamento será na Fase 6.1.5."""

    type: Literal["excel_upload"] = "excel_upload"
    referencia_default: str | None = None
    coluna_referencia: str | None = Field(
        default=None,
        description="Nome da coluna no Excel que carrega o id do condomínio.",
    )
    coluna_texto: str = Field(
        description="Nome da coluna que vira o `paragraph` indexado.",
    )


class CsvUploadConfig(ExcelUploadConfig):
    type: Literal["csv_upload"] = "csv_upload"
    delimiter: str = ","


class S3SourceConfig(BaseModel):
    """Bucket S3 do cliente. Stub funcional na Fase 6.1, completo na 6.2."""

    type: Literal["s3"] = "s3"
    bucket: str
    region: str = "sa-east-1"
    prefix: str = ""
    # Credenciais — nunca no JSON em prod; usar secret_name.
    access_key_id: str | None = None
    secret_access_key: str | None = None


class AzureBlobSourceConfig(BaseModel):
    type: Literal["azure_blob"] = "azure_blob"
    account: str
    container: str
    prefix: str = ""
    # Credenciais via SAS token ou account key.
    sas_token: str | None = None
    account_key: str | None = None


class PostgresSourceConfig(BaseModel):
    type: Literal["postgres"] = "postgres"
    host: str
    port: int = 5432
    database: str
    user: str
    password: str | None = None  # via secret em prod
    ssl_mode: Literal["disable", "require", "verify-ca", "verify-full"] = "require"
    # Mapeamento da query: como transformar linhas em chunks
    table: str | None = None
    schema_name: str | None = "public"
    coluna_referencia: str | None = None
    coluna_texto: str | None = None
    coluna_data: str | None = None
    custom_query: str | None = Field(
        default=None,
        description="SQL custom (SELECT). Ignora table+colunas se setado.",
    )


class SqlServerSourceConfig(BaseModel):
    type: Literal["sqlserver"] = "sqlserver"
    host: str
    port: int = 1433
    database: str
    user: str
    password: str | None = None
    table: str | None = None
    coluna_referencia: str | None = None
    coluna_texto: str | None = None
    coluna_data: str | None = None
    custom_query: str | None = None


class DatabricksSourceConfig(BaseModel):
    """Compat com a Bella original da Lello."""

    type: Literal["databricks"] = "databricks"
    server_hostname: str
    http_path: str
    cluster_id: str
    table_embeddings: str
    table_condominios: str | None = None
    table_areas: str | None = None
    access_token: str | None = None  # via secret em prod


# Discriminator union — Pydantic escolhe pelo campo `type`.
SourceConfig = Annotated[
    PdfUploadConfig
    | ExcelUploadConfig
    | CsvUploadConfig
    | S3SourceConfig
    | AzureBlobSourceConfig
    | PostgresSourceConfig
    | SqlServerSourceConfig
    | DatabricksSourceConfig,
    Field(discriminator="type"),
]


# =============================================================================
# Wrappers de request/response
# =============================================================================
class CreateSourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    config: SourceConfig
    secret_name: str | None = Field(
        default=None,
        description="Referência ao Secrets Manager. Em prod, credenciais "
                    "vêm daqui — não do payload.",
    )


class SourceSummary(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    type: str
    enabled: bool
    qtde_files: int
    last_run_at: datetime | None
    last_run_status: str | None
    created_at: datetime
    updated_at: datetime


class SourceDetail(SourceSummary):
    config: dict[str, Any]
    secret_name: str | None
