/**
 * Cliente HTTP para a API FastAPI.
 *
 * Em DEV, as rotas `/api/*` são proxy via next.config.ts para `http://localhost:8000`.
 * Em PROD, a mesma origem é assumida (deploy atrás de reverse proxy).
 */

import { lerSessao, limparSessao, salvarSessao } from "./auth";
import type {
  ChatRequest,
  ChatResponse,
  HealthResponse,
  TokenResponse,
} from "./types";

const API_BASE = "/api";

class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { auth?: boolean } = {}
): Promise<T> {
  const { auth = true, headers = {}, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers as Record<string, string>),
  };

  if (auth) {
    const session = lerSessao();
    if (session) {
      finalHeaders["Authorization"] = `Bearer ${session.access_token}`;
    }
  }

  const resp = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: finalHeaders,
  });

  if (resp.status === 401) {
    limparSessao();
    throw new ApiError(401, "Sessão expirada. Faça login novamente.");
  }

  if (!resp.ok) {
    let body: unknown;
    try {
      body = await resp.json();
    } catch {
      body = await resp.text();
    }
    throw new ApiError(resp.status, `${resp.status} ${resp.statusText}`, body);
  }

  return (await resp.json()) as T;
}

// ===========================================================================
// Endpoints
// ===========================================================================

export async function devLogin(input: {
  tenant_id: string;
  user_id?: string;
  role?: string;
}): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/auth/dev-token", {
    method: "POST",
    body: JSON.stringify(input),
    auth: false,
  });
  salvarSessao(data);
  return data;
}

export async function chat(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function health(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { method: "GET", auth: false });
}

export { ApiError };
