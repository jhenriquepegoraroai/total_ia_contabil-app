"""
RAG — orquestrador da resposta.

Fluxo (espelha o `core_logic.py` da Bella original com adaptações):

    pergunta + referencia + tenant_config + datasource + llm
        │
        ▼
    1. Reformulação opcional (prompt_formatacao, temperature=0)
    2. Classificação → categoria (int | None)
    3. Roteamento por categoria:
        a) resposta_padrao[cat]    → retorna direto
        b) prompts_por_categoria[cat] + dados_estruturados → gera com GPT
        c) categoria de esclarecimento → retorna prompt_esclarecimento
        d) busca por embeddings (default + categoria 51/65/68 → pattern fixo)
    4. Geração GPT com prompt_principal e contexto = chunks
    5. Cita fontes (file_name + data_valida)

Nunca inventa dados (RULES.md #14): se top-K abaixo do threshold ou
estruturado vazio, retorna `mensagem_nao_encontrada` configurada.
"""

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from api import config as app_config
from api.llm import LLMClient
from api.tenants.datasources.base import DataSource
from api.tenants.models import TenantConfig
from .classifier import classificar_pergunta


# Categorias especiais herdadas do domínio Lello — outros tenants podem
# customizar via `prompts_por_categoria` e `respostas_padrao`.
CAT_DADOS_CADASTRAIS = 0
CAT_AREAS = 42
CAT_ASSEMBLEIA = 51
CAT_EDITAL_CONTEUDO = 65
CAT_EDITAL_DATA = 67
CAT_EDITAL_VS_ATA = 68
CAT_CARTEIRA = 70  # pergunta sobre a carteira inteira (cross-condomínio)
CAT_ESCLARECIMENTO = -1

# Busca de carteira varre vários condomínios — precisa de mais chunks que a
# busca de 1 condomínio para o modelo conseguir listar/comparar entre eles.
CARTEIRA_TOP_K = 24


@dataclass
class Citacao:
    file_name: str
    record_id: str | None = None
    data_valida: str | None = None
    similarity: float | None = None


@dataclass
class RAGResposta:
    resposta: str
    categoria: int | None
    citacoes: list[Citacao] = field(default_factory=list)
    via: str = "embeddings"  # 'resposta_padrao' | 'estruturado' | 'esclarecimento' | 'embeddings' | 'pattern'


