"""
Cliente Google Document AI — extração de texto/tabelas/form fields de PDFs.

Versão multi-tenant: o construtor recebe `TenantCobrancasConfig` (não lê
env). Cada tenant usa as próprias credenciais. Por enquanto suporta só
processamento síncrono (≤15 páginas — limite da API sync). Batch via GCS
(PDFs grandes) entra na próxima rodada.

Adaptado do projeto Decob original. Limpezas obrigatórias aplicadas:
  - print → loguru.logger
  - sem secrets hardcoded (creds vêm do tenant_config)
  - sem `except Exception: pass`
"""

from typing import Any

from loguru import logger

from api.tenants.models import TenantCobrancasConfig


class DocumentAIClient:
    """Cliente Document AI por tenant. Síncrono, ≤15 páginas por chamada."""

    SYNC_PAGE_LIMIT = 15

    def __init__(self, config: TenantCobrancasConfig):
        if not config.gcp_credentials_json:
            raise ValueError("Tenant sem service account JSON cadastrado.")
        if not config.gcp_project_id or not config.processor_id:
            raise ValueError("Tenant sem gcp_project_id ou processor_id.")

        # Imports lazy — google-cloud-documentai é dep pesada (~50MB).
        from google.cloud import documentai_v1 as documentai
        from google.oauth2 import service_account

        self._documentai = documentai
        self.project_id = config.gcp_project_id
        self.location = config.gcp_location
        self.processor_id = config.processor_id

        credentials = service_account.Credentials.from_service_account_info(
            config.gcp_credentials_json
        )
        endpoint = f"{self.location}-documentai.googleapis.com"
        self.client = documentai.DocumentProcessorServiceClient(
            credentials=credentials,
            client_options={"api_endpoint": endpoint},
        )
        self.processor_name = self.client.processor_path(
            self.project_id, self.location, self.processor_id
        )
        logger.info(
            f"[cobrancas/documentai] Cliente inicializado "
            f"project={self.project_id} location={self.location} processor={self.processor_id}"
        )

    def extract_from_bytes(self, pdf_bytes: bytes) -> dict[str, Any]:
        """
        Extrai dados de um PDF inteiro (bytes). Síncrono.

        Retorna `{"full_text": str, "tables": list, "form_fields": list}`.
        Levanta `ValueError` se o PDF tem mais que `SYNC_PAGE_LIMIT` páginas.
        """
        documentai = self._documentai
        raw_document = documentai.RawDocument(
            content=pdf_bytes,
            mime_type="application/pdf",
        )
        request = documentai.ProcessRequest(
            name=self.processor_name,
            raw_document=raw_document,
        )
        result = self.client.process_document(request=request)
        document = result.document

        return {
            "full_text": document.text or "",
            "tables": _extract_tables(document),
            "form_fields": _extract_form_fields(document),
        }


# =============================================================================
# Helpers — parse do `Document` proto pra dicts simples
# =============================================================================
def _extract_tables(document) -> list[dict[str, Any]]:
    """Extrai tabelas estruturadas (header rows + body rows) de cada página."""
    tables_out: list[dict[str, Any]] = []
    for page_idx, page in enumerate(document.pages):
        for table in page.tables:
            tables_out.append({
                "page": page_idx + 1,
                "header_rows": [_row_to_text(r, document.text) for r in table.header_rows],
                "body_rows": [_row_to_text(r, document.text) for r in table.body_rows],
            })
    return tables_out


def _extract_form_fields(document) -> list[dict[str, str]]:
    """Extrai pares chave/valor (form fields) de cada página."""
    out: list[dict[str, str]] = []
    for page in document.pages:
        for field in page.form_fields:
            name = _text_anchor(field.field_name, document.text).strip() if field.field_name else ""
            value = _text_anchor(field.field_value, document.text).strip() if field.field_value else ""
            if name or value:
                out.append({"name": name, "value": value})
    return out


def _row_to_text(row, full_text: str) -> list[str]:
    return [_text_anchor(cell.layout, full_text).strip() for cell in row.cells]


def _text_anchor(layout, full_text: str) -> str:
    """Resolve um TextAnchor → string concatenando os segments."""
    if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
        return ""
    chunks: list[str] = []
    for seg in layout.text_anchor.text_segments:
        start = int(seg.start_index) if seg.start_index else 0
        end = int(seg.end_index) if seg.end_index else 0
        chunks.append(full_text[start:end])
    return "".join(chunks)
