"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  Building2,
  Building2 as BuildingIcon,
  ChevronLeft,
  Clock,
  FileText,
  User as UserIcon,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, adminBuscarChat } from "@/lib/api";
import type { ChatSessionDetail } from "@/lib/types";
import { cn } from "@/lib/utils";


export default function ChatDetailPage({
  params,
}: {
  params: Promise<{ id: string; sessionId: string }>;
}) {
  const { id: tenantId, sessionId } = use(params);
  const [data, setData] = useState<ChatSessionDetail | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    adminBuscarChat(tenantId, sessionId)
      .then(setData)
      .catch((err) => setErro(err instanceof ApiError ? err.message : String(err)));
  }, [tenantId, sessionId]);

  if (erro) {
    return (
      <div className="space-y-3">
        <BackLink tenantId={tenantId} />
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="space-y-3">
        <BackLink tenantId={tenantId} />
        <Skeleton className="h-24" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <BackLink tenantId={tenantId} />

      <div>
        <h2 className="text-xl font-bold">Conversa</h2>
        <div className="text-sm text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 mt-2">
          <span className="inline-flex items-center gap-1.5">
            <UserIcon className="h-3.5 w-3.5" />
            {data.user_nome || data.user_email || "Anônimo"}
            {data.user_email && data.user_nome && (
              <span className="text-xs">({data.user_email})</span>
            )}
          </span>
          {data.referencia && (
            <span className="inline-flex items-center gap-1.5">
              <BuildingIcon className="h-3.5 w-3.5" />
              Cond. {data.referencia}
            </span>
          )}
          <span className="inline-flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            Iniciada em {formatarData(data.started_at)}
          </span>
          <span>{data.mensagens.length} mensagem{data.mensagens.length === 1 ? "" : "s"}</span>
        </div>
      </div>

      <div className="space-y-3">
        {data.mensagens.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
      </div>
    </div>
  );
}


function MessageBubble({
  message,
}: {
  message: ChatSessionDetail["mensagens"][number];
}) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <Avatar role={message.role} />
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-4 py-3 text-sm shadow-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-card border border-border text-card-foreground"
        )}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>

        {!isUser && message.citacoes.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/60">
            <p className="text-[10px] font-semibold text-muted-foreground mb-2 uppercase tracking-wider">
              Fontes
            </p>
            <ul className="flex flex-wrap gap-2">
              {message.citacoes.map((c, i) => (
                <li key={i}>
                  <Badge variant="outline" className="gap-1.5 font-normal">
                    <FileText className="h-3 w-3" />
                    <span className="font-medium">{c.file_name}</span>
                    {c.data_valida && (
                      <span className="text-muted-foreground">· {formatarDataCurta(c.data_valida)}</span>
                    )}
                    {typeof c.similarity === "number" && (
                      <span className="text-muted-foreground">· {(c.similarity * 100).toFixed(0)}%</span>
                    )}
                  </Badge>
                </li>
              ))}
            </ul>
          </div>
        )}

        {!isUser && (typeof message.categoria === "number" || message.trace_id) && (
          <div className="mt-2 pt-2 border-t border-border/60 flex flex-wrap gap-x-3 text-[10px] uppercase tracking-wider text-muted-foreground">
            {typeof message.categoria === "number" && (
              <span>cat {message.categoria}</span>
            )}
            <span>{formatarHora(message.created_at)}</span>
          </div>
        )}
      </div>
    </div>
  );
}


function Avatar({ role }: { role: string }) {
  if (role === "user") {
    return (
      <div className="h-8 w-8 rounded-full bg-secondary text-secondary-foreground grid place-items-center text-xs font-semibold shrink-0">
        U
      </div>
    );
  }
  return (
    <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground grid place-items-center shrink-0">
      <Building2 className="h-4 w-4" />
    </div>
  );
}


function BackLink({ tenantId }: { tenantId: string }) {
  return (
    <Link
      href={`/admin/tenants/${tenantId}/chats`}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ChevronLeft className="h-3 w-3" /> Conversas
    </Link>
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

function formatarHora(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function formatarDataCurta(iso: string): string {
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${d}/${m}/${y}`;
}