async def responder(
    *,
    pergunta: str,
    referencia: str,
    tenant_config: TenantConfig,
    datasource: DataSource,
    llm: LLMClient,
) -> RAGResposta:
    """Entry point principal. Não levanta — sempre retorna RAGResposta."""
    pergunta = (pergunta or "").strip()
    if not pergunta:
        return RAGResposta(
            resposta=tenant_config.mensagem_nao_encontrada,
            categoria=None,
            via="esclarecimento",
        )

    # 1. Classificação
    categoria = await classificar_pergunta(pergunta, tenant_config, llm)
    logger.info(
        f"[{tenant_config.tenant_id}] ref={referencia} cat={categoria} pergunta={pergunta[:80]!r}"
    )

    # 2. Resposta padrão (atalho)
    if categoria is not None and categoria in tenant_config.respostas_padrao:
        return RAGResposta(
            resposta=tenant_config.respostas_padrao[categoria],
            categoria=categoria,
            via="resposta_padrao",
        )

    # 3. Esclarecimento
    if categoria == CAT_ESCLARECIMENTO:
        return RAGResposta(
            resposta=tenant_config.prompt_esclarecimento,
            categoria=categoria,
            via="esclarecimento",
        )

    # 4. Categorias com query estruturada (cat 0 e 42 da Lello)
    if categoria == CAT_DADOS_CADASTRAIS and "condominios" in tenant_config.schemas_estruturados:
        return await _responder_estruturado(
            schema_key="condominios",
            categoria=categoria,
            pergunta=pergunta,
            referencia=referencia,
            tenant_config=tenant_config,
            datasource=datasource,
            llm=llm,
        )

    if categoria == CAT_AREAS and "areas" in tenant_config.schemas_estruturados:
        return await _responder_estruturado(
            schema_key="areas",
            categoria=categoria,
            pergunta=pergunta,
            referencia=referencia,
            tenant_config=tenant_config,
            datasource=datasource,
            llm=llm,
        )

    # 5. Categorias com pattern fixo (assembleia, edital — sem embeddings)
    if categoria == CAT_ASSEMBLEIA:
        return await _responder_pattern(
            pattern_include=None,
            pattern_exclude="%edital%",
            regex_pattern=r"(^|[- ])(age|ago|ata)([- ]|$)",
            only_latest=True,
            categoria=categoria,
            pergunta=pergunta,
            referencia=referencia,
            tenant_config=tenant_config,
            datasource=datasource,
            llm=llm,
        )

    if categoria == CAT_EDITAL_CONTEUDO:
        return await _responder_pattern(
            pattern_include="%edital%",
            pattern_exclude=None,
            regex_pattern=None,
            only_latest=True,
            categoria=categoria,
            pergunta=pergunta,
            referencia=referencia,
            tenant_config=tenant_config,
            datasource=datasource,
            llm=llm,
        )

    if categoria == CAT_EDITAL_DATA:
        data = await datasource.buscar_data_mais_recente(referencia, "%edital%")
        if data is None:
            return RAGResposta(
                resposta=tenant_config.mensagem_nao_encontrada,
                categoria=categoria,
                via="pattern",
            )
        return RAGResposta(
            resposta=f"O edital mais recente é de {data.strftime('%d/%m/%Y')}.",
            categoria=categoria,
            via="pattern",
        )

    # 6. Carteira — busca cross-condomínio (pergunta sobre a carteira inteira)
    if categoria == CAT_CARTEIRA:
        return await _responder_carteira(
            categoria=categoria,
            pergunta=pergunta,
            tenant_config=tenant_config,
            datasource=datasource,
            llm=llm,
        )

    # 7. Default — busca por embeddings
    return await _responder_embeddings(
        categoria=categoria,
        pergunta=pergunta,
        referencia=referencia,
        tenant_config=tenant_config,
        datasource=datasource,
        llm=llm,
    )


# =============================================================================
# Caminho: dados estruturados
# =============================================================================
async def _responder_estruturado(
    *,
    schema_key: str,
    categoria: int,
    pergunta: str,
    referencia: str,
    tenant_config: TenantConfig,
    datasource: DataSource,
    llm: LLMClient,
) -> RAGResposta:
    rows = await datasource.buscar_dados_estruturados(schema_key, referencia)
    if not rows:
        # Fallback: a categoria pediu dado estruturado mas não há cadastro
        # para esta referência. Em vez de devolver "sem documento", tenta
        # responder com busca por embeddings nos documentos do condomínio.
        # Útil quando a info pedida (ex: nome do síndico) está só na ata.
        logger.info(
            f"[{tenant_config.tenant_id}] estruturado vazio para "
            f"schema={schema_key} ref={referencia} → fallback para embeddings"
        )
        return await _responder_embeddings(
            categoria=categoria,
            pergunta=pergunta,
            referencia=referencia,
            tenant_config=tenant_config,
            datasource=datasource,
            llm=llm,
        )

    contexto = _formatar_dados_estruturados(rows)
    system_prompt = tenant_config.prompts_por_categoria.get(
        categoria, tenant_config.prompt_principal
    )
    resposta = await llm.gerar_resposta(
        system_prompt=system_prompt,
        contexto=contexto,
        pergunta=pergunta,
        temperature=tenant_config.rag.completion_temperature,
    )
    return RAGResposta(resposta=resposta, categoria=categoria, via="estruturado")


