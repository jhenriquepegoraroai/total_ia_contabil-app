"""
Cliente leve do Google Document AI — só o necessário pra validar credenciais.

O pipeline real de extração (chunking, batch via GCS, etc.) entra na Fase 4
e provavelmente vive em `api/cobrancas/pipeline.py`. Este arquivo é
proposital pequeno e síncrono.
"""

from typing import Any

from loguru import logger


def testar_conexao_documentai(
    *,
    gcp_credentials_json: dict[str, Any],
    gcp_project_id: str,
    gcp_location: str,
    processor_id: str,
) -> dict[str, Any]:
    """
    Tenta validar as credenciais Google Document AI fazendo um get_processor
    no processor configurado. Operação read-only, ~1s.

    Retorna `{"ok": bool, "detail": str, "metadata": {...}}` no mesmo
    formato do `adminTestarConexao` dos datasources, pra reusar o tipo
    no frontend.
    """
    try:
        from google.cloud import documentai_v1 as documentai
        from google.oauth2 import service_account
    except ImportError:
        return {
            "ok": False,
            "detail": (
                "Bibliotecas 'google-cloud-documentai' e 'google-auth' não "
                "instaladas no servidor. Adicione ao requirements.txt e refaça "
                "o build da imagem da API."
            ),
            "metadata": {},
        }

    try:
        credentials = service_account.Credentials.from_service_account_info(
            gcp_credentials_json
        )
    except Exception as exc:
        return {
            "ok": False,
            "detail": f"Service account JSON inválido: {exc}",
            "metadata": {},
        }

    endpoint = f"{gcp_location}-documentai.googleapis.com"
    try:
        client = documentai.DocumentProcessorServiceClient(
            credentials=credentials,
            client_options={"api_endpoint": endpoint},
        )
        processor_name = client.processor_path(
            gcp_project_id, gcp_location, processor_id
        )
        proc = client.get_processor(name=processor_name)
    except Exception as exc:
        # Mensagens de erro comuns do Google chegam aqui; preservamos o texto
        # original pra o usuário entender (PERMISSION_DENIED, NOT_FOUND, etc.).
        msg = str(exc)
        logger.warning(
            f"[cobrancas] Falha no test-connection (project={gcp_project_id}, "
            f"processor={processor_id}): {msg[:200]}"
        )
        return {
            "ok": False,
            "detail": _mensagem_amigavel(msg, processor_id, gcp_project_id),
            "metadata": {"endpoint": endpoint, "raw_error": msg},
        }

    return {
        "ok": True,
        "detail": (
            f"Conexão OK. Processor '{proc.display_name or processor_id}' "
            f"(tipo {proc.type_}) acessível."
        ),
        "metadata": {
            "endpoint": endpoint,
            "processor_name": proc.name,
            "processor_display_name": proc.display_name,
            "processor_type": proc.type_,
            "processor_state": str(proc.state),
        },
    }


def _mensagem_amigavel(raw_error: str, processor_id: str, project_id: str) -> str:
    """Traduz erros mais comuns do Google em mensagens compreensíveis."""
    low = raw_error.lower()
    if "permission" in low or "403" in low:
        return (
            f"Acesso negado. A service account não tem permissão pra acessar "
            f"o processor '{processor_id}' no projeto '{project_id}'. "
            f"Conceda a role 'Document AI API User' à conta."
        )
    if "not found" in low or "404" in low:
        return (
            f"Processor '{processor_id}' não encontrado no projeto "
            f"'{project_id}'. Confira se o ID e a região estão corretos."
        )
    if "invalid_grant" in low or "invalid_argument" in low:
        return (
            "Credenciais inválidas ou expiradas. Verifique se o JSON do "
            "service account está íntegro."
        )
    return f"Erro Google: {raw_error[:300]}"
