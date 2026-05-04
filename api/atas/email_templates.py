"""
Templates HTML dos e-mails de workflow do Bella Atas.

Mantemos como constantes Python (sem Jinja) pra não introduzir dependência
extra. Substituições são `.format(...)` simples — placeholders entre
chaves duplas pra escapar de HTML/CSS.

Variáveis comuns:
  - {nome_empresa}         nome da administradora (TenantConfig.nome_empresa)
  - {ata_titulo}           título da ata
  - {ata_referencia}       condomínio/referência (opcional)
  - {nome_destinatario}    nome do user que vai receber (síndico/presidente/consultor)
  - {nome_remetente}       nome do consultor que enviou (ou "Sistema")
  - {link_ata}             URL completa pra abrir a ata no front
  - {ano}                  ano corrente (footer)
"""

# CSS inline simples, mantém HTML compatível com a maioria dos clientes
# (Gmail, Outlook). Sem media queries, sem JS, sem imagens externas.
_BASE_HTML = """<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="utf-8">
  <title>{titulo_pagina}</title>
</head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,Helvetica,sans-serif;color:#222;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f5f5f5;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
        <tr><td style="padding:24px 32px;background:#0E0E0E;color:#ffffff;">
          <h1 style="margin:0;font-size:18px;font-weight:600;">Bella Atas — {nome_empresa}</h1>
        </td></tr>
        <tr><td style="padding:32px;">
          {corpo}
        </td></tr>
        <tr><td style="padding:16px 32px;background:#fafafa;color:#888;font-size:11px;">
          E-mail automático enviado por {nome_empresa} via Bella SaaS · {ano}.<br>
          Se você não esperava este e-mail, ignore esta mensagem.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _envelope(*, titulo_pagina: str, corpo: str, nome_empresa: str, ano: str) -> str:
    return _BASE_HTML.format(
        titulo_pagina=titulo_pagina,
        corpo=corpo,
        nome_empresa=nome_empresa,
        ano=ano,
    )


def _botao_link(url: str, label: str) -> str:
    return (
        f'<p style="margin:24px 0;text-align:center;">'
        f'<a href="{url}" style="display:inline-block;padding:12px 24px;'
        f'background:#CB1D40;color:#ffffff;text-decoration:none;'
        f'border-radius:6px;font-weight:600;">{label}</a></p>'
        f'<p style="font-size:12px;color:#666;text-align:center;">'
        f'Se o botão não funcionar, copie e cole no navegador:<br>'
        f'<span style="word-break:break-all;color:#0066cc;">{url}</span></p>'
    )


# =============================================================================
# Templates — um por tipo de notificação do workflow
# =============================================================================
def html_convite_sindico(
    *,
    nome_empresa: str,
    nome_destinatario: str,
    nome_remetente: str,
    ata_titulo: str,
    ata_referencia: str | None,
    link_ata: str,
    ano: str,
) -> str:
    """Síndico recebe ata pra revisar (status='aguardando_sindico')."""
    contexto_ref = f" do condomínio <strong>{ata_referencia}</strong>" if ata_referencia else ""
    corpo = (
        f'<h2 style="margin:0 0 16px;font-size:20px;">Olá, {nome_destinatario}.</h2>'
        f'<p>{nome_remetente}, da {nome_empresa}, enviou para você a ata da '
        f'assembleia <strong>{ata_titulo}</strong>{contexto_ref} para revisão.</p>'
        f'<p>No link abaixo você pode <strong>ler</strong> a ata e <strong>fazer '
        f'alterações</strong>. Quando terminar, basta clicar em "Devolver" — '
        f'o consultor recebe sua versão e revisa as mudanças.</p>'
        + _botao_link(link_ata, "Abrir a ata")
    )
    return _envelope(
        titulo_pagina="Ata para revisão",
        corpo=corpo,
        nome_empresa=nome_empresa,
        ano=ano,
    )


def html_convite_presidente(
    *,
    nome_empresa: str,
    nome_destinatario: str,
    nome_remetente: str,
    ata_titulo: str,
    ata_referencia: str | None,
    link_ata: str,
    ano: str,
) -> str:
    """Presidente recebe ata pra revisar (status='aguardando_presidente')."""
    contexto_ref = f" do condomínio <strong>{ata_referencia}</strong>" if ata_referencia else ""
    corpo = (
        f'<h2 style="margin:0 0 16px;font-size:20px;">Olá, {nome_destinatario}.</h2>'
        f'<p>{nome_remetente}, da {nome_empresa}, enviou para você a ata da '
        f'assembleia <strong>{ata_titulo}</strong>{contexto_ref} para revisão como '
        f'presidente da mesa.</p>'
        f'<p>Você pode <strong>ler</strong> e <strong>fazer alterações</strong> '
        f'na ata pelo link abaixo. Quando terminar, clique em "Devolver" para '
        f'que o consultor finalize.</p>'
        + _botao_link(link_ata, "Abrir a ata")
    )
    return _envelope(
        titulo_pagina="Ata para revisão (presidente)",
        corpo=corpo,
        nome_empresa=nome_empresa,
        ano=ano,
    )


def html_devolucao_para_consultor(
    *,
    nome_empresa: str,
    nome_destinatario: str,
    nome_ator_externo: str,
    papel_ator: str,                 # "síndico" ou "presidente"
    ata_titulo: str,
    ata_referencia: str | None,
    link_ata: str,
    ano: str,
) -> str:
    """Consultor recebe aviso de que síndico/presidente devolveu a ata."""
    contexto_ref = f" ({ata_referencia})" if ata_referencia else ""
    corpo = (
        f'<h2 style="margin:0 0 16px;font-size:20px;">Olá, {nome_destinatario}.</h2>'
        f'<p><strong>{nome_ator_externo}</strong> ({papel_ator}) editou e devolveu '
        f'a ata <strong>{ata_titulo}</strong>{contexto_ref}.</p>'
        f'<p>Já geramos a comparação entre a versão enviada e a devolvida. '
        f'Acesse o link abaixo para revisar as alterações e aprovar ou rejeitar.</p>'
        + _botao_link(link_ata, "Ver alterações")
    )
    return _envelope(
        titulo_pagina="Ata devolvida",
        corpo=corpo,
        nome_empresa=nome_empresa,
        ano=ano,
    )


def html_ata_registrada(
    *,
    nome_empresa: str,
    nome_destinatario: str,
    ata_titulo: str,
    ata_referencia: str | None,
    link_ata: str,
    ano: str,
) -> str:
    """Aviso de que a ata foi finalizada (status='registrada')."""
    contexto_ref = f" do condomínio <strong>{ata_referencia}</strong>" if ata_referencia else ""
    corpo = (
        f'<h2 style="margin:0 0 16px;font-size:20px;">Olá, {nome_destinatario}.</h2>'
        f'<p>A ata da assembleia <strong>{ata_titulo}</strong>{contexto_ref} '
        f'foi finalizada e está disponível para registro em cartório.</p>'
        + _botao_link(link_ata, "Abrir a ata final")
    )
    return _envelope(
        titulo_pagina="Ata finalizada",
        corpo=corpo,
        nome_empresa=nome_empresa,
        ano=ano,
    )
