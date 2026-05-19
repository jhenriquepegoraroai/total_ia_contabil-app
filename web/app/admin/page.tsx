"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Building2,
  CheckCircle2,
  CircleSlash,
  Database,
  FileText,
  Plus,
  Users,
  Loader2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  adminListarModulos,
  adminListarTenants,
  adminToggleEnabled,
} from "@/lib/api";
import type { ModuloInfo, TenantSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function AdminTenantsPage() {
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [modulosCatalogo, setModulosCatalogo] = useState<Record<string, ModuloInfo>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  async function carregar() {
    try {
      const [data, catalogo] = await Promise.all([
        adminListarTenants(),
        adminListarModulos(),
      ]);
      setTenants(data);
      setModulosCatalogo(Object.fromEntries(catalogo.map((m) => [m.slug, m])));
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregar();
  }, []);

  async function toggle(t: TenantSummary) {
    setTogglingId(t.id);
    try {
      await adminToggleEnabled(t.id, !t.enabled);
      await carregar();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <>
      <header className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold">Administradoras</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Cadastre e gerencie as administradoras de condomínios atendidas pelo
            assistente.
          </p>
        </div>
        <Button asChild>
          <Link href="/admin/tenants/new">
            <Plus className="h-4 w-4" /> Nova administradora
          </Link>
        </Button>
      </header>

      {erro && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      )}

      {carregando ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-44" />
          ))}
        </div>
      ) : tenants.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-muted-foreground">
            <Building2 className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium text-foreground">Nenhuma administradora cadastrada</p>
            <p className="text-sm mt-1">
              Comece criando a primeira via "Nova administradora".
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {tenants.map((t) => (
            <Card
              key={t.id}
              className={cn(
                "hover:shadow-md transition-shadow",
                !t.enabled && "opacity-70"
              )}
            >
              <CardContent className="p-5 space-y-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="font-semibold truncate" title={t.nome_empresa}>
                      {t.nome_empresa}
                    </h3>
                    <code className="text-xs text-muted-foreground">{t.id}</code>
                  </div>
                  {t.enabled ? (
                    <Badge variant="default" className="gap-1 shrink-0">
                      <CheckCircle2 className="h-3 w-3" /> Ativo
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="gap-1 shrink-0">
                      <CircleSlash className="h-3 w-3" /> Inativo
                    </Badge>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <Stat icon={FileText} label="docs" value={t.qtde_documents} />
                  <Stat icon={Database} label="chunks" value={t.qtde_embeddings} />
                  <Stat icon={Users} label="users" value={t.qtde_users} />
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {t.datasource_type && (
                    <span className="text-xs text-muted-foreground">
                      fonte: <code>{t.datasource_type}</code>
                    </span>
                  )}
                  {t.modalidade && (
                    <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                      Mod. {t.modalidade}
                    </span>
                  )}
                </div>

                <ModulosBadges
                  modulos={t.modulos_contratados}
                  catalogo={modulosCatalogo}
                />

                <div className="flex gap-2 pt-1">
                  <Button asChild variant="outline" size="sm" className="flex-1">
                    <Link href={`/admin/tenants/${t.id}`}>Abrir</Link>
                  </Button>
                  <Button
                    variant={t.enabled ? "outline" : "default"}
                    size="sm"
                    onClick={() => toggle(t)}
                    disabled={togglingId === t.id}
                    className="flex-1"
                  >
                    {togglingId === t.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : t.enabled ? (
                      "Desativar"
                    ) : (
                      "Ativar"
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number;
}) {
  return (
    <div className="rounded-md bg-muted/50 px-2 py-2">
      <Icon className="h-3.5 w-3.5 mx-auto mb-1 text-muted-foreground" />
      <div className="font-semibold">{value.toLocaleString("pt-BR")}</div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
    </div>
  );
}

function ModulosBadges({
  modulos,
  catalogo,
}: {
  modulos: Record<string, boolean> | undefined;
  catalogo: Record<string, ModuloInfo>;
}) {
  const ativos = Object.entries(modulos ?? {})
    .filter(([, ativo]) => ativo)
    .map(([slug]) => slug);
  if (ativos.length === 0) {
    return (
      <div className="text-xs text-muted-foreground italic">Sem módulos contratados</div>
    );
  }
  return (
    <div className="flex flex-wrap gap-1">
      {ativos.map((slug) => (
        <Badge key={slug} variant="secondary" className="text-[10px]">
          {catalogo[slug]?.label ?? slug}
        </Badge>
      ))}
    </div>
  );
}
