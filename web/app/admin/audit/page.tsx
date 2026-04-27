"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  CircleSlash,
  Edit,
  LogIn,
  Plus,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, adminListarAudit } from "@/lib/api";
import type { AuditEntry } from "@/lib/types";


const ACTION_META: Record<
  AuditEntry["action"],
  { label: string; icon: React.ComponentType<{ className?: string }>; tone: "default" | "destructive" | "secondary" | "outline" }
> = {
  tenant_create: { label: "criou tenant", icon: Plus, tone: "default" },
  tenant_update: { label: "editou tenant", icon: Edit, tone: "secondary" },
  tenant_enable: { label: "ativou tenant", icon: CheckCircle2, tone: "default" },
  tenant_disable: { label: "desativou tenant", icon: CircleSlash, tone: "outline" },
  tenant_delete: { label: "removeu tenant", icon: Trash2, tone: "destructive" },
  superadmin_login: { label: "logou como superadmin", icon: LogIn, tone: "outline" },
};


export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    adminListarAudit({ limit: 100 })
      .then(setEntries)
      .catch((err) =>
        setErro(err instanceof ApiError ? err.message : String(err))
      )
      .finally(() => setCarregando(false));
  }, []);

  return (
    <>
      <header className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-primary" /> Auditoria
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Histórico das últimas 100 ações de superadmin sobre os tenants.
        </p>
      </header>

      {erro && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      )}

      {carregando ? (
        <div className="space-y-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      ) : entries.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-muted-foreground">
            <ShieldCheck className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium text-foreground">Sem ações registradas</p>
            <p className="text-sm mt-1">
              Crie ou edite tenants em /admin pra começar a popular o log.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y">
              {entries.map((e) => {
                const meta = ACTION_META[e.action];
                const Icon = meta?.icon ?? ShieldCheck;
                return (
                  <li
                    key={e.id}
                    className="px-4 py-3 flex items-start gap-3 text-sm hover:bg-muted/40 transition-colors"
                  >
                    <Badge variant={meta?.tone ?? "outline"} className="mt-0.5 gap-1 shrink-0">
                      <Icon className="h-3 w-3" /> {meta?.label ?? e.action}
                    </Badge>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-baseline gap-x-2">
                        <span className="font-medium truncate">{e.actor_email}</span>
                        {e.target_tenant_id && (
                          <span className="text-muted-foreground">
                            → <code className="text-xs">{e.target_tenant_id}</code>
                          </span>
                        )}
                      </div>
                      {e.payload && Object.keys(e.payload).length > 0 && (
                        <pre className="text-xs text-muted-foreground mt-1 font-mono whitespace-pre-wrap break-all">
                          {JSON.stringify(e.payload, null, 0)}
                        </pre>
                      )}
                      {(e.ip_address || e.user_agent) && (
                        <div className="text-[10px] text-muted-foreground/70 mt-1 truncate">
                          {e.ip_address && <span>{e.ip_address}</span>}
                          {e.ip_address && e.user_agent && <span> · </span>}
                          {e.user_agent && <span title={e.user_agent}>{shortUA(e.user_agent)}</span>}
                        </div>
                      )}
                    </div>
                    <time className="text-xs text-muted-foreground shrink-0 tabular-nums">
                      {formatarData(e.created_at)}
                    </time>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}
    </>
  );
}

function formatarData(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("pt-BR", {
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

function shortUA(ua: string): string {
  if (ua.length < 60) return ua;
  return ua.slice(0, 57) + "...";
}
