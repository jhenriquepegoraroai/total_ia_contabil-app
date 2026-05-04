"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  FileJson,
  FileText,
  LogOut,
  Menu,
  MessageCircle,
  Users,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { LelloLogo } from "@/components/lello-logo";
import { logout as logoutApi } from "@/lib/api";


interface SidebarItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  visible: boolean;
}


/**
 * Shell padrão das páginas pós-login do TENANT (chat / cobranças / atas / usuários).
 *
 * Header sempre visível. Hamburger (drawer lateral) só aparece pra
 * `role === "admin"` — outros roles (síndico, presidente, atendente,
 * morador) têm header simples sem menu de navegação.
 *
 * Visibilidade dos itens da sidebar é gateada pelos `modulos`
 * contratados pelo tenant (vem na sessão após login):
 *   - Bella Chat       → tenant tem `chat` contratado
 *   - Bella Cobranças  → tenant tem `cobrancas` contratado
 *   - Bella Atas       → tenant tem `atas` contratado
 *   - Usuários         → sempre visível (a rota é gateada no backend)
 *
 * Itens cujas páginas ainda não estão neste branch (ex: /cobrancas e
 * /usuarios vivem em branch paralelo) seguem aparecendo no menu como
 * documentação visual do produto. O 404 só ocorre se o usuário clicar
 * antes do merge.
 */
export function AppShell({
  children,
  tenantId,
  role,
  modulos,
}: {
  children: React.ReactNode;
  tenantId: string;
  role: string;
  modulos: Record<string, boolean>;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Fecha drawer ao navegar.
  useEffect(() => {
    setDrawerOpen(false);
  }, [pathname]);

  // ESC fecha drawer.
  useEffect(() => {
    if (!drawerOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setDrawerOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const isAdmin = role === "admin";

  const items: SidebarItem[] = [
    {
      href: "/",
      label: "Bella Chat",
      icon: MessageCircle,
      visible: !!modulos.chat,
    },
    {
      href: "/cobrancas",
      label: "Bella Cobranças",
      icon: FileJson,
      visible: !!modulos.cobrancas,
    },
    {
      href: "/atas",
      label: "Bella Atas",
      icon: FileText,
      visible: !!modulos.atas,
    },
    {
      href: "/usuarios",
      label: "Usuários",
      icon: Users,
      visible: true, // backend gateia se não for admin
    },
  ];

  async function logout() {
    await logoutApi();
    router.replace("/login");
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="border-b bg-card/50 backdrop-blur supports-[backdrop-filter]:bg-card/50 sticky top-0 z-20">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {isAdmin && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setDrawerOpen(true)}
                title="Abrir menu"
                aria-label="Abrir menu de navegação"
              >
                <Menu />
              </Button>
            )}
            <LelloLogo className="h-7" />
          </div>
          <div className="flex items-center gap-3 text-sm">
            <div className="text-right hidden sm:block">
              <div className="text-xs text-muted-foreground">Administradora</div>
              <div className="font-medium">{tenantId}</div>
            </div>
            <Button variant="ghost" size="icon" onClick={logout} title="Sair">
              <LogOut />
            </Button>
          </div>
        </div>
      </header>

      {/* Drawer (apenas admin renderiza) */}
      {isAdmin && (
        <>
          <div
            onClick={() => setDrawerOpen(false)}
            className={`fixed inset-0 z-30 bg-black/40 transition-opacity duration-200 ${
              drawerOpen ? "opacity-100" : "opacity-0 pointer-events-none"
            }`}
            aria-hidden
          />
          <aside
            className={`fixed top-0 left-0 z-40 h-full w-72 bg-card border-r shadow-xl transition-transform duration-200 ${
              drawerOpen ? "translate-x-0" : "-translate-x-full"
            }`}
            aria-hidden={!drawerOpen}
          >
            <div className="flex items-center justify-between p-4 border-b">
              <div className="font-semibold">Menu</div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setDrawerOpen(false)}
                title="Fechar menu"
              >
                <X />
              </Button>
            </div>
            <nav className="p-2 space-y-1">
              {items
                .filter((it) => it.visible)
                .map((it) => {
                  const Icon = it.icon;
                  const ativo = pathname === it.href || pathname.startsWith(it.href + "/");
                  return (
                    <Link
                      key={it.href}
                      href={it.href}
                      className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                        ativo
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-accent/50"
                      }`}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      <span>{it.label}</span>
                    </Link>
                  );
                })}
            </nav>
            <div className="absolute bottom-0 left-0 right-0 p-3 border-t text-[11px] text-muted-foreground">
              Logado como <code className="font-mono">admin</code> · tenant{" "}
              <code className="font-mono">{tenantId}</code>
            </div>
          </aside>
        </>
      )}

      <div className="flex-1 flex flex-col">{children}</div>
    </div>
  );
}
