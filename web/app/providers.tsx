"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import * as React from "react";

import { TenantThemeProvider } from "@/components/tenant-theme-provider";
import { ToastProvider } from "@/components/ui/toast";

/**
 * Providers globais — tema (next-themes) + theming per-tenant + toasts.
 *
 * TenantThemeProvider lê o tenant_id do localStorage (salvo no login),
 * busca o tema no backend e injeta CSS variables em :root. next-themes
 * controla apenas light/dark sobre as cores do tenant.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="light"
      enableSystem
      disableTransitionOnChange
    >
      <TenantThemeProvider />
      <ToastProvider>{children}</ToastProvider>
    </NextThemesProvider>
  );
}
