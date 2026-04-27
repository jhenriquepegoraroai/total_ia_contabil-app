/**
 * Registry de temas. Lello é o tema default; outros tenants podem
 * registrar variantes aqui ou injetar dinamicamente a partir do
 * `tenant_config.theme` recebido do backend.
 */

import { lelloTheme, type Theme } from "./lello";

export const themes: Record<string, Theme> = {
  lello: lelloTheme,
};

export const defaultTheme = lelloTheme;

export type { Theme } from "./lello";
export { lelloTheme } from "./lello";
