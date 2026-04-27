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
