"""
CLI do pipeline de ingestão.

Uso:
    python -m ingestion.run --tenant lello --connector pdf_folder \\
                            --path ./data/lello/12345 --referencia 12345

A pasta de configs dos tenants é lida via env (TENANTS_CONFIG_DIR).
DATABASE_URL e OPEN_AI_KEY também via env (ver .env.example).
"""

import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger

from api import config
from api.db import dispose_engine, tenant_session
from api.tenants.registry import TenantRegistry

from .connectors import criar_connector
from .embeddings import cliente_padrao
from .pipeline import executar


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline de ingestão de embeddings — Assistente Virtual de Condomínios.",
    )
    parser.add_argument("--tenant", required=True, help="ID do tenant (ex: lello)")
    parser.add_argument("--referencia", required=True, help="Referência do condomínio")
    parser.add_argument(
        "--connector",
        required=True,
        choices=["pdf_folder", "postgres"],
        help="Tipo de conector",
    )
    parser.add_argument(
        "--path",
        required=False,
        help="Path/URI específico do conector (ex: pasta de PDFs ou conn string)",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="(pdf_folder) busca recursiva em subpastas",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=config.INGESTION_BATCH_SIZE,
        help=f"Chunks por batch (default {config.INGESTION_BATCH_SIZE})",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=config.INGESTION_MAX_WORKERS,
        help=f"Batches em paralelo (default {config.INGESTION_MAX_WORKERS})",
    )
    return parser.parse_args()


async def _amain() -> int:
    args = _parse_args()

    # 1. Carrega registry de tenants
    configs_dir = Path(config.TENANTS_CONFIG_DIR)
    if not configs_dir.is_absolute():
        # Resolve relativo ao diretório onde está rodando (ex: ./api/tenants/configs)
        # Convenção: rodar do root do projeto.
        configs_dir = Path("api") / config.TENANTS_CONFIG_DIR if not configs_dir.exists() else configs_dir

    registry = TenantRegistry(configs_dir)
    registry.carregar_todos()
    tenant_config = registry.get(args.tenant, only_enabled=False)
    # only_enabled=False — pipeline de ingestão pode rodar para tenant ainda
    # não habilitado (etapa do onboarding antes de ligar).

    # 2. Conector
    conn_kwargs: dict = {}
    if args.connector == "pdf_folder":
        if not args.path:
            print("--path obrigatório para pdf_folder", file=sys.stderr)
            return 2
        conn_kwargs["path"] = args.path
        conn_kwargs["recursive"] = args.recursive
    elif args.connector == "postgres":
        conn_kwargs["connection_string"] = args.path

    connector = criar_connector(args.connector, **conn_kwargs)

    # 3. Cliente OpenAI
    embedding_client = cliente_padrao()

    # 4. Executar pipeline em sessão do tenant (RLS aplicado)
    try:
        async with tenant_session(args.tenant) as session:
            audit = await executar(
                tenant_config=tenant_config,
                referencia=args.referencia,
                connector=connector,
                session=session,
                embedding_client=embedding_client,
                batch_size=args.batch_size,
                max_concurrent_batches=args.max_workers,
            )

        if audit.qtde_erros > 0:
            logger.warning(f"Concluído com {audit.qtde_erros} erros.")
            return 1
        return 0

    finally:
        await embedding_client.aclose()
        await dispose_engine()


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
