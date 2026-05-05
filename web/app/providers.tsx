"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import * as React from "react";

import { ToastProvider } from "@/components/ui/toast";

/**
 * Providers globais — tema (next-themes) + sistema de toasts.
 *
 * Para multi-tenant: o tenant atual injeta variantes via CSS variables
 * (lidas em globals.css). next-themes só controla light/dark.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="light"
      enableSystem
      disableTransitionOnChange
    >
      <ToastProvider>{children}</ToastProvider>
    </NextThemesProvider>
  );
}