# =============================================================================
# Caminho: pattern (assembleia, edital)
# =============================================================================
async def _responder_pattern(
    *,
    pattern_include: str | None,
    pattern_exclude: str | None,
    regex_pattern: str | None,
    only_latest: bool,
    categoria: int,
    pergunta: str,
    referencia: str,
    tenant_config: TenantConfig,
    datasource: DataSource,
    llm: LLMClient,
) -> RAGResposta:
    rows = await datasource.buscar_paragrafos_por_pattern(
        referencia=referencia,
        file_pattern_include=pattern_include,
        file_pattern_exclude=pattern_exclude,
        regex_pattern=regex_pattern,
        only_latest_date=only_latest,
    )
    if not rows:
        return RAGResposta(
            resposta=tenant_config.resposta_sem_documento,
            categoria=categoria,
            via="pattern",
        )

    contexto = _formatar_chunks(rows)
    citacoes = _citacoes_de(rows)
    resposta = await llm.gerar_resposta(
        system_prompt=tenant_config.prompt_principal,
        contexto=contexto,
        pergunta=pergunta,
        temperature=tenant_config.rag.completion_temperature,
    )
    return RAGResposta(
        resposta=resposta,
        categoria=categoria,
        citacoes=citacoes,
        via="pattern",
    )


# =============================================================================
# Caminho: busca por embeddings (default)
# =============================================================================
async def _responder_embeddings(
    *,
    categoria: int | None,
    pergunta: str,
    referencia: str,
    tenant_config: TenantConfig,
    datasource: DataSource,
    llm: LLMClient,
) -> RAGResposta:
    pergunta_para_busca = pergunta
    # Reformulação opcional — só faz sentido para busca por embeddings.
    if tenant_config.prompt_formatacao:
        try:
            pergunta_para_busca = await llm.reformular_pergunta(
                system_prompt=tenant_config.prompt_formatacao,
                pergunta=pergunta,
            )
        except Exception as exc:
            logger.warning(f"Falha reformulando pergunta, usando original: {exc}")

    embedding = await llm.embed_query(pergunta_para_busca)

    chunks = await datasource.busca_similaridade(
        referencia=referencia,
        query_embedding=embedding,
        top_k=tenant_config.rag.top_k,
        threshold=tenant_config.rag.similarity_threshold,
        file_pattern_exclude="%edital%",  # editais têm caminho próprio (cat 65/67/68)
    )

    if not chunks:
        # Não confunde "sem documento nenhum" (resposta_sem_documento) com "tem
        # documento mas nada relevante" (mensagem_nao_encontrada). Aqui é o segundo.
        return RAGResposta(
            resposta=tenant_config.mensagem_nao_encontrada,
            categoria=categoria,
            via="embeddings",
        )

    contexto = _formatar_chunks(chunks)
    citacoes = _citacoes_de(chunks)
    resposta = await llm.gerar_resposta(
        system_prompt=tenant_config.prompt_principal,
        contexto=contexto,
        pergunta=pergunta,
        temperature=tenant_config.rag.completion_temperature,
        max_tokens=app_config.DEFAULT_TOP_K * 100,  # ajuste fino — proporção a chunks
    )
    return RAGResposta(
        resposta=resposta,
        categoria=categoria,
        citacoes=citacoes,
        via="embeddings",
    )


# =============================================================================
# Caminho: carteira (cross-condomínio)
# =============================================================================
async def _responder_carteira(
    *,
    categoria: int | None,
    pergunta: str,
    tenant_config: TenantConfig,
    datasource: DataSource,
    llm: LLMClient,
) -> RAGResposta:
    """
    Responde perguntas sobre a carteira inteira do tenant (vários condomínios).

    Busca sem filtro de referência, agrupa os chunks por condomínio (resolvendo
    o nome quando há cadastro) e deixa o modelo listar/comparar entre eles.
    """
    pergunta_para_busca = pergunta
    if tenant_config.prompt_formatacao:
        try:
            pergunta_para_busca = await llm.reformular_pergunta(
                system_prompt=tenant_config.prompt_formatacao,
                pergunta=pergunta,
            )
        except Exception as exc:
            logger.warning(f"Falha reformulando pergunta (carteira), usando original: {exc}")

    embedding = await llm.embed_query(pergunta_para_busca)

    chunks = await datasource.busca_similaridade_carteira(
        query_embedding=embedding,
        top_k=CARTEIRA_TOP_K,
        threshold=tenant_config.rag.similarity_threshold,
        file_pattern_exclude="%edital%",  # editais têm caminho próprio (cat 65/67/68)
    )

    if not chunks:
        return RAGResposta(
            resposta=tenant_config.mensagem_nao_encontrada,
            categoria=categoria,
            via="carteira",
        )

    nomes = await _resolver_nomes_condominios(chunks, tenant_config, datasource)
    contexto = _formatar_chunks_carteira(chunks, nomes)
    citacoes = _citacoes_de(chunks)
    system_prompt = tenant_config.prompts_por_categoria.get(
        CAT_CARTEIRA, tenant_config.prompt_principal
    )
    resposta = await llm.gerar_resposta(
        system_prompt=system_prompt,
        contexto=contexto,
        pergunta=pergunta,
        temperature=tenant_config.rag.completion_temperature,
        max_tokens=CARTEIRA_TOP_K * 100,
    )
    return RAGResposta(
        resposta=resposta,
        categoria=categoria,
        citacoes=citacoes,
        via="carteira",
    )


