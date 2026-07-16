"""
Estimativa de custo OpenAI da ingestão de embeddings — deliverable D3 (João → Henrique).

Uso pretendido: rodar sobre uma AMOSTRA do corpus (uma pasta com alguns PDFs ou
.txt representativos), extrapolar para o volume total estimado e devolver uma
faixa de custo (baixo/médio/alto) para o slide do número.

NÃO faz parte do runtime da aplicação — é uma ferramenta de análise pontual.
Não chama a OpenAI: só conta tokens localmente com o MESMO encoder/limite do
pipeline (`ingestion/chunking.py`) e multiplica pelo preço vigente.

Exemplos:
    # Amostra de PDFs, extrapolando para 5.000 documentos no corpus:
    python -m scripts.estimar_custo_ingestao --sample-dir ./amostra --docs-total 5000

    # Sem amostra em disco — informando tokens/documento médios direto:
    python -m scripts.estimar_custo_ingestao --tokens-por-doc 3500 --docs-total 5000

Premissas ficam explícitas na saída — o Henrique ajusta o preço e o volume.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Reusa o encoder/limite oficiais do pipeline (mesma contagem de tokens da ingestão).
from ingestion.chunking import EMBEDDING_MAX_TOKENS, EMBEDDING_MODEL, contar_tokens

# Preço vigente de referência (USD por 1M de tokens) do text-embedding-3-large.
# CONFIRMAR na tabela oficial da OpenAI antes de usar no slide — muda com o tempo.
PRECO_PADRAO_POR_1M_USD = 0.13

# Faixa de incerteza aplicada sobre a estimativa central (±).
FAIXA_INCERTEZA = 0.25


def _ler_texto(caminho: Path) -> str:
    """Lê .txt direto; tenta extrair texto de .pdf via pypdf (dependência opcional)."""
    if caminho.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print(
                f"  [aviso] pypdf não instalado — pulando {caminho.name}. "
                "Instale com `pip install pypdf` ou use amostra em .txt.",
                file=sys.stderr,
            )
            return ""
        try:
            reader = PdfReader(str(caminho))
            return "\n".join((pagina.extract_text() or "") for pagina in reader.pages)
        except Exception as exc:  # noqa: BLE001 — ferramenta de análise, best-effort
            print(f"  [aviso] falha lendo {caminho.name}: {exc}", file=sys.stderr)
            return ""
    return caminho.read_text(encoding="utf-8", errors="ignore")


def _tokens_da_amostra(sample_dir: Path) -> tuple[int, int]:
    """Retorna (total_tokens, n_documentos) da amostra em disco."""
    arquivos = sorted(
        p for p in sample_dir.rglob("*") if p.suffix.lower() in {".pdf", ".txt"}
    )
    if not arquivos:
        raise SystemExit(f"Nenhum .pdf/.txt em {sample_dir}")

    total = 0
    for p in arquivos:
        texto = _ler_texto(p)
        # Espelha o truncate por chunk: nenhum input passa de MAX_TOKENS.
        tokens = min(contar_tokens(texto), EMBEDDING_MAX_TOKENS) if texto else 0
        total += tokens
        print(f"  {p.name}: {tokens} tokens")
    return total, len(arquivos)


def _formatar_usd(valor: float) -> str:
    return f"US$ {valor:,.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimativa de custo de embeddings.")
    parser.add_argument("--sample-dir", type=Path, help="Pasta com PDFs/TXT de amostra.")
    parser.add_argument(
        "--tokens-por-doc",
        type=int,
        help="Média de tokens por documento (alternativa a --sample-dir).",
    )
    parser.add_argument(
        "--docs-total",
        type=int,
        required=True,
        help="Nº estimado de documentos no corpus real.",
    )
    parser.add_argument(
        "--preco-por-1m",
        type=float,
        default=PRECO_PADRAO_POR_1M_USD,
        help=f"Preço USD por 1M tokens (default {PRECO_PADRAO_POR_1M_USD}).",
    )
    args = parser.parse_args()

    if args.sample_dir:
        print(f"Amostra: {args.sample_dir}")
        total_amostra, n_docs = _tokens_da_amostra(args.sample_dir)
        tokens_por_doc = total_amostra / n_docs if n_docs else 0
        print(f"\n  → {n_docs} docs na amostra, {total_amostra} tokens totais")
    elif args.tokens_por_doc:
        tokens_por_doc = float(args.tokens_por_doc)
    else:
        raise SystemExit("Informe --sample-dir OU --tokens-por-doc.")

    tokens_totais = tokens_por_doc * args.docs_total
    custo_central = (tokens_totais / 1_000_000) * args.preco_por_1m
    custo_baixo = custo_central * (1 - FAIXA_INCERTEZA)
    custo_alto = custo_central * (1 + FAIXA_INCERTEZA)

    print("\n" + "=" * 60)
    print("ESTIMATIVA DE CUSTO — INGESTÃO DE EMBEDDINGS")
    print("=" * 60)
    print(f"Modelo:              {EMBEDDING_MODEL}")
    print(f"Preço:               US$ {args.preco_por_1m}/1M tokens (confirmar vigente)")
    print(f"Tokens/documento:    {tokens_por_doc:,.0f}")
    print(f"Documentos no corpus:{args.docs_total:,}")
    print(f"Tokens totais:       {tokens_totais:,.0f}")
    print("-" * 60)
    print(f"Estimativa central:  {_formatar_usd(custo_central)}")
    print(f"Faixa (±{int(FAIXA_INCERTEZA*100)}%):        "
          f"{_formatar_usd(custo_baixo)} — {_formatar_usd(custo_alto)}")
    print("=" * 60)
    print("Premissas: custo só de embeddings (ingestão única). Reprocessamento por")
    print("troca de modelo, geração (chat) e re-ingestões não estão inclusos.")


if __name__ == "__main__":
    main()
