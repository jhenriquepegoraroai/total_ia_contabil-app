"""
Schemas Pydantic do módulo Bella Atas.

Estes modelos espelham as tabelas do migration 010_atas.sql:
    atas → AtaSummary, AtaDetail
    atas_versoes → AtaVersao
    atas_acoes → AtaAcao
    atas_audios → AtaAudio
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# Estados possíveis da máquina (espelha o CHECK do DB).
AtaStatus = Literal[
    "rascunho",
    "aguardando_transcricao",
    "aguardando_geracao",
    "gerada",
    "revisao_consultor",
    "aguardando_sindico",
    "revisao_sindico",
    "comparando",
    "revisao_consultor_diff",
    "aguardando_presidente",
    "revisao_presidente",
    "revisao_consultor_final",
    "corrigindo",
    "registrada",
    "arquivada",
    "falhou",
]


VersaoTipo = Literal[
    "gerada",
    "edicao_consultor",
    "edicao_sindico",
    "edicao_presidente",
    "comparacao",
    "correcao_ortografica",
    "final",
]


# =============================================================================
# Inputs
# =============================================================================
class AtaCreate(BaseModel):
    """Criar uma ata em status='rascunho'. Insumos vêm depois (áudio + cabeçalho)."""

    titulo: str = Field(..., min_length=1, max_length=200)
    referencia: str | None = Field(
        default=None,
        description="Condomínio (referencia). Opcional — pode ser preenchido depois.",
    )
    sindico_user_id: UUID | None = None
    presidente_user_id: UUID | None = None


class AtaInsumosUpdate(BaseModel):
    """
    Atualiza os insumos da geração de uma ata.

    Pelo menos `cabecalho` e `resumo` precisam estar presentes na hora do
    `POST /atas/{id}/gerar` — mas aceitamos updates parciais aqui pra UX
    (consultor pode salvar rascunho e voltar depois).

    Campos espelham `InsumosGeracao` em pipeline_geracao.py.
    """

    cabecalho: str | None = None                 # HTML com dados oficiais do condomínio
    resumo: str | None = None                    # texto da assembleia (ou transcrição STT)
    edital: str | None = None                    # HTML com pauta (opcional)
    complemento: str | None = None               # dados complementares de votação/eleição
    assinatura_eletronica: bool | None = None
    nome_presidente: str | None = None
    nome_secretario: str | None = None
    cnpj_condominio: str | None = None


# =============================================================================
# Outputs
# =============================================================================
class AtaSummary(BaseModel):
    """Linha da listagem `/atas`. Sem conteúdo da ata, só metadados."""

    id: str
    tenant_id: str
    titulo: str
    referencia: str | None
    status: AtaStatus
    versao_atual_id: str | None
    consultor_user_id: str
    sindico_user_id: str | None
    presidente_user_id: str | None
    erro_detalhe: str | None
    created_at: datetime
    updated_at: datetime


class AtaDetail(AtaSummary):
    """Detalhe completo de uma ata, incluindo insumos (sem conteúdo das versões)."""

    insumos_json: dict[str, Any] = Field(default_factory=dict)


class AtaVersao(BaseModel):
    """Linha da tabela atas_versoes (incluindo conteúdo HTML)."""

    id: str
    ata_id: str
    tenant_id: str
    tipo: VersaoTipo
    conteudo_html: str
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    criada_por_user_id: str | None
    criada_em: datetime


class AtaAcao(BaseModel):
    """Linha do log de auditoria (atas_acoes)."""

    id: str
    ata_id: str
    tenant_id: str
    ator_user_id: str | None
    acao: str
    detalhe_json: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class AtaAudio(BaseModel):
    """Upload de áudio + estado da transcrição."""

    id: str
    ata_id: str
    tenant_id: str
    file_name: str
    file_size_bytes: int
    duracao_segundos: float | None
    status: Literal["uploaded", "transcribing", "done", "failed"]
    qtde_chunks: int | None
    custo_estimado_usd: float | None
    error_detail: str | None
    uploaded_by_user_id: str | None
    uploaded_at: datetime
    transcribed_at: datetime | None


# =============================================================================
# Audio upload (Fase 6 STT)
# =============================================================================
class AudioUploadRequest(BaseModel):
    """Pedido pra obter SAS URL de upload direto pro storage."""

    file_name: str = Field(..., min_length=1, max_length=255)
    file_size_bytes: int = Field(..., ge=1, le=2 * 1024 * 1024 * 1024)  # 2GB max
    content_type: str | None = None


class AudioUploadResponse(BaseModel):
    """Resposta com SAS URL — frontend faz PUT direto."""

    audio_id: str
    upload_url: str
    storage_key: str
    expires_in_seconds: int


# =============================================================================
# Workflow (Fase 7) — payloads
# =============================================================================
class ConteudoHTMLPayload(BaseModel):
    """Body genérico que carrega HTML — usado em edicao-consultor e devolver."""

    conteudo_html: str = Field(..., min_length=1)


class AprovarDiffPayload(BaseModel):
    """Decisão do consultor sobre o diff produzido pelo comparador."""

    decisao: Literal["aceitar", "rejeitar"]
    motivo: str | None = None              # opcional, pra rejeição
