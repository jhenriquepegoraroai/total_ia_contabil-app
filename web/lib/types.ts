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
  referencia?: string | null;  // condomínio default do usuário
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

export interface TenantOpenAIConfig {
  /** "lello" usa a chave global da plataforma; "custom" usa a chave do próprio cliente. */
  mode: "lello" | "custom";
  /** Chave OpenAI (sk-...). Em GETs do admin vem mascarada (`sk-proj...wxyz`). */
  api_key: string | null;
  /** Nome do secret no Secrets Manager (em prod). Opcional. */
  secret_name: string | null;
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
  openai?: TenantOpenAIConfig;
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

// =============================================================================
// Data sources (Fase 6)
// =============================================================================
export type SourceType =
  | "pdf_upload"
  | "excel_upload"
  | "csv_upload"
  | "s3"
  | "azure_blob"
  | "postgres"
  | "sqlserver"
  | "databricks";

export interface SourceSummary {
  id: string;
  tenant_id: string;
  name: string;
  type: SourceType;
  enabled: boolean;
  qtde_files: number;
  last_run_at: string | null;
  last_run_status: "queued" | "running" | "done" | "failed" | null;
  created_at: string;
  updated_at: string;
}

export interface SourceDetail extends SourceSummary {
  config: Record<string, unknown>;
  secret_name: string | null;
}

export interface SourceFile {
  key: string;
  filename: string;
  size_bytes: number;
  last_modified: string | null;
}

export type SourceConfigPayload =
  | { type: "pdf_upload"; referencia_default?: string | null }
  | { type: "excel_upload"; referencia_default?: string | null; coluna_referencia?: string | null; coluna_texto: string }
  | { type: "csv_upload"; referencia_default?: string | null; coluna_referencia?: string | null; coluna_texto: string; delimiter?: string }
  | { type: "s3"; bucket: string; region?: string; prefix?: string; access_key_id?: string; secret_access_key?: string }
  | { type: "azure_blob"; account: string; container: string; prefix?: string; sas_token?: string; account_key?: string }
  | { type: "postgres"; host: string; port?: number; database: string; user: string; password?: string; ssl_mode?: string; table?: string; coluna_referencia?: string; coluna_texto?: string; coluna_data?: string; custom_query?: string }
  | { type: "sqlserver"; host: string; port?: number; database: string; user: string; password?: string; table?: string; coluna_referencia?: string; coluna_texto?: string; coluna_data?: string; custom_query?: string }
  | { type: "databricks"; server_hostname: string; http_path: string; cluster_id: string; table_embeddings: string; access_token?: string };

export interface IngestionJob {
  id: string;
  tenant_id: string;
  source_id: string | null;
  source_name: string | null;
  source_type: string | null;
  referencia: string | null;
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  started_at: string | null;
  finished_at: string | null;
  qtde_chunks_origem: number;
  qtde_processada: number;
  qtde_skipped: number;
  qtde_erros: number;
  duracao_segundos: number | null;
  erro_detalhe: string | null;
  actor_email: string | null;
  created_at: string;
}

export interface TestConnectionResult {
  ok: boolean;
  detail: string;
  metadata: Record<string, unknown>;
}

// =============================================================================
// Users (gerenciar via UI superadmin)
// =============================================================================
export type UserRole = "admin" | "sindico" | "atendente" | "morador";

export interface TenantUser {
  id: string;
  tenant_id: string;
  email: string;
  nome: string;
  role: UserRole;
  referencia: string | null;
  enabled: boolean;
  is_superadmin: boolean;
  tem_senha: boolean;
  created_at: string;
}

export interface CreateUserPayload {
  email: string;
  nome: string;
  role: UserRole;
  password: string;
  referencia?: string | null;
}

export interface UpdateUserPayload {
  nome?: string;
  role?: UserRole;
  enabled?: boolean;
  // Para mudar referencia, envie o valor + referencia_set:true. Sem
  // referencia_set, o backend preserva o valor atual.
  referencia?: string | null;
  referencia_set?: boolean;
}

// =============================================================================
// Histórico de conversas (admin)
// =============================================================================
export interface ChatSessionSummary {
  id: string;
  tenant_id: string;
  user_id: string | null;
  user_email: string | null;
  user_nome: string | null;
  referencia: string | null;
  started_at: string;
  ended_at: string | null;
  qtde_mensagens: number;
  primeira_pergunta: string | null;
  ultima_at: string | null;
}

export interface ChatCitationDetail {
  file_name: string;
  record_id: string | null;
  data_valida: string | null;
  similarity: number | null;
  rank_position: number;
}

export interface ChatMessageDetail {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  categoria: number | null;
  trace_id: string | null;
  created_at: string;
  citacoes: ChatCitationDetail[];
}

export interface ChatSessionDetail {
  id: string;
  tenant_id: string;
  user_id: string | null;
  user_email: string | null;
  user_nome: string | null;
  referencia: string | null;
  started_at: string;
  ended_at: string | null;
  mensagens: ChatMessageDetail[];
}

export interface HealthResponse {
  status: string;
  db: string;
  tenants_enabled: string[];
  version: string;
}

// =============================================================================
// Browser de tabelas (admin → tab Tabelas)
// =============================================================================
export interface TableSummary {
  name: string;
  label: string;
  descricao: string;
  qtde_linhas: number;
  colunas: string[];
}

export interface TableRows {
  table: string;
  label: string;
  descricao: string;
  columns: string[];
  rows: Record<string, unknown>[];
  total: number;
  offset: number;
  limit: number;
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
