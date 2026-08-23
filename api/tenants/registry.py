"""
Registry — fonte de verdade dos tenant configs.

A partir da Fase 5, o DB é a source of truth: lê de `tenant_configs.config_json`.
Os JSONs em `tenants/configs/` continuam servindo como **seed inicial** —
quando o DB está vazio na primeira inicialização, o registry importa os JSONs
e insere no banco. Configs criadas via UI (`/admin/tenants`) entram direto no
DB e o registry é recarregado.

Estratégia de boot:
  1. SELECT FROM tenant_configs.
  2. Se vazio → import dos JSONs do diretório → INSERT no DB.
  3. Carrega cache em memória do que está no DB.
  4. Falha rápida (fail-fast) se algum config tem erro de validação.
"""

import json
import re
from pathlib import Path

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.tenants.models import TenantConfig

# Padrão para detectar placeholders não preenchidos em campos críticos.
_PLACEHOLDER_PATTERN = re.compile(
    r"\(XX\)|XXXX|55XXXXXXXXXX|placeholder|TODO|TBD",
    re.IGNORECASE,
)


class TenantRegistry:
    """Registry. Carrega tenants do DB (com seed via JSON files) e cacheia."""

    def __init__(self, configs_dir: Path):
        self._configs_dir = configs_dir
        self._cache: dict[str, TenantConfig] = {}

    # =========================================================================
    # Boot
    # =========================================================================
    async def carregar_todos(self, session: AsyncSession) -> dict[str, TenantConfig]:
        """
        Carrega todos os tenants (DB-first, com seed automático dos JSONs).

        Recebe uma `session` que DEVE ser uma `superadmin_session` ou conexão
        sem RLS — o registry precisa ler tenants de qualquer tenant_id.
        """
        self._cache.clear()

        # 1. Tentar ler do DB
        rows = (await session.execute(
            text("SELECT tenant_id, config_json FROM tenant_configs ORDER BY tenant_id")
        )).all()

        # 2. DB vazio → seed dos JSONs
        if not rows:
            logger.info("DB sem tenant_configs — fazendo seed dos JSON files.")
            await self._seed_from_json_files(session)
            rows = (await session.execute(
                text("SELECT tenant_id, config_json FROM tenant_configs ORDER BY tenant_id")
            )).all()

        # 3. Validar e popular cache
        erros: list[str] = []
        for tenant_id, config_json in rows:
            try:
                # config_json vem como dict (JSONB) com asyncpg.
                data = config_json if isinstance(config_json, dict) else json.loads(config_json)
                config = TenantConfig(**data)
            except Exception as exc:
                erros.append(f"{tenant_id}: {exc}")
                continue

            avisos = _validar_placeholders(config)
            for aviso in avisos:
                logger.warning(f"⚠ {aviso}")

            self._cache[config.tenant_id] = config
            status = "habilitado" if config.enabled else "desabilitado"
            logger.info(
                f"Tenant '{config.tenant_id}' ({config.nome_empresa}) "
                f"carregado [{status}, datasource={config.datasource.type}]"
            )

        if erros:
            msg = "Erros ao carregar tenants:\n" + "\n".join(f"  - {e}" for e in erros)
            raise RuntimeError(msg)

        if not self._cache:
            raise RuntimeError("Nenhum tenant válido carregado.")

        habilitados = [tid for tid, cfg in self._cache.items() if cfg.enabled]
        logger.info(
            f"Total de tenants: {len(self._cache)} ({len(habilitados)} habilitados: {habilitados})"
        )
        return dict(self._cache)

    async def _seed_from_json_files(self, session: AsyncSession) -> None:
        """Importa JSONs do diretório de configs e insere no DB. Idempotente."""
        if not self._configs_dir.exists():
            logger.warning(f"Diretório de configs não existe: {self._configs_dir}")
            return

        arquivos = [p for p in self._configs_dir.glob("*.json") if not p.name.startswith("_")]
        if not arquivos:
            logger.warning(f"Nenhum arquivo de tenant em {self._configs_dir}")
            return

        for filepath in sorted(arquivos):
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                # Valida antes de inserir.
                config = TenantConfig(**data)
            except Exception as exc:
                logger.error(f"Falha ao carregar seed {filepath.name}: {exc}")
                continue

            # Garantir que tenant existe na tabela tenants (FK).
            await session.execute(
                text(
                    "INSERT INTO tenants (id, nome_empresa, enabled) "
                    "VALUES (:tid, :nome, :en) ON CONFLICT (id) DO NOTHING"
                ),
                {"tid": config.tenant_id, "nome": config.nome_empresa, "en": config.enabled},
            )

            await session.execute(
                text(
                    "INSERT INTO tenant_configs (tenant_id, config_json, schema_version) "
                    "VALUES (:tid, CAST(:cj AS jsonb), :sv) "
                    "ON CONFLICT (tenant_id) DO NOTHING"
                ),
                {
                    "tid": config.tenant_id,
                    "cj": config.model_dump_json(),
                    "sv": config.schema_version,
                },
            )
            logger.info(f"[seed] Tenant '{config.tenant_id}' importado de {filepath.name}")

    # =========================================================================
    # Reload sob demanda (após admin criar/editar tenant)
    # =========================================================================
    async def recarregar(self, session: AsyncSession) -> None:
        """Re-lê tudo do DB. Chamar após mudança via /admin/tenants."""
        await self.carregar_todos(session)

    def upsert_em_memoria(self, config: TenantConfig) -> None:
        """Atualiza cache em memória sem hit no DB. Usado após persistência ok."""
        self._cache[config.tenant_id] = config

    def remover_em_memoria(self, tenant_id: str) -> None:
        self._cache.pop(tenant_id, None)

    # =========================================================================
    # Acesso
    # =========================================================================
    def get(self, tenant_id: str, *, only_enabled: bool = True) -> TenantConfig:
        """Retorna config de um tenant pelo ID."""
        config = self._cache.get(tenant_id)
        if config is None:
            disponiveis = [tid for tid in self._cache if tid != "_system"]
            raise ValueError(
                f"Tenant '{tenant_id}' não encontrado. Tenants disponíveis: {disponiveis}"
            )
        if only_enabled and not config.enabled:
            raise ValueError(f"Tenant '{tenant_id}' está desabilitado.")
        return config

    def get_por_nome(self, nome_empresa: str) -> TenantConfig | None:
        nome_lower = nome_empresa.strip().lower()
        for cfg in self._cache.values():
            if cfg.nome_empresa.strip().lower() == nome_lower:
                return cfg
        return None

    def listar(self, *, only_enabled: bool = True, include_system: bool = False) -> list[str]:
        """Lista tenant_ids. Por default exclui o tenant `_system` reservado."""
        return [
            tid for tid, cfg in self._cache.items()
            if (include_system or tid != "_system")
            and (not only_enabled or cfg.enabled)
        ]

    def __contains__(self, tenant_id: str) -> bool:
        return tenant_id in self._cache


def _validar_placeholders(config: TenantConfig) -> list[str]:
    """Detecta placeholders não preenchidos em campos de contato/URL críticos."""
    # Tenant `_system` é reservado e não tem dados de contato reais.
    if config.tenant_id == "_system":
        return []
    avisos = []
    campos = {
        "contatos.telefone": config.contatos.telefone,
        "contatos.whatsapp": config.contatos.whatsapp,
        "contatos.whatsapp_link": config.contatos.whatsapp_link,
        "contatos.email": config.contatos.email,
        "urls.app_moradores": config.urls.app_moradores,
        "urls.portal_resolva_facil": config.urls.portal_resolva_facil,
    }
    for campo, valor in campos.items():
        if _PLACEHOLDER_PATTERN.search(valor):
            avisos.append(
                f"Tenant '{config.tenant_id}': '{campo}' contém placeholder: {valor!r}"
            )
    return avisos
