"""
Contrato de storage — quem implementa `signed_url_upload` e quem não.

O upload de áudio do módulo Atas depende de URL assinada: o arquivo vai do
browser direto para o bucket, sem passar pela API (áudio de assembleia de
duas horas passa de 100 MB). Antes, só o Azure Blob implementava, o que
prendia o Atas a uma nuvem específica — este teste existe para que essa
regressão não volte silenciosamente.
"""

import os

import pytest

from api.storage.base import Storage, StorageError
from api.storage.local import LocalStorage
from api.storage.s3 import S3Storage


def _implementa_upload_assinado(cls: type[Storage]) -> bool:
    """True se a classe sobrescreve o default que levanta NotImplementedError."""
    return cls.signed_url_upload is not Storage.signed_url_upload


def test_s3_implementa_upload_assinado():
    assert _implementa_upload_assinado(S3Storage), (
        "S3Storage precisa de signed_url_upload — sem ele o módulo Atas só "
        "funciona com Azure Blob."
    )


@pytest.mark.asyncio
async def test_local_nao_implementa_e_a_mensagem_diz_o_que_fazer():
    assert not _implementa_upload_assinado(LocalStorage)

    storage = LocalStorage(root=os.getcwd())
    with pytest.raises(NotImplementedError) as exc:
        # Precisa de await: sendo async, chamar sem aguardar só devolve a
        # corrotina e o erro nunca aparece.
        await storage.signed_url_upload("qualquer/chave.mp3")
    assert "s3" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_s3_presigned_upload_carrega_chave_e_expiracao(monkeypatch):
    """
    Presign é cálculo local — não chama a AWS. Com credenciais falsas dá para
    verificar que a URL aponta para a chave certa e carrega assinatura.

    Os marcadores `X-Amz-*` são de SigV4. O default do botocore aqui seria
    SigV2 contra o endpoint global, recusado por regiões pós-2014.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "chave-falsa-de-teste")

    storage = S3Storage(bucket="bucket-de-teste", region="sa-east-1")
    url = await storage.signed_url_upload(
        "lello/atas/123/audio.mp3", expires_in_seconds=900
    )

    assert "bucket-de-teste" in url
    assert "lello/atas/123/audio.mp3" in url
    assert "X-Amz-Expires=900" in url
    assert "X-Amz-Signature=" in url
    # Endpoint regional, não o global: presign SigV4 é assinado por região.
    assert "sa-east-1" in url


@pytest.mark.asyncio
async def test_s3_presigned_inclui_content_type_quando_informado(monkeypatch):
    """
    Com `content_type` na assinatura, o cliente é obrigado a mandar o mesmo
    header no PUT — divergência vira 403 na S3, não upload corrompido.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "chave-falsa-de-teste")

    storage = S3Storage(bucket="bucket-de-teste", region="sa-east-1")
    url = await storage.signed_url_upload(
        "lello/atas/123/audio.mp3", content_type="audio/mpeg"
    )

    assert "content-type" in url.lower()


def test_storage_error_existe_para_falha_de_provider():
    """Contrato de erro comum — usado pelo router de atas para responder 502."""
    assert issubclass(StorageError, Exception)