async def _resolver_nomes_condominios(
    chunks: list[dict[str, Any]],
    tenant_config: TenantConfig,
    datasource: DataSource,
) -> dict[str, str]:
    """
    Mapeia `referencia` → nome do condomínio, best-effort.

    Usa a tabela estruturada `condominios` quando o tenant a tem cadastrada.
    Se não houver cadastro (ou schema), cai para "Condomínio {referencia}".
    """
    referencias = {c.get("referencia") for c in chunks if c.get("referencia")}
    nomes: dict[str, str] = {}
    tem_schema = "condominios" in tenant_config.schemas_estruturados
    for ref in referencias:
        nome = None
        if tem_schema:
            try:
                rows = await datasource.buscar_dados_estruturados("condominios", ref)
                if rows:
                    nome = rows[0].get("nome") or rows[0].get("nome_condominio")
            except Exception as exc:
                logger.warning(f"Falha resolvendo nome do condomínio ref={ref}: {exc}")
        nomes[ref] = nome or f"Condomínio {ref}"
    return nomes


# =============================================================================
# Helpers
# =============================================================================
def _formatar_chunks(rows: list[dict[str, Any]]) -> str:
    """Formata chunks em texto para o contexto do GPT."""
    partes = []
    for r in rows:
        data = r.get("data_valida")
        data_str = data.strftime("%d/%m/%Y") if data else "data desconhecida"
        partes.append(
            f"[{r.get('file_name', '?')} | {data_str}]\n{r.get('paragraph', '')}"
        )
    return "\n\n---\n\n".join(partes)


def _formatar_chunks_carteira(
    rows: list[dict[str, Any]], nomes: dict[str, str]
) -> str:
    """
    Formata chunks agrupados por condomínio, para o modelo comparar entre eles.

    Cada bloco começa com o nome do condomínio (+ referência), seguido dos
    parágrafos daquele condomínio. Preserva a ordem de similaridade dentro
    de cada grupo.
    """
    grupos: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        ref = r.get("referencia") or "?"
        grupos.setdefault(ref, []).append(r)

    partes: list[str] = []
    for ref, chunks_grupo in grupos.items():
        nome = nomes.get(ref, f"Condomínio {ref}")
        linhas = [f"=== {nome} (referência {ref}) ==="]
        for r in chunks_grupo:
            data = r.get("data_valida")
            data_str = data.strftime("%d/%m/%Y") if data else "data desconhecida"
            linhas.append(
                f"[{r.get('file_name', '?')} | {data_str}]\n{r.get('paragraph', '')}"
            )
        partes.append("\n".join(linhas))
    return "\n\n---\n\n".join(partes)


def _formatar_dados_estruturados(rows: list[dict[str, Any]]) -> str:
    """Formata linhas de tabela como key: value."""
    partes = []
    for i, row in enumerate(rows, start=1):
        linhas = [f"{k}: {v}" for k, v in row.items() if v is not None and k != "tenant_id"]
        partes.append(f"[Registro {i}]\n" + "\n".join(linhas))
    return "\n\n".join(partes)


def _citacoes_de(rows: list[dict[str, Any]]) -> list[Citacao]:
    return [
        Citacao(
            file_name=r.get("file_name", "?"),
            record_id=r.get("record_id"),
            data_valida=(
                r["data_valida"].strftime("%Y-%m-%d") if r.get("data_valida") else None
            ),
            similarity=float(r["similarity"]) if "similarity" in r else None,
        )
        for r in rows
    ]
