"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  Building2,
  ChevronRight,
  Clock,
  MessageSquare,
  Search,
  User as UserIcon,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, adminListarChats } from "@/lib/api";
import type { ChatSessionSummary } from "@/lib/types";


export default function ChatsListPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: tenantId } = use(params);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [filtro, setFiltro] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    adminListarChats(tenantId, { limit: 200 })
      .then(setSessions)
      .catch((err) => setErro(err instanceof ApiError ? err.message : String(err)))
      .finally(() => setCarregando(false));
  }, [tenantId]);

  const filtradas = sessions.filter((s) => {
    if (!filtro) return true;
    const q = filtro.toLowerCase();
    return (
      (s.user_email && s.user_email.toLowerCase().includes(q)) ||
      (s.user_nome && s.user_nome.toLowerCase().includes(q)) ||
      (s.referencia && s.referencia.toLowerCase().includes(q)) ||
      (s.primeira_pergunta && s.primeira_pergunta.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold flex items-center gap-2">
          <MessageSquare className="h-5 w-5 text-primary" /> Conversas
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Histórico das conversas dos usuários com o assistente. Útil para
          auditoria, melhoria de prompts e identificação de perguntas frequentes.
        </p>
      </div>

      {sessions.length > 0 && (
        <div className="flex items-center gap-2 max-w-md">
          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
          <Input
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
            placeholder="Filtrar por usuário, condomínio ou pergunta..."
            className="h-8 text-sm"
          />
        </div>
      )}

      {erro && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      )}

      {carregando ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      ) : filtradas.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-muted-foreground">
            <MessageSquare className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium text-foreground">
              {sessions.length === 0
                ? "Nenhuma conversa registrada"
                : "Nenhum resultado para esse filtro"}
            </p>
            {sessions.length === 0 && (
              <p className="text-sm mt-1">
                As conversas aparecerão aqui quando os usuários começarem a
                fazer perguntas no chat.
              </p>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y">
              {filtradas.map((s) => (
                <li key={s.id}>
                  <Link
                    href={`/admin/tenants/${tenantId}/chats/${s.id}`}
                    className="block px-4 py-3 hover:bg-muted/40 transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-baseline gap-x-3 mb-0.5">
                          <span className="font-medium truncate inline-flex items-center gap-1.5">
                            <UserIcon className="h-3.5 w-3.5 text-muted-foreground" />
                            {s.user_nome || s.user_email || "Anônimo"}
                          </span>
                          {s.referencia && (
                            <Badge variant="outline" className="gap-1 text-[10px] py-0 px-1.5">
                              <Building2 className="h-2.5 w-2.5" /> {s.referencia}
                            </Badge>
                          )}
                          <Badge variant="secondary" className="text-[10px] py-0 px-1.5">
                            {s.qtde_mensagens} msg
                          </Badge>
                        </div>
                        {s.primeira_pergunta && (
                          <p className="text-sm text-muted-foreground italic line-clamp-1">
                            “{s.primeira_pergunta}”
                          </p>
                        )}
                        <div className="text-[10px] text-muted-foreground/70 mt-1 inline-flex items-center gap-1">
                          <Clock className="h-2.5 w-2.5" />
                          {formatarData(s.ultima_at || s.started_at)}
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground/50 shrink-0 mt-1" />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}


function formatarData(iso: string): string {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
