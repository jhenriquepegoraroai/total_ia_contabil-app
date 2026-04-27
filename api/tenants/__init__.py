"""Pacote de tenants — configs, registry e datasources adapters."""

from api.tenants.models import TenantConfig
from api.tenants.registry import TenantRegistry

__all__ = ["TenantConfig", "TenantRegistry"]
