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
    // Body stream só pode ser consumido uma vez — text() primeiro, parse JSON depois.
    const raw = await resp.text();
    let body: unknown = raw;
    try {
      body = JSON.parse(raw);
    } catch {
      /* mantém raw como string */
    }
    const detail =
      typeof body === "object" && body && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : raw || `${resp.status} ${resp.statusText}`;
    throw new ApiError(resp.status, detail, body);
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

export async function login(input: {
  email: string;
  password: string;
  tenant_id?: string;
}): Promise<TokenResponse> {
  const data = await request<TokenResponse>("/auth/login", {
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

// =============================================================================
// Admin endpoints
// =============================================================================
import type { AuditEntry, TenantConfig, TenantSummary } from "./types";

export async function adminListarTenants(): Promise<TenantSummary[]> {
  return request<TenantSummary[]>("/admin/tenants");
}

export async function adminBuscarTenant(tenantId: string): Promise<{
  id: string;
  nome_empresa: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  config: TenantConfig;
}> {
  return request(`/admin/tenants/${encodeURIComponent(tenantId)}`);
}

export async function adminCriarTenant(config: TenantConfig): Promise<unknown> {
  return request("/admin/tenants", {
    method: "POST",
    body: JSON.stringify(config),
  });
}

export async function adminAtualizarTenant(
  tenantId: string,
  config: TenantConfig
): Promise<unknown> {
  return request(`/admin/tenants/${encodeURIComponent(tenantId)}`, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

export async function adminToggleEnabled(
  tenantId: string,
  enabled: boolean
): Promise<TenantSummary> {
  return request<TenantSummary>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/enabled`,
    {
      method: "PATCH",
      body: JSON.stringify({ enabled }),
    }
  );
}

export async function adminListarAudit(params?: {
  limit?: number;
  target_tenant_id?: string;
}): Promise<AuditEntry[]> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.target_tenant_id) qs.set("target_tenant_id", params.target_tenant_id);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<AuditEntry[]>(`/admin/audit${suffix}`);
}

export { ApiError };
