"use client";

import { useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEFAULT_TENANT = process.env.NEXT_PUBLIC_DEFAULT_TENANT ?? "lello";

interface TemaPublico {
  primary: string;
  secondary: string;
  accent: string;
  ink: string;
  muted: string;
  background: string;
  logo_url: string;
  favicon_url: string;
  font_family: string;
}

function hexToHsl(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }

  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

function aplicarTema(tema: TemaPublico) {
  const root = document.documentElement;

  root.style.setProperty("--primary", hexToHsl(tema.primary));
  root.style.setProperty("--secondary", hexToHsl(tema.secondary));
  root.style.setProperty("--accent", hexToHsl(tema.accent));
  root.style.setProperty("--background", hexToHsl(tema.background));
  root.style.setProperty("--foreground", hexToHsl(tema.ink));
  root.style.setProperty("--muted", hexToHsl(tema.muted));
  root.style.setProperty("--muted-foreground", hexToHsl(tema.ink));
  root.style.setProperty("--font-tenant", tema.font_family);

  // Favicon dinâmico
  const favicon = document.querySelector<HTMLLinkElement>("link[rel~='icon']");
  if (favicon) favicon.href = tema.favicon_url;
}

function obterTenantId(): string {
  try {
    const raw = window.localStorage.getItem("avc_session");
    if (raw) {
      const parsed = JSON.parse(raw) as { tenant_id?: string };
      if (parsed.tenant_id) return parsed.tenant_id;
    }
  } catch {
    // ignorar erro de parse
  }
  return DEFAULT_TENANT;
}

export function TenantThemeProvider() {
  useEffect(() => {
    const tenantId = obterTenantId();

    fetch(`${API_URL}/tenants/${tenantId}/tema`)
      .then((r) => (r.ok ? r.json() : null))
      .then((tema: TemaPublico | null) => {
        if (tema) aplicarTema(tema);
      })
      .catch(() => {
        // Sem backend: mantém tema padrão do globals.css
      });
  }, []);

  return null;
}
