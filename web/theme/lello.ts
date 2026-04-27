/**
 * Tema Lello — paleta padrão do Assistente Virtual de Condomínios.
 *
 * IMPORTANTE: hex codes abaixo são ESTIMATIVAS VISUAIS feitas a partir de
 * screenshots de site-da-administradora.exemplo (capturados em 2026-04-27).
 * Substituir por valores oficiais quando o brandbook for fornecido.
 *
 * Outros tenants podem sobrescrever via tenant_config.theme — os tokens
 * abaixo são consumidos pelo shadcn/ui através de CSS custom properties
 * declaradas em web/app/globals.css.
 */

export const lelloTheme = {
  name: "lello",
  displayName: "Administradora Exemplo",

  colors: {
    // Cor primária — vermelho cereja do logo, eyebrows e CTAs principais.
    // Observada em "PRAZER, LELLO!", botão "2ª via do boleto", logo.
    primary: "#CB1D40",
    primaryForeground: "#FFFFFF",

    // Cor secundária — vinho/bordô profundo dos CTAs secundários.
    // Observada em "Fale com o time comercial".
    secondary: "#5D0E1F",
    secondaryForeground: "#FFFFFF",

    // Accent — pêssego acolhedor de cards complementares.
    // Observado em card lateral do hero.
    accent: "#F5B79E",
    accentForeground: "#0E0E0E",

    // Tinta principal das headlines pretas.
    ink: "#0E0E0E",

    // Cinzas neutros.
    muted: "#EDEDED",
    mutedForeground: "#6B6B6B",
    border: "#E5E5E5",

    // Backgrounds.
    background: "#FFFFFF",
    foreground: "#0E0E0E",

    // Estados.
    destructive: "#CB1D40", // mesmo tom do primário (Lello é vermelha mesmo)
    destructiveForeground: "#FFFFFF",
    success: "#1F8A4D",
    warning: "#E0A21A",
  },

  typography: {
    // Fonte oficial Lello pendente de confirmação.
    // Inter como fallback — sans-serif moderna próxima do que aparece no site.
    fontFamily: {
      sans: '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
      heading: '"Inter", system-ui, -apple-system, sans-serif',
    },
    // Headlines da Lello têm peso forte (extrabold/black).
    fontWeight: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
      extrabold: 800,
    },
  },

  radius: {
    // Botões e cards do site têm cantos suavemente arredondados.
    sm: "0.375rem",   // 6px
    md: "0.5rem",     // 8px
    lg: "0.75rem",    // 12px
    xl: "1rem",       // 16px
    full: "9999px",
  },

  shadows: {
    sm: "0 1px 2px rgba(14, 14, 14, 0.04)",
    md: "0 4px 12px rgba(14, 14, 14, 0.08)",
    lg: "0 10px 30px rgba(14, 14, 14, 0.12)",
  },

  brand: {
    logoUrl: "/themes/lello/logo.svg",
    logoMonochromeUrl: "/themes/lello/logo-mono.svg",
    faviconUrl: "/themes/lello/favicon.ico",
    tagline: "Viver o Condomínio Une!",
  },
} as const;

export type Theme = typeof lelloTheme;
