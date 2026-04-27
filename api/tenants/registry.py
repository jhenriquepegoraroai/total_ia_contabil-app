"""
Registry — carrega todos os JSONs de tenant do diretório de configs e mantém
um cache em memória.

Estratégia de boot:
  - `carregar_todos_os_tenants()` é chamado uma vez no startup do FastAPI.
  - Falha rápida (fail-fast): se qualquer JSON for inválido, ID duplicado, ou
    placeholder não preenchido em campo crítico, derruba o boot.
  - Tenants com `enabled=false` são carregados (presentes no cache) mas
    ignorados no health/listagem pública.
"""

import json
import re
from pathlib import Path
from typing import Optional

from loguru import logger

from api.tenants.models import TenantConfig


# Padrão para detectar placeholders não preenchidos em campos de contato/URL.
_PLACEHOLDER_PATTERN = re.compile(
    r"\(XX\)|XXXX|55XXXXXXXXXX|placeholder|TODO|TBD",
    re.IGNORECASE,
)


class TenantRegistry:
    """Registry singleton-style. Mantém o cache global de tenants carregados."""

    def __init__(self, configs_dir: Path):
        self._configs_dir = configs_dir
        self._cache: dict[str, TenantConfig] = {}

    def carregar_todos(self) -> dict[str, TenantConfig]:
        """
        Lê todos os arquivos `*.json` do diretório (excluindo `_template.json`),
        valida cada um e popula o cache.

        Raises:
            RuntimeError: se diretório não existe, está vazio, ou alguma config
                tem erro de validação ou ID duplicado.
        """
        self._cache.clear()

        if not self._configs_dir.exists():
            raise RuntimeError(
                f"Diretório de configs de tenants não encontrado: {self._configs_dir}"
            )

        arquivos = [
            p for p in self._configs_dir.glob("*.json")
            if not p.name.startswith("_")
        ]
        if not arquivos:
            raise RuntimeError(
                f"Nenhum arquivo de tenant encontrado em {self._configs_dir}. "
                f"Adicione ao menos um <tenant_id>.json."
            )

        erros: list[str] = []
        for filepath in sorted(arquivos):
            try:
                config = self._carregar_arquivo(filepath)
            except Exception as exc:
                erros.append(f"{filepath.name}: {exc}")
                continue

            if config.tenant_id in self._cache:
                erros.append(
                    f"Tenant ID duplicado '{config.tenant_id}' em {filepath.name}"
                )
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

    def _carregar_arquivo(self, filepath: Path) -> TenantConfig:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return TenantConfig(**data)

    def get(self, tenant_id: str, *, only_enabled: bool = True) -> TenantConfig:
        """
        Retorna config de um tenant pelo ID.

        Args:
            only_enabled: se True (default), tenants desabilitados levantam erro.

        Raises:
            ValueError: tenant não encontrado, ou desabilitado quando `only_enabled=True`.
        """
        config = self._cache.get(tenant_id)
        if config is None:
            disponiveis = list(self._cache.keys())
            raise ValueError(
                f"Tenant '{tenant_id}' não encontrado. Tenants disponíveis: {disponiveis}"
            )
        if only_enabled and not config.enabled:
            raise ValueError(f"Tenant '{tenant_id}' está desabilitado.")
        return config

    def get_por_nome(self, nome_empresa: str) -> Optional[TenantConfig]:
        """Busca tenant pelo nome da empresa (case-insensitive). None se não acha."""
        nome_lower = nome_empresa.strip().lower()
        for cfg in self._cache.values():
            if cfg.nome_empresa.strip().lower() == nome_lower:
                return cfg
        return None

    def listar(self, *, only_enabled: bool = True) -> list[str]:
        """Retorna lista de tenant_ids."""
        return [
            tid for tid, cfg in self._cache.items()
            if not only_enabled or cfg.enabled
        ]

    def __contains__(self, tenant_id: str) -> bool:
        return tenant_id in self._cache


def _validar_placeholders(config: TenantConfig) -> list[str]:
    """Detecta placeholders não preenchidos em campos de contato/URL críticos."""
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
