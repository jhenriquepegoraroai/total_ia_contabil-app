"""
CLI da API. Comandos administrativos rodáveis via:

    python -m api.cli <comando> [args]

Comandos:
    create-superadmin --email X --password Y [--name N]
    list-superadmins
"""

import argparse
import asyncio
import sys
from uuid import UUID

from loguru import logger
from sqlalchemy import text

from api import auth
from api.db import dispose_engine, superadmin_session


_SYSTEM_TENANT = "_system"


async def _create_superadmin(email: str, password: str, name: str) -> int:
    """Cria um superadmin no tenant _system. Retorna 0 em sucesso, 1 em conflito."""
    if len(password) < 8:
        print("Erro: senha precisa ter pelo menos 8 caracteres.", file=sys.stderr)
        return 2

    password_hash = auth.hash_password(password)

    async with superadmin_session() as session:
        # 1. Garantir tenant _system existe (migration 002 já cria, mas safe).
        await session.execute(
            text(
                "INSERT INTO tenants (id, nome_empresa, enabled) "
                "VALUES (:tid, 'System (reservado)', false) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"tid": _SYSTEM_TENANT},
        )

        # 2. Verificar se email já existe (em qualquer tenant).
        existing = (await session.execute(
            text("SELECT id, tenant_id, is_superadmin FROM users WHERE email = :em"),
            {"em": email},
        )).first()
        if existing:
            print(
                f"Erro: já existe usuário com email '{email}' "
                f"(tenant={existing.tenant_id}, superadmin={existing.is_superadmin}).",
                file=sys.stderr,
            )
            return 1

        # 3. Criar.
        row = (await session.execute(
            text(
                "INSERT INTO users (tenant_id, email, nome, role, password_hash, is_superadmin) "
                "VALUES (:tid, :em, :nm, 'admin', :ph, true) "
                "RETURNING id"
            ),
            {"tid": _SYSTEM_TENANT, "em": email, "nm": name, "ph": password_hash},
        )).first()

    assert row is not None
    print(f"✔ Superadmin criado. id={row.id} email={email}")
    return 0


async def _list_superadmins() -> int:
    async with superadmin_session() as session:
        rows = (await session.execute(
            text(
                "SELECT id, email, nome, enabled, created_at FROM users "
                "WHERE is_superadmin = true ORDER BY created_at"
            )
        )).all()

    if not rows:
        print("(nenhum superadmin cadastrado — use create-superadmin)")
        return 0

    print(f"{'id':<38}  {'email':<32}  {'nome':<24}  enabled  created_at")
    print("-" * 120)
    for r in rows:
        print(
            f"{str(r.id):<38}  {r.email:<32}  {(r.nome or ''):<24}  "
            f"{str(r.enabled):<7}  {r.created_at}"
        )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="api.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create-superadmin", help="Cria um superadmin global")
    p_create.add_argument("--email", required=True)
    p_create.add_argument("--password", required=True)
    p_create.add_argument("--name", default="Super Admin")

    sub.add_parser("list-superadmins", help="Lista os superadmins existentes")

    return parser.parse_args()


async def _amain() -> int:
    args = _parse_args()
    try:
        if args.cmd == "create-superadmin":
            return await _create_superadmin(args.email, args.password, args.name)
        if args.cmd == "list-superadmins":
            return await _list_superadmins()
        return 1
    finally:
        await dispose_engine()


def main() -> None:
    sys.exit(asyncio.run(_amain()))


if __name__ == "__main__":
    main()
