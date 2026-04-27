# Web — Assistente Virtual de Condomínios

Frontend Next.js 15 + React 19 + Tailwind + shadcn/ui. Tema Lello como padrão;
outros tenants sobrescrevem via CSS variables (paleta em `app/globals.css`,
tokens em `theme/lello.ts`).

## Stack
- Next.js 15 (App Router)
- React 19
- Tailwind 3.4
- shadcn/ui (`cva` + `clsx` + `tailwind-merge`)
- lucide-react
- next-themes

## Dev

```bash
cd web
npm install
npm run dev    # http://localhost:3000
```

A API FastAPI deve estar rodando em `http://localhost:8000` (ou `NEXT_PUBLIC_API_URL`).
As chamadas `/api/*` do frontend são proxy para a API via `next.config.ts`.

## Estrutura

```
web/
├── app/
│   ├── layout.tsx          # root + providers + Inter
│   ├── page.tsx            # tela de chat
│   ├── login/page.tsx      # /auth/dev-token
│   ├── providers.tsx       # next-themes
│   └── globals.css         # CSS variables Lello (HSL)
├── components/
│   ├── ui/                 # shadcn primitives (Button, Card, Input, ...)
│   ├── chat/               # ChatInput, MessageList, MessageBubble, CitationList
│   └── lello-logo.tsx      # placeholder do logo
├── lib/
│   ├── api.ts              # client da API
│   ├── auth.ts             # localStorage do token
│   ├── types.ts            # espelhos dos schemas Pydantic
│   └── utils.ts            # cn()
├── theme/
│   ├── lello.ts            # tokens da marca
│   └── index.ts
└── public/themes/lello/
    ├── logo.svg            # placeholder — substituir pelo oficial
    └── favicon.svg
```

## Theming por tenant (futuro)

Hoje o tema Lello é hardcoded em `globals.css`. Quando outros tenants entrarem,
a página vai receber `theme` no payload do tenant atual e setar as CSS variables
no `<html>` server-side. shadcn/ui já consome as variables, então basta trocar
os valores de `--primary`, `--secondary`, etc.
