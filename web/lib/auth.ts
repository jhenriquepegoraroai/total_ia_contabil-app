/**
 * Auth client-side.
 *
 * NOTA: usamos localStorage para o token. Em produção, mover para cookie
 * httpOnly setado pelo backend (mais seguro contra XSS).
 */

import type { TokenResponse } from "./types";

const STORAGE_KEY = "avc_session";

interface StoredSession {
  access_token: string;
  tenant_id: string;
  user_id: string;
  is_superadmin: boolean;
}

export function salvarSessao(token: TokenResponse): void {
  if (typeof window === "undefined") return;
  const session: StoredSession = {
    access_token: token.access_token,
    tenant_id: token.tenant_id,
    user_id: token.user_id,
    is_superadmin: token.is_superadmin ?? false,
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
      access_token: parsed.access_token ?? "",
      tenant_id: parsed.tenant_id ?? "",
      user_id: parsed.user_id ?? "",
      is_superadmin: parsed.is_superadmin ?? false,
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
