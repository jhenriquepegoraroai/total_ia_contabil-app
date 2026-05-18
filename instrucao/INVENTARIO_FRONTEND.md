# Inventário Frontend — Lello AI Platform

Gerado em 2026-05-18. Branch: `main`. Stack: Next.js 15.1 + React 19 + Tailwind 3.4 + shadcn/ui.

---

## Rotas (App Router — `web/app/`)

| Rota | Arquivo | Acesso | Descrição |
|------|---------|--------|-----------|
| `/` | `app/page.tsx` | Autenticado | Redirect para `/chat` ou `/admin` conforme role |
| `/login` | `app/login/page.tsx` | Público | Formulário email + senha |
| `/admin` | `app/admin/page.tsx` | Superadmin | Dashboard — lista tenants com métricas |
| `/admin/audit` | `app/admin/audit/page.tsx` | Superadmin | Log de ações do superadmin |
| `/admin/tenants/new` | `app/admin/tenants/new/page.tsx` | Superadmin | Criar novo tenant |
| `/admin/tenants/[id]` | `app/admin/tenants/[id]/page.tsx` | Superadmin | Detalhe do tenant (tabs) |
| `/admin/tenants/[id]/edit` | `app/admin/tenants/[id]/edit/page.tsx` | Superadmin | Editar config do tenant |
| `/admin/tenants/[id]/chats` | `app/admin/tenants/[id]/chats/page.tsx` | Superadmin | Histórico de conversas do tenant |
| `/admin/tenants/[id]/chats/[sessionId]` | `...chats/[sessionId]/page.tsx` | Superadmin | Mensagens de uma sessão |
| `/admin/tenants/[id]/jobs` | `app/admin/tenants/[id]/jobs/page.tsx` | Superadmin | Jobs de ingestão do tenant |
| `/admin/tenants/[id]/sources` | `app/admin/tenants/[id]/sources/page.tsx` | Superadmin | Fontes de dados do tenant |
| `/admin/tenants/[id]/sources/new` | `.../sources/new/page.tsx` | Superadmin | Nova fonte de dados |
| `/admin/tenants/[id]/sources/[sid]/edit` | `.../sources/[sid]/edit/page.tsx` | Superadmin | Editar fonte |
| `/admin/tenants/[id]/tables` | `app/admin/tenants/[id]/tables/page.tsx` | Superadmin | Browser read-only de dados estruturados |
| `/admin/tenants/[id]/users` | `app/admin/tenants/[id]/users/page.tsx` | Superadmin | Gerenciar usuários do tenant |
| `/atas` | `app/atas/page.tsx` | Tenant (módulo atas) | Lista de atas |
| `/atas/nova` | `app/atas/nova/page.tsx` | Tenant (módulo atas) | Criar nova ata |
| `/atas/[id]` | `app/atas/[id]/page.tsx` | Tenant (módulo atas) | Detalhe: editor, diff, status, exportar |
| `/cobrancas` | `app/cobrancas/page.tsx` | Tenant (módulo cobrancas) | Upload PDF, status de jobs, resultados |
| `/usuarios` | `app/usuarios/page.tsx` | Admin do tenant | Gerenciar usuários do próprio tenant |

**Total: 20 páginas.** Layouts: `app/layout.tsx` (root), `app/admin/layout.tsx` (admin shell).

---

## Componentes (`web/components/`)

### Layout

| Componente | Descrição |
|-----------|-----------|
| `layout/app-shell.tsx` | Shell principal — hamburger nav multi-módulo, header com tema do tenant |
| `lello-logo.tsx` | Logo SVG da Lello (componente isolado para fácil troca por tenant) |

### Chat

| Componente | Descrição |
|-----------|-----------|
| `chat/chat-input.tsx` | Caixa de input da pergunta com submit |
| `chat/message-bubble.tsx` | Bolha de mensagem (user / assistant) |
| `chat/message-list.tsx` | Lista de mensagens da sessão |
| `chat/citation-list.tsx` | Lista de citações de documentos em cada resposta |

### Atas

| Componente | Descrição |
|-----------|-----------|
| `atas/editor.tsx` | Editor de texto HTML da ata (WYSIWYG simplificado) |
| `atas/status-badge.tsx` | Badge de status do workflow (15 estados, cores distintas) |

### Admin

| Componente | Descrição |
|-----------|-----------|
| `admin/cobrancas-card.tsx` | Card de configuração de credenciais GCP por tenant |
| `admin/modulos-checkboxes-card.tsx` | Checkboxes de módulos contratados por tenant |
| `admin/openai-key-card.tsx` | Card de chave OpenAI por tenant (mode: lello / custom) |
| `admin/source-config-fields.tsx` | Campos de configuração por tipo de fonte (postgres, s3, etc.) |

### UI (shadcn/ui wrappados)

| Componente | Descrição |
|-----------|-----------|
| `ui/badge.tsx` | Badge genérico |
| `ui/button.tsx` | Botão com variantes (primary, outline, ghost, destructive) |
| `ui/card.tsx` | Card container |
| `ui/confirm-dialog.tsx` | Dialog de confirmação de ação destrutiva |
| `ui/input.tsx` | Input de texto |
| `ui/password-input.tsx` | Input de senha com toggle de visibilidade |
| `ui/skeleton.tsx` | Skeleton loader |
| `ui/textarea.tsx` | Textarea |
| `ui/toast.tsx` | Notificações toast |

---

## Themes (`web/public/themes/` e `web/theme/`)

| Recurso | Descrição |
|---------|-----------|
| `web/public/themes/lello/` | Assets estáticos do tema Lello: logo.svg, favicon.ico |
| `web/theme/lello.ts` | Paleta de cores do tema Lello em CSS custom properties |
| `web/theme/index.ts` | Exports do sistema de theming |

**Theming por tenant:** CSS custom properties (`--primary`, `--secondary`, etc.) sobrescritas via `TenantTheme` do `TenantConfig`. Modo dark/light via `next-themes`.

**Cores Lello (estimativa visual — pendente confirmação oficial):**
- Primary: `#CB1D40` (vermelho Lello)
- Secondary: `#5D0E1F`
- Accent: `#F5B79E`

---

## Dados técnicos

- **9.568 linhas** TypeScript/TSX em ~40 arquivos
- **Next.js 15.1** App Router, React 19, TypeScript strict
- **Tailwind 3.4** + shadcn/ui (Radix UI primitives)
- **lucide-react** para ícones
- Cookie HttpOnly para JWT (não localStorage)
- `NEXT_PUBLIC_API_URL` aponta para o backend FastAPI
