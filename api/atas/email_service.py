"""
Serviço de e-mail (SMTP async) usado pelo workflow do Bella Atas.

Provider neutro: lê SMTP_HOST/PORT/USER/PASS/USE_TLS do env. Funciona
com Gmail (app password), AWS SES, SendGrid, Mailgun, Outlook, etc.

Política de erro: o envio é **best-effort** — falhas SMTP são logadas
mas NÃO derrubam o workflow. A ata muda de estado mesmo se o e-mail
falhar; o consultor pode reenviar manualmente. Isso evita que outage
do provider de e-mail trave a operação.

Quando o tenant não tem `email_admin` configurado ou SMTP não está
montado, o serviço apenas loga e retorna sem enviar — desenvolvimento
local fica funcional sem precisar montar SMTP.
"""

from __future__ import annotations

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from uuid import UUID

import aiosmtplib
from loguru import logger

from api import config
from api.atas import email_templates
from api.tenants.models import TenantConfig


# =============================================================================
# Helpers — montagem de MIME e envio
# =============================================================================
def _smtp_disponivel() -> bool:
    return bool(config.SMTP_HOST)


def _from_address(tenant_config: TenantConfig) -> str:
    """
    Resolve o endereço FROM:
      1. tenant_config.email_admin (preferido — representa a administradora)
      2. SMTP_FROM_DEFAULT do env (fallback global)
      3. None — caller deve abortar com log
    """
    if tenant_config.email_admin:
        nome = tenant_config.nome_empresa or "Bella SaaS"
        return f"{nome} <{tenant_config.email_admin}>"
    if config.SMTP_FROM_DEFAULT:
        return config.SMTP_FROM_DEFAULT
    return ""


async def _enviar_smtp(
    *,
    from_addr: str,
    to_addr: str,
    subject: str,
    html_body: str,
    reply_to: str | None = None,
) -> bool:
    """
    Envia um e-mail via SMTP. Retorna True se enviou, False em qualquer falha.
    Não levanta exceção pra fora — caller decide se loga só ou re-tenta.
    """
    if not _smtp_disponivel():
        logger.info(
            f"[email] SMTP não configurado (SMTP_HOST vazio) — "
            f"e-mail descartado: to={to_addr} subject={subject[:40]}"
        )
        return False

    if not from_addr:
        logger.warning(
            f"[email] FROM vazio (tenant sem email_admin e sem SMTP_FROM_DEFAULT) — "
            f"e-mail descartado: to={to_addr} subject={subject[:40]}"
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(html_body, "html", _charset="utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=config.SMTP_HOST,
            port=config.SMTP_PORT,
            username=config.SMTP_USERNAME or None,
            password=config.SMTP_PASSWORD or None,
            start_tls=config.SMTP_USE_TLS,
            timeout=30,
        )
        logger.info(f"[email] enviado to={to_addr} subject={subject[:40]}")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[email] falha enviando to={to_addr} subject={subject[:40]}: {exc}")
        return False


def _ano_atual() -> str:
    return str(datetime.now().year)


def _link_ata(tenant_id: str, ata_id: UUID) -> str:
    """URL completa da página da ata no front (tenant_id implícito via JWT)."""
    base = config.WEB_URL_BASE.rstrip("/")
    return f"{base}/atas/{ata_id}"


# =============================================================================
# Notificações de workflow — uma por transição importante
# =============================================================================
async def notificar_sindico(
    *,
    tenant_config: TenantConfig,
    ata_id: UUID,
    sindico_email: str,
    sindico_nome: str,
    consultor_nome: str,
    ata_titulo: str,
    ata_referencia: str | None,
) -> bool:
    """Síndico recebeu uma ata pra revisar."""
    from_addr = _from_address(tenant_config)
    html = email_templates.html_convite_sindico(
        nome_empresa=tenant_config.nome_empresa,
        nome_destinatario=sindico_nome,
        nome_remetente=consultor_nome,
        ata_titulo=ata_titulo,
        ata_referencia=ata_referencia,
        link_ata=_link_ata(tenant_config.tenant_id, ata_id),
        ano=_ano_atual(),
    )
    return await _enviar_smtp(
        from_addr=from_addr,
        to_addr=sindico_email,
        subject=f"[{tenant_config.nome_empresa}] Ata para revisão: {ata_titulo}",
        html_body=html,
        reply_to=tenant_config.email_admin,
    )


async def notificar_presidente(
    *,
    tenant_config: TenantConfig,
    ata_id: UUID,
    presidente_email: str,
    presidente_nome: str,
    consultor_nome: str,
    ata_titulo: str,
    ata_referencia: str | None,
) -> bool:
    """Presidente da assembleia recebeu uma ata pra revisar."""
    from_addr = _from_address(tenant_config)
    html = email_templates.html_convite_presidente(
        nome_empresa=tenant_config.nome_empresa,
        nome_destinatario=presidente_nome,
        nome_remetente=consultor_nome,
        ata_titulo=ata_titulo,
        ata_referencia=ata_referencia,
        link_ata=_link_ata(tenant_config.tenant_id, ata_id),
        ano=_ano_atual(),
    )
    return await _enviar_smtp(
        from_addr=from_addr,
        to_addr=presidente_email,
        subject=f"[{tenant_config.nome_empresa}] Ata para revisão (presidente): {ata_titulo}",
        html_body=html,
        reply_to=tenant_config.email_admin,
    )


async def notificar_devolucao_consultor(
    *,
    tenant_config: TenantConfig,
    ata_id: UUID,
    consultor_email: str,
    consultor_nome: str,
    ator_externo_nome: str,
    papel_ator: str,                  # "síndico" ou "presidente"
    ata_titulo: str,
    ata_referencia: str | None,
) -> bool:
    """Consultor recebe aviso quando síndico/presidente devolve a ata editada."""
    from_addr = _from_address(tenant_config)
    html = email_templates.html_devolucao_para_consultor(
        nome_empresa=tenant_config.nome_empresa,
        nome_destinatario=consultor_nome,
        nome_ator_externo=ator_externo_nome,
        papel_ator=papel_ator,
        ata_titulo=ata_titulo,
        ata_referencia=ata_referencia,
        link_ata=_link_ata(tenant_config.tenant_id, ata_id),
        ano=_ano_atual(),
    )
    return await _enviar_smtp(
        from_addr=from_addr,
        to_addr=consultor_email,
        subject=f"[{tenant_config.nome_empresa}] {papel_ator.capitalize()} devolveu: {ata_titulo}",
        html_body=html,
        reply_to=tenant_config.email_admin,
    )


async def notificar_ata_registrada(
    *,
    tenant_config: TenantConfig,
    ata_id: UUID,
    destinatario_email: str,
    destinatario_nome: str,
    ata_titulo: str,
    ata_referencia: str | None,
) -> bool:
    """Notifica destinatário (síndico, presidente, consultor) que a ata foi finalizada."""
    from_addr = _from_address(tenant_config)
    html = email_templates.html_ata_registrada(
        nome_empresa=tenant_config.nome_empresa,
        nome_destinatario=destinatario_nome,
        ata_titulo=ata_titulo,
        ata_referencia=ata_referencia,
        link_ata=_link_ata(tenant_config.tenant_id, ata_id),
        ano=_ano_atual(),
    )
    return await _enviar_smtp(
        from_addr=from_addr,
        to_addr=destinatario_email,
        subject=f"[{tenant_config.nome_empresa}] Ata finalizada: {ata_titulo}",
        html_body=html,
        reply_to=tenant_config.email_admin,
    )
