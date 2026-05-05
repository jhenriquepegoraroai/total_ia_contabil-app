"""
Pipeline do Bella Cobranças — Document AI → GPT-4o → JSON estruturado.

Versão inicial (Fatia 1): suporta apenas PDFs ≤15 páginas (limite síncrono
do Document AI). PDFs maiores levantam `ValueError` com mensagem clara —
suporte a batch via GCS entra na próxima rodada.

Adaptado do Decob original (`main.py::CondominioDataPipeline`). Aqui o
construtor recebe `TenantCobrancasConfig` (não lê env). OpenAI usa a
chave global da Bella (`OPEN_AI_KEY`) — billing único, não passa pelo
cliente do tenant.
"""

import json
from typing import Any

from loguru import logger
from openai import OpenAI

from api import config as app_config
from api.cobrancas.documentai import DocumentAIClient
from api.cobrancas.prompts import EXTRACTION_PROMPT
from api.cobrancas.schema import TARGET_SCHEMA, CobrancaResultado
from api.tenants.models import TenantCobrancasConfig


# Configurações do pipeline (mesmas constantes do Decob original).
MAX_TEXT_LENGTH = 10000          # caracteres máximos do full_text enviado ao LLM
MAX_TABLES_PER_CALL = 10         # tabelas máximas por chamada
EXTRACTION_MODEL = "gpt-4o"      # modelo (override via TenantCobrancasConfig.extraction_model — futuro)


class PipelineError(RuntimeError):
    """Erro de processamento — wrap de erros das libs subjacentes."""


class CobrancasPipeline:
    """Pipeline de extração de PDFs de cobrança condominial por tenant."""

    def __init__(self, tenant_cobrancas: TenantCobrancasConfig):
        self.docai = DocumentAIClient(tenant_cobrancas)
        self.openai = OpenAI(api_key=app_config.OPEN_AI_KEY)
        self.model = EXTRACTION_MODEL

    def processar_pdf(self, pdf_bytes: bytes, qtde_paginas: int) -> CobrancaResultado:
        """
        Processa um PDF e retorna o resultado estruturado.

        Levanta:
          - ValueError: PDF maior que o limite síncrono.
          - PipelineError: falha na extração (Document AI ou LLM).
        """
        if qtde_paginas > self.docai.SYNC_PAGE_LIMIT:
            raise ValueError(
                f"PDF tem {qtde_paginas} páginas — máximo suportado nesta versão "
                f"é {self.docai.SYNC_PAGE_LIMIT} (síncrono). Suporte a PDFs grandes "
                f"via batch GCS entra na próxima atualização."
            )

        logger.info(f"[cobrancas] [1/2] Document AI extract ({qtde_paginas} págs)")
        try:
            doc_data = self.docai.extract_from_bytes(pdf_bytes)
        except Exception as exc:
            logger.error(f"[cobrancas] Document AI falhou: {exc}")
            raise PipelineError(f"Document AI: {exc}") from exc

        logger.info(f"[cobrancas] [2/2] Mapeamento via {self.model}")
        try:
            extraido = self._mapear_com_llm(
                full_text=doc_data["full_text"],
                tables=doc_data["tables"],
                form_fields=doc_data["form_fields"],
            )
        except Exception as exc:
            logger.error(f"[cobrancas] LLM falhou: {exc}")
            raise PipelineError(f"LLM: {exc}") from exc

        resultado = CobrancaResultado(**extraido)
        # Recalcula metadata pra fonte da verdade.
        total_valor = sum(
            r.VALOR_ORIGINAL for r in resultado.registros if r.VALOR_ORIGINAL is not None
        )
        resultado.metadata.total_registros = len(resultado.registros)
        resultado.metadata.total_valor = round(total_valor, 2)
        return resultado

    # =========================================================================
    # LLM
    # =========================================================================
    def _mapear_com_llm(
        self,
        *,
        full_text: str,
        tables: list[dict[str, Any]],
        form_fields: list[dict[str, str]],
    ) -> dict[str, Any]:
        full_text_t = full_text[:MAX_TEXT_LENGTH]
        if len(full_text) > MAX_TEXT_LENGTH:
            logger.warning(
                f"[cobrancas] full_text truncado de {len(full_text)} pra {MAX_TEXT_LENGTH} chars"
            )

        prompt = EXTRACTION_PROMPT.format(
            schema=json.dumps(TARGET_SCHEMA, indent=2, ensure_ascii=False),
            full_text=full_text_t,
            tables_text=_format_tables(tables[:MAX_TABLES_PER_CALL]),
            form_fields=_format_form_fields(form_fields),
        )

        completion = self.openai.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Responda APENAS com JSON válido, sem markdown."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        content = completion.choices[0].message.content or "{}"
        return json.loads(content)


# =============================================================================
# Helpers de formatação pro prompt
# =============================================================================
def _format_tables(tables: list[dict[str, Any]]) -> str:
    if not tables:
        return "(nenhuma tabela detectada)"
    out: list[str] = []
    for i, t in enumerate(tables, 1):
        out.append(f"--- Tabela {i} (página {t.get('page', '?')}) ---")
        for row in t.get("header_rows", []):
            out.append("HEADER: " + " | ".join(row))
        for row in t.get("body_rows", []):
            out.append("ROW: " + " | ".join(row))
    return "\n".join(out)


def _format_form_fields(fields: list[dict[str, str]]) -> str:
    if not fields:
        return "(nenhum campo de formulário detectado)"
    return "\n".join(f"- {f['name']}: {f['value']}" for f in fields)
