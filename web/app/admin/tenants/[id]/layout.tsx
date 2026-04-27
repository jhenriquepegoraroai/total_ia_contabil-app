"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { use } from "react";
import {
  Building2,
  Database,
  History,
  ChevronLeft,
  MessageSquare,
  Users as UsersIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

const TABS = [
  { suffix: "", label: "Visão geral", icon: Building2 },
  { suffix: "/sources", label: "Fontes de dados", icon: Database },
  { suffix: "/users", label: "Usuários", icon: UsersIcon },
  { suffix: "/chats", label: "Conversas", icon: MessageSquare },
  { suffix: "/jobs", label: "Histórico de jobs", icon: History },
];

export default function TenantLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const pathname = usePathname();
  const base = `/admin/tenants/${id}`;

  return (
    <>
      <Link
        href="/admin"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3"
      >
        <ChevronLeft className="h-3 w-3" /> Tenants
      </Link>

      <div className="border-b mb-6">
        <nav className="flex gap-1 -mb-px">
          {TABS.map((t) => {
            const href = `${base}${t.suffix}`;
            const ativo =
              t.suffix === ""
                ? pathname === base
                : pathname.startsWith(`${base}${t.suffix}`);
            const Icon = t.icon;
            return (
              <Link
                key={t.suffix}
                href={href}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 text-sm border-b-2 transition-colors",
                  ativo
                    ? "border-primary text-primary font-medium"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" /> {t.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {children}
    </>
  );
}
