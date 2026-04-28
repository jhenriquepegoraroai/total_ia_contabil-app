/**
 * Cliente HTTP para a API FastAPI.
 *
 * Em DEV, as rotas `/api/*` são proxy via next.config.ts para `http://localhost:8000`.
 * Em PROD, a mesma origem é assumida (deploy atrás de reverse proxy).
 */

import { limparSessao, salvarSessao } from "./auth";
import type {
  AuditEntry,
  ChatRequest,
  ChatResponse,
  ChatSessionDetail,
  ChatSessionSummary,
  CreateUserPayload,
  HealthResponse,
  IngestionJob,
  SourceConfigPayload,
  SourceDetail,
  SourceFile,
  SourceSummary,
  TableRows,
  TableSummary,
  TenantConfig,
  TenantSummary,
  TenantUser,
  TestConnectionResult,
  TokenResponse,
  UpdateUserPayload,
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
  const { auth: _auth = true, headers = {}, ...rest } = options;
  // Intencionalmente ignorado: a auth agora vem 100% do cookie HttpOnly
  // setado pelo /auth/login. Mantemos o param para retrocompat dos call
  // sites — vai sair em uma limpeza futura.
  void _auth;

  const finalHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...(headers as Record<string, string>),
  };

  const resp = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: finalHeaders,
    credentials: "same-origin",
  });

  if (resp.status === 401) {
    limparSessao();
    throw new ApiError(401, "Sessão expirada. Faça login novamente.");
  }

  if (!resp.ok) {
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

  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// ===========================================================================
// Auth
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

export async function logout(): Promise<void> {
  try {
    await request<void>("/auth/logout", { method: "POST", auth: false });
  } catch {
    // Mesmo se a chamada falhar (rede etc.), limpamos o estado local
    // para que a UI volte ao login. O cookie expira por max-age de toda
    // forma.
  }
  limparSessao();
}

// ===========================================================================
// Chat / Health
// ===========================================================================
export async function chat(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function health(): Promise<HealthResponse> {
  return request<HealthResponse>("/health", { method: "GET", auth: false });
}

// ===========================================================================
// Admin — tenants
// ===========================================================================
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

// ===========================================================================
// Admin — sources
// ===========================================================================
export async function adminListarSources(tenantId: string): Promise<SourceSummary[]> {
  return request<SourceSummary[]>(`/admin/tenants/${encodeURIComponent(tenantId)}/sources`);
}

export async function adminBuscarSource(
  tenantId: string,
  sourceId: string
): Promise<SourceDetail> {
  return request<SourceDetail>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/sources/${sourceId}`
  );
}

export async function adminCriarSource(
  tenantId: string,
  body: { name: string; config: SourceConfigPayload; secret_name?: string }
): Promise<SourceDetail> {
  return request<SourceDetail>(`/admin/tenants/${encodeURIComponent(tenantId)}/sources`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function adminAtualizarSource(
  tenantId: string,
  sourceId: string,
  body: {
    name: string;
    config: SourceConfigPayload;
    secret_name?: string | null;
    enabled?: boolean | null;
  }
): Promise<SourceDetail> {
  return request<SourceDetail>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/sources/${sourceId}`,
    {
      method: "PATCH",
      body: JSON.stringify(body),
    }
  );
}

export async function adminDeletarSource(
  tenantId: string,
  sourceId: string
): Promise<void> {
  await request<void>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/sources/${sourceId}`,
    { method: "DELETE" }
  );
}

export async function adminTestarConexao(
  config: SourceConfigPayload
): Promise<TestConnectionResult> {
  return request<TestConnectionResult>("/admin/sources/test-connection", {
    method: "POST",
    body: JSON.stringify({ config }),
  });
}

export async function adminListarFiles(
  tenantId: string,
  sourceId: string
): Promise<SourceFile[]> {
  return request<SourceFile[]>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/sources/${sourceId}/files`
  );
}

