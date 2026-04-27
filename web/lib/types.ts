/**
 * Tipos compartilhados entre web/lib e web/components.
 * Espelham os schemas Pydantic do backend (api/routers/chat.py, auth.py).
 */

export interface ChatRequest {
  pergunta: string;
  referencia: string;
  session_id?: string;
}

export interface Citacao {
  file_name: string;
  record_id?: string | null;
  data_valida?: string | null;
  similarity?: number | null;
}

export interface ChatResponse {
  resposta: string;
  categoria: number | null;
  citacoes: Citacao[];
  via: string;
  session_id: string;
  trace_id: string;
  duracao_ms: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  tenant_id: string;
  user_id: string;
  is_superadmin?: boolean;
}

// =============================================================================
// Admin
// =============================================================================
export interface TenantSummary {
  id: string;
  nome_empresa: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  qtde_documents: number;
  qtde_embeddings: number;
  qtde_users: number;
  datasource_type: string | null;
}

export interface TenantTheme {
  primary: string;
  primary_foreground: string;
  secondary: string;
  secondary_foreground: string;
  accent: string;
  accent_foreground: string;
  ink: string;
  muted: string;
  background: string;
  logo_url: string;
  favicon_url: string;
  font_family: string;
}

export interface TenantContatos {
  telefone: string;
  whatsapp: string;
  whatsapp_link: string;
  email: string;
  horario_atendimento?: string;
}

export interface TenantURLs {
  app_moradores: string;
  portal_resolva_facil: string;
  prestacao_contas?: string | null;
  cadastro_inquilino?: string | null;
}

export interface TenantConfig {
  schema_version?: string;
  tenant_id: string;
  nome_empresa: string;
  nome_assistente: string;
  enabled: boolean;
  contatos: TenantContatos;
  urls: TenantURLs;
  datasource: { type: "postgres_pgvector" } | { type: "databricks"; [k: string]: unknown };
  theme?: Partial<TenantTheme>;
  rag?: { top_k?: number; similarity_threshold?: number; completion_temperature?: number };
  schemas_estruturados?: Record<string, string>;
  prompt_principal: string;
  prompt_formatacao: string;
  prompt_esclarecimento: string;
  categorias_prompt: string;
  prompts_por_categoria?: Record<string, string>;
  respostas_padrao?: Record<string, string>;
  resposta_sem_documento: string;
  mensagem_nao_encontrada: string;
  regra_concorrentes?: string;
  leis_referencia?: string;
}

export interface AuditEntry {
  id: number;
  actor_user_id: string;
  actor_email: string;
  action:
    | "tenant_create"
    | "tenant_update"
    | "tenant_enable"
    | "tenant_disable"
    | "tenant_delete"
    | "superadmin_login";
  target_tenant_id: string | null;
  payload: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface HealthResponse {
  status: string;
  db: string;
  tenants_enabled: string[];
  version: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citacoes?: Citacao[];
  categoria?: number | null;
  via?: string;
  trace_id?: string;
  duracao_ms?: number;
  pending?: boolean;
  error?: boolean;
}
