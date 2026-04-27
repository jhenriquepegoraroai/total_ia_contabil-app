"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { LayoutDashboard, Building2, ShieldCheck, LogOut, ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LelloLogo } from "@/components/lello-logo";
import { lerSessao } from "@/lib/auth";
import { logout as logoutApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/admin", label: "Tenants", icon: Building2 },
  { href: "/admin/audit", label: "Auditoria", icon: ShieldCheck },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [sessaoOk, setSessaoOk] = useState<boolean | null>(null);
  const [email, setEmail] = useState<string>("");

  useEffect(() => {
    const s = lerSessao();
    if (!s) {
      router.replace("/login?next=/admin");
      return;
    }
    if (!s.is_superadmin) {
      router.replace("/?error=acesso_negado");
      return;
    }
    setSessaoOk(true);
    setEmail(s.user_id);
  }, [router]);

  async function logout() {
    await logoutApi();
    router.replace("/login");
  }

  if (!sessaoOk) return null;

  return (
    <div className="min-h-screen flex bg-muted/40">
      <aside className="w-64 bg-card border-r flex flex-col">
        <div className="p-4 border-b">
          <Link href="/admin" className="flex items-center gap-2">
            <LelloLogo className="h-7" />
          </Link>
          <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-secondary text-secondary-foreground px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider">
            <ShieldCheck className="h-3 w-3" /> Superadmin
          </div>
        </div>

        <nav className="flex-1 p-2 space-y-1">
          {NAV.map((item) => {
            const Icon = item.icon;
            const ativo = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                  ativo
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-foreground hover:bg-accent/50"
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-3 border-t space-y-2">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronLeft className="h-3 w-3" /> Voltar pro chat
          </Link>
          <div className="text-xs text-muted-foreground truncate" title={email}>
            {email}
          </div>
          <Button variant="ghost" size="sm" onClick={logout} className="w-full justify-start gap-2">
            <LogOut className="h-3.5 w-3.5" /> Sair
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto p-6 sm:p-8">{children}</div>
      </main>
    </div>
  );
}