export async function adminUploadFiles(
  tenantId: string,
  sourceId: string,
  files: File[]
): Promise<{
  uploaded: { filename: string; key: string; size_bytes: number; ok: boolean; erro: string | null }[];
}> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f, f.name);

  const resp = await fetch(
    `/api/admin/tenants/${encodeURIComponent(tenantId)}/sources/${sourceId}/files`,
    { method: "POST", body: fd, credentials: "same-origin" }
  );
  if (!resp.ok) {
    const raw = await resp.text();
    throw new ApiError(resp.status, raw || `${resp.status}`, raw);
  }
  return await resp.json();
}

// ===========================================================================
// Admin — ingestion jobs
// ===========================================================================
export async function adminDispararJob(
  tenantId: string,
  body: { source_id: string; referencia?: string }
): Promise<IngestionJob> {
  return request<IngestionJob>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/ingestions`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export async function adminListarJobs(
  tenantId: string,
  limit = 50
): Promise<IngestionJob[]> {
  return request<IngestionJob[]>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/ingestions?limit=${limit}`
  );
}

export async function adminBuscarJob(
  tenantId: string,
  jobId: string
): Promise<IngestionJob> {
  return request<IngestionJob>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/ingestions/${jobId}`
  );
}

// ===========================================================================
// Admin — usuários do tenant
// ===========================================================================
export async function adminListarUsuarios(tenantId: string): Promise<TenantUser[]> {
  return request<TenantUser[]>(`/admin/tenants/${encodeURIComponent(tenantId)}/users`);
}

export async function adminCriarUsuario(
  tenantId: string,
  payload: CreateUserPayload
): Promise<TenantUser> {
  return request<TenantUser>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/users`,
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export async function adminAtualizarUsuario(
  tenantId: string,
  userId: string,
  payload: UpdateUserPayload
): Promise<TenantUser> {
  return request<TenantUser>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/users/${userId}`,
    { method: "PATCH", body: JSON.stringify(payload) }
  );
}

export async function adminResetarSenha(
  tenantId: string,
  userId: string,
  novaSenha: string
): Promise<void> {
  await request<void>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/users/${userId}/password`,
    { method: "PATCH", body: JSON.stringify({ nova_senha: novaSenha }) }
  );
}

export async function adminDeletarUsuario(
  tenantId: string,
  userId: string
): Promise<void> {
  await request<void>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/users/${userId}`,
    { method: "DELETE" }
  );
}

// ===========================================================================
// Admin — histórico de conversas
// ===========================================================================
export async function adminListarChats(
  tenantId: string,
  params?: { limit?: number; referencia?: string }
): Promise<ChatSessionSummary[]> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.referencia) qs.set("referencia", params.referencia);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<ChatSessionSummary[]>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/chats${suffix}`
  );
}

export async function adminBuscarChat(
  tenantId: string,
  sessionId: string
): Promise<ChatSessionDetail> {
  return request<ChatSessionDetail>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/chats/${sessionId}`
  );
}

// ===========================================================================
// Admin — browser de tabelas (debug do superadmin)
// ===========================================================================
export async function adminListarTabelas(
  tenantId: string
): Promise<TableSummary[]> {
  return request<TableSummary[]>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/tables`
  );
}

export async function adminListarRowsTabela(
  tenantId: string,
  tabela: string,
  params?: { referencia?: string; q?: string; offset?: number; limit?: number }
): Promise<TableRows> {
  const qs = new URLSearchParams();
  if (params?.referencia) qs.set("referencia", params.referencia);
  if (params?.q) qs.set("q", params.q);
  if (params?.offset !== undefined) qs.set("offset", String(params.offset));
  if (params?.limit !== undefined) qs.set("limit", String(params.limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<TableRows>(
    `/admin/tenants/${encodeURIComponent(tenantId)}/tables/${encodeURIComponent(tabela)}${suffix}`
  );
}

export { ApiError };
