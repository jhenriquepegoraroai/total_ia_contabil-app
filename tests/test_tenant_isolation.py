"""
Testes de isolamento cross-tenant — RULES.md regra crítica #39.

Estes testes validam o invariante mais importante do sistema: dados de um
tenant NUNCA podem ser visíveis para outro tenant. Falha aqui é showstopper.

Cenários cobertos:
  1. Adapter do tenant A faz busca de embeddings → não vê linhas do tenant B
  2. Adapter do tenant A faz busca de dados estruturados → não vê linhas do B
  3. Adapter do tenant A em uma sessão SEM `app.current_tenant` setado → RLS
     bloqueia tudo (defense-in-depth: WHERE tenant_id no SQL + RLS)
  4. Buscar referência que existe no tenant B mas não no tenant A → zero linhas

Pré-requisito: Postgres rodando com migration 001_init.sql aplicada.
Variáveis de ambiente: DATABASE_URL apontando para um banco DE TESTE.

Para rodar apenas estes testes:
    pytest tests/test_tenant_isolation.py -v -m integration

Para pular se Postgres não estiver disponível:
    pytest tests/ -m "not integration"
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.tenants.datasources.postgres_pgvector import PostgresPgvectorDataSource

pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures de banco
# =============================================================================
@pytest_asyncio.fixture(scope="module")
async def engine():
    """Engine compartilhado entre testes do módulo."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        pytest.skip("DATABASE_URL não definida — pulando integration tests.")
    eng = create_async_engine(db_url, pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def seed_dois_tenants(session_factory):
    """
    Cria 2 tenants com dados distintos. Limpa antes e depois.

    Estrutura:
      - tenant 'tA' tem condominio referencia '111' com 2 chunks de embeddings
      - tenant 'tB' tem condominio referencia '222' com 2 chunks de embeddings
      - Ambos têm dados estruturados em `condominios`.

    O seed roda COM `app.current_tenant` setado, um tenant de cada vez. Não é
    detalhe de estilo: `condominios` e `documents_embeddings` têm
    `FORCE ROW LEVEL SECURITY` e policy `WITH CHECK (tenant_id =
    current_tenant())`, então INSERT sem tenant setado é recusado.

    A alternativa — conectar como superusuário para semear — quebraria
    `test_sem_app_current_tenant_rls_bloqueia`, porque superusuário ignora RLS
    e enxergaria todas as linhas. Com uma role só, semear por fora e verificar
    o bloqueio de RLS são requisitos incompatíveis; semear pelo mesmo caminho
    da aplicação resolve os dois e ainda exercita a policy de escrita.
    """
    embedding_a1 = [0.1] * 3072
    embedding_a2 = [0.2] * 3072
    embedding_b1 = [0.9] * 3072
    embedding_b2 = [0.8] * 3072

    linhas = {
        "tA": [
            ("111", "r1", "paragrafo do tenant A item 1", embedding_a1),
            ("111", "r2", "paragrafo do tenant A item 2", embedding_a2),
        ],
        "tB": [
            ("222", "r1", "paragrafo do tenant B item 1", embedding_b1),
            ("222", "r2", "paragrafo do tenant B item 2", embedding_b2),
        ],
    }
    condominios = {"tA": ("111", "Cond A111"), "tB": ("222", "Cond B222")}

    await _limpar(session_factory)

    # `tenants` não tem RLS (ver 001_init.sql) — pode ser semeado sem contexto.
    async with session_factory() as s:
        await s.execute(
            text(
                "INSERT INTO tenants (id, nome_empresa, enabled) "
                "VALUES ('tA','Tenant A',true), ('tB','Tenant B',true)"
            )
        )
        await s.commit()

    for tid in ("tA", "tB"):
        s = await _open_tenant_session(session_factory, tid)
        try:
            ref, nome = condominios[tid]
            await s.execute(
                text(
                    "INSERT INTO condominios (tenant_id, referencia, nome) "
                    "VALUES (:tid, :ref, :nome)"
                ),
                {"tid": tid, "ref": ref, "nome": nome},
            )
            for ref, rid, par, emb in linhas[tid]:
                await s.execute(
                    text(
                        "INSERT INTO documents_embeddings "
                        "(tenant_id, referencia, file_name, record_id, paragraph, "
                        "embedding, content_hash) "
                        "VALUES (:tid, :ref, :fn, :rid, :par, CAST(:emb AS vector), :hash)"
                    ),
                    {
                        "tid": tid,
                        "ref": ref,
                        "fn": f"doc_{tid}.pdf",
                        "rid": rid,
                        "par": par,
                        "emb": "[" + ",".join(str(x) for x in emb) + "]",
                        "hash": f"hash_{tid}_{rid}",
                    },
                )
            await s.commit()
        finally:
            await s.close()

    yield {
        "tA": {"ref": "111", "embedding_query": embedding_a1},
        "tB": {"ref": "222", "embedding_query": embedding_b1},
    }

    await _limpar(session_factory)


async def _limpar(session_factory) -> None:
    """
    Remove os dados de teste. DELETE também passa por RLS nas tabelas com
    FORCE, então cada tenant é limpo dentro do próprio contexto.
    """
    for tid in ("tA", "tB"):
        s = await _open_tenant_session(session_factory, tid)
        try:
            await s.execute(
                text("DELETE FROM documents_embeddings WHERE tenant_id = :tid"),
                {"tid": tid},
            )
            await s.execute(
                text("DELETE FROM condominios WHERE tenant_id = :tid"), {"tid": tid}
            )
            await s.commit()
        finally:
            await s.close()

    async with session_factory() as s:
        await s.execute(text("DELETE FROM tenant_configs WHERE tenant_id IN ('tA','tB')"))
        await s.execute(text("DELETE FROM tenants WHERE id IN ('tA','tB')"))
        await s.commit()


async def _open_tenant_session(session_factory, tenant_id: str) -> AsyncSession:
    """Abre sessão setando `app.current_tenant` (mesmo padrão de `api.db.tenant_session`)."""
    s = session_factory()
    await s.begin()
    await s.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
    return s


# =============================================================================
# Testes de isolamento
# =============================================================================
async def test_busca_similaridade_isola_tenants(session_factory, seed_dois_tenants):
    """A busca por similaridade do tenant A não deve enxergar nada do tenant B."""
    s = await _open_tenant_session(session_factory, "tA")
    try:
        ds_a = PostgresPgvectorDataSource(tenant_id="tA", session=s)

        # Mesmo procurando em uma referência que SÓ EXISTE no tenant B,
        # o tenant A deve ver zero resultados.
        rows = await ds_a.busca_similaridade(
            referencia="222",  # essa referência é do tenant B!
            query_embedding=seed_dois_tenants["tB"]["embedding_query"],
            top_k=10,
            threshold=0.0,
        )
        assert rows == [], f"LEAK: tenant A viu dados do tenant B: {rows}"
    finally:
        await s.rollback()
        await s.close()


async def test_busca_similaridade_retorna_apenas_dados_proprios(session_factory, seed_dois_tenants):
    """Busca na própria referência do tenant A retorna SÓ chunks do tenant A."""
    s = await _open_tenant_session(session_factory, "tA")
    try:
        ds_a = PostgresPgvectorDataSource(tenant_id="tA", session=s)
        rows = await ds_a.busca_similaridade(
            referencia="111",
            query_embedding=seed_dois_tenants["tA"]["embedding_query"],
            top_k=10,
            threshold=0.0,
        )
        assert len(rows) == 2
        for r in rows:
            assert "tenant A" in r["paragraph"], f"LEAK: chunk de outro tenant: {r}"
    finally:
        await s.rollback()
        await s.close()


async def test_busca_carteira_isola_tenants(session_factory, seed_dois_tenants):
    """
    A busca de carteira (cross-condomínio) NÃO filtra por referência — depende
    exclusivamente do filtro por tenant_id + RLS. É o caminho mais sensível:
    tenant A varrendo "toda a carteira" jamais pode enxergar linha do tenant B.
    """
    s = await _open_tenant_session(session_factory, "tA")
    try:
        ds_a = PostgresPgvectorDataSource(tenant_id="tA", session=s)
        # Consulta com o embedding do tenant B e threshold 0 — se houvesse leak,
        # os chunks do B viriam no topo. Devem vir SÓ os do tenant A.
        rows = await ds_a.busca_similaridade_carteira(
            query_embedding=seed_dois_tenants["tB"]["embedding_query"],
            top_k=10,
            threshold=0.0,
        )
        assert len(rows) == 2, f"esperado 2 chunks do tenant A, veio {len(rows)}"
        for r in rows:
            assert r["referencia"] == "111", f"LEAK: referência de outro tenant: {r}"
            assert "tenant A" in r["paragraph"], f"LEAK: chunk de outro tenant: {r}"
    finally:
        await s.rollback()
        await s.close()


async def test_dados_estruturados_isolam_tenants(session_factory, seed_dois_tenants):
    """Tenant A consultando uma referência do B deve receber zero linhas."""
    s = await _open_tenant_session(session_factory, "tA")
    try:
        ds_a = PostgresPgvectorDataSource(tenant_id="tA", session=s)
        # ref '222' existe só em tenant B
        rows = await ds_a.buscar_dados_estruturados("condominios", "222")
        assert rows == [], f"LEAK: dados estruturados do tenant B vazaram: {rows}"
    finally:
        await s.rollback()
        await s.close()


async def test_sem_app_current_tenant_rls_bloqueia(session_factory, seed_dois_tenants):
    """
    Defesa em profundidade: mesmo que o adapter fosse bypassed, RLS bloqueia
    qualquer SELECT na tabela quando `app.current_tenant` não está setado.
    """
    async with session_factory() as s:
        # Sem `set_config('app.current_tenant', ...)` → current_tenant() retorna NULL
        # → policy NULL = tenant_id é falso → zero linhas.
        result = await s.execute(text("SELECT COUNT(*) FROM documents_embeddings"))
        count = result.scalar_one()
        assert count == 0, (
            f"LEAK CRÍTICO: SELECT sem tenant retornou {count} linhas. "
            "RLS não está aplicando. Auditar policies da migration!"
        )


async def test_paragrafos_por_pattern_isolam_tenants(session_factory, seed_dois_tenants):
    """Busca de parágrafos por pattern também respeita o isolamento."""
    s = await _open_tenant_session(session_factory, "tA")
    try:
        ds_a = PostgresPgvectorDataSource(tenant_id="tA", session=s)
        # Pattern bate em ambos os tenants (`%doc_%`), mas ref é do B
        rows = await ds_a.buscar_paragrafos_por_pattern(
            referencia="222",
            file_pattern_include="%doc_%",
        )
        assert rows == [], f"LEAK em buscar_paragrafos_por_pattern: {rows}"
    finally:
        await s.rollback()
        await s.close()


async def test_data_mais_recente_isola_tenants(session_factory, seed_dois_tenants):
    """Buscar data em ref do outro tenant retorna None (sem leak)."""
    s = await _open_tenant_session(session_factory, "tA")
    try:
        ds_a = PostgresPgvectorDataSource(tenant_id="tA", session=s)
        data = await ds_a.buscar_data_mais_recente(referencia="222", file_pattern_include="%doc%")
        assert data is None, f"LEAK em buscar_data_mais_recente: {data}"
    finally:
        await s.rollback()
        await s.close()
