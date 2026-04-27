"""Testes do content_hash — base da idempotência do pipeline."""

from ingestion.idempotency import content_hash


def test_hash_deterministico():
    h1 = content_hash("lello", "111", "ata.pdf", "p1_b1", "Texto do parágrafo")
    h2 = content_hash("lello", "111", "ata.pdf", "p1_b1", "Texto do parágrafo")
    assert h1 == h2


def test_hash_muda_com_paragraph():
    h1 = content_hash("lello", "111", "ata.pdf", "p1_b1", "Texto A")
    h2 = content_hash("lello", "111", "ata.pdf", "p1_b1", "Texto B")
    assert h1 != h2


def test_hash_diferente_entre_tenants():
    """Mesmo conteúdo em tenants diferentes não pode colidir."""
    h_lello = content_hash("lello", "111", "ata.pdf", "p1_b1", "Igual")
    h_apsa = content_hash("apsa", "111", "ata.pdf", "p1_b1", "Igual")
    assert h_lello != h_apsa


def test_hash_diferente_entre_referencias():
    h1 = content_hash("lello", "111", "ata.pdf", "p1_b1", "Igual")
    h2 = content_hash("lello", "222", "ata.pdf", "p1_b1", "Igual")
    assert h1 != h2


def test_hash_diferente_entre_records():
    h1 = content_hash("lello", "111", "ata.pdf", "p1_b1", "Igual")
    h2 = content_hash("lello", "111", "ata.pdf", "p1_b2", "Igual")
    assert h1 != h2


def test_separador_evita_colisao_de_concatenacao():
    """
    Sem separador entre campos, ('ab','cd') colidiria com ('abc','d').
    O separador \\x1f resolve isso.
    """
    h1 = content_hash("ab", "cd", "f", "r", "p")
    h2 = content_hash("abc", "d", "f", "r", "p")
    assert h1 != h2


def test_hash_e_hex_64_chars():
    """SHA-256 em hex sempre dá 64 chars."""
    h = content_hash("lello", "111", "ata.pdf", "p1_b1", "Texto")
    assert len(h) == 64
    int(h, 16)  # não levanta = é hex válido
