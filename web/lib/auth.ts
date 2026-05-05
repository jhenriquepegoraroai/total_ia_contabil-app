/**
 * Auth client-side.
 *
 * O JWT vive em cookie HttpOnly setado pelo backend — JS desta página
 * NÃO o lê (defesa contra XSS). O que guardamos aqui é só metadado de
 * UI: tenant_id, user_id, is_superadmin, suficiente para roteamento e
 * exibição. O cookie é o que autoriza as chamadas à API.
 */

import type { TokenResponse } from "./types";

const STORAGE_KEY = "avc_session";

interface StoredSession {
  tenant_id: string;
  user_id: string;
  role: string;
  is_superadmin: boolean;
  referencia: string | null;
  modulos_contratados: Record<string, boolean>;
}

export function salvarSessao(token: TokenResponse): void {
  if (typeof window === "undefined") return;
  const session: StoredSession = {
    tenant_id: token.tenant_id,
    user_id: token.user_id,
    role: token.role ?? "morador",
    is_superadmin: token.is_superadmin ?? false,
    referencia: token.referencia ?? null,
    modulos_contratados: token.modulos_contratados ?? {},
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function lerSessao(): StoredSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<StoredSession>;
    return {
      tenant_id: parsed.tenant_id ?? "",
      user_id: parsed.user_id ?? "",
      role: parsed.role ?? "morador",
      is_superadmin: parsed.is_superadmin ?? false,
      referencia: parsed.referencia ?? null,
      modulos_contratados: parsed.modulos_contratados ?? {},
    };
  } catch {
    window.localStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function limparSessao(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}

export function estaAutenticado(): boolean {
  return lerSessao() !== null;
}
