"""
Módulo Bella Cobranças — extração de dados de PDFs de cobrança condominial
via Google Document AI + GPT-4o.

Subcomponentes:
  - documentai_client: testar conexão (usado pelo super admin no cadastro)
  - documentai: cliente real (DocumentAIClient) usado pelo pipeline
  - pipeline: orquestrador (Document AI → GPT-4o → JSON)
  - schema: TARGET_SCHEMA + modelos Pydantic do resultado
  - prompts: prompts do GPT-4o
  - jobs_service: persistência de jobs em PG
"""

from api.cobrancas.documentai_client import testar_conexao_documentai

__all__ = ["testar_conexao_documentai"]
