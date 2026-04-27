"""
Idempotência via content_hash.

Cada chunk é identificado por `(tenant_id, referencia, file_name, record_id)`.
O `content_hash = sha256(<chave> + paragraph)` permite detectar:
  - Chunk já existe e conteúdo igual → SKIP
  - Chunk já existe mas conteúdo mudou → REEMBED
  - Chunk não existe → EMBED novo

Espelha a lógica `leftanti` do script Spark original, mas com vantagem
adicional de detectar atualizações de conteúdo.
"""

import hashlib


def content_hash(
    tenant_id: str,
    referencia: str,
    file_name: str,
    record_id: str,
    paragraph: str,
) -> str:
    """
    Hash determinístico do conteúdo de um chunk.

    O hash inclui a chave de identidade para evitar colisões entre tenants
    (extremamente improváveis com SHA-256, mas defesa em profundidade).
    """
    h = hashlib.sha256()
    # Separador `\x1f` (Unit Separator ASCII) — não aparece em texto normal,
    # evita ambiguidade entre, por exemplo, ("a","bc") e ("ab","c").
    sep = b"\x1f"
    for parte in (tenant_id, referencia, file_name, record_id, paragraph):
        h.update(parte.encode("utf-8"))
        h.update(sep)
    return h.hexdigest()
