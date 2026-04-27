"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, Suspense } from "react";
import { LogIn, Loader2, ShieldCheck, FlaskConical } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, devLogin, health, login } from "@/lib/api";
import { LelloLogo } from "@/components/lello-logo";

type Mode = "user" | "admin";

function LoginInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next");
  const initialMode: Mode = next?.startsWith("/admin") ? "admin" : "user";

  const [mode, setMode] = useState<Mode>(initialMode);
  const [tenantId, setTenantId] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [tenantsDisponiveis, setTenantsDisponiveis] = useState<string[]>([]);
  const [mostrarDevToken, setMostrarDevToken] = useState(false);
  const [devTokenTenant, setDevTokenTenant] = useState("");
  const [devTokenUserId, setDevTokenUserId] = useState("dev_user");

  useEffect(() => {
    health()
      .then((h) => {
        setTenantsDisponiveis(h.tenants_enabled);
        if (h.tenants_enabled.length && !tenantId) {
          setTenantId(h.tenants_enabled[0]);
          setDevTokenTenant(h.tenants_enabled[0]);
        }
      })
      .catch(() => setTenantsDisponiveis([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      if (mode === "admin") {
        const resp = await login({ email: email.trim(), password });
        if (!resp.is_superadmin) {
          router.push("/");
          return;
        }
        router.push(next && next.startsWith("/admin") ? next : "/admin");
      } else {
        await login({
          email: email.trim(),
          password,
          tenant_id: tenantId.trim() || undefined,
        });
        router.push(next && !next.startsWith("/admin") ? next : "/");
      }
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(false);
    }
  }

  async function entrarComDevToken() {
    setErro(null);
    setEnviando(true);
    try {
      await devLogin({
        tenant_id: devTokenTenant.trim(),
        user_id: devTokenUserId.trim() || "dev_user",
        role: "admin",
      });
      router.push("/");
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-accent/30 px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader className="items-center text-center space-y-4">
          <LelloLogo className="h-10" />
          <div>
            <CardTitle className="text-2xl">Assistente Virtual de Condomínios</CardTitle>
            <CardDescription className="mt-2">
              {mode === "admin"
                ? "Entrar como superadmin."
                : "Entre para tirar dúvidas sobre o seu condomínio."}
            </CardDescription>
          </div>
        </CardHeader>

        <div className="px-6 pb-2">
          <div className="grid grid-cols-2 rounded-md bg-muted p-1 text-sm">
            <button
              type="button"
              onClick={() => {
                setMode("user");
                setErro(null);
                setMostrarDevToken(false);
              }}
              className={`rounded-sm py-1.5 transition-colors ${
                mode === "user"
                  ? "bg-background shadow-sm font-medium"
                  : "text-muted-foreground"
              }`}
            >
              Usuário
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("admin");
                setErro(null);
                setMostrarDevToken(false);
              }}
              className={`rounded-sm py-1.5 transition-colors inline-flex items-center justify-center gap-1.5 ${
                mode === "admin"
                  ? "bg-background shadow-sm font-medium"
                  : "text-muted-foreground"
              }`}
            >
              <ShieldCheck className="h-3.5 w-3.5" />
              Superadmin
            </button>
          </div>
        </div>

        <form onSubmit={onSubmit}>
          <CardContent className="space-y-4">
            {mode === "user" && (
              <div className="space-y-1">
                <label htmlFor="tenant" className="text-sm font-medium">
                  Administradora
                </label>
                <Input
                  id="tenant"
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  placeholder="lello"
                  required
                  autoFocus={mode === "user"}
                />
                {tenantsDisponiveis.length > 0 && (
                  <p className="text-xs text-muted-foreground pt-1">
                    Disponíveis: {tenantsDisponiveis.join(", ")}
                  </p>
                )}
              </div>
            )}

            <div className="space-y-1">
              <label htmlFor="email" className="text-sm font-medium">
                E-mail
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={mode === "admin" ? "admin@empresa.com" : "morador@email.com"}
                required
                autoFocus={mode === "admin"}
                autoComplete="email"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="password" className="text-sm font-medium">
                Senha
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </div>

            {erro && (
              <div className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
                {erro}
              </div>
            )}
          </CardContent>
          <CardFooter className="flex-col gap-3">
            <Button type="submit" className="w-full" disabled={enviando}>
              {enviando ? (
                <>
                  <Loader2 className="animate-spin" /> Entrando...
                </>
              ) : (
                <>
                  <LogIn /> Entrar
                </>
              )}
            </Button>

            {/*
              Modo DEV: token rápido sem credencial. Em prod, /auth/dev-token retorna
              404 e o link some. Mantemos pra desenvolvimento e demos.
            */}
            {mode === "user" && (
              <button
                type="button"
                onClick={() => setMostrarDevToken((m) => !m)}
                className="text-xs text-muted-foreground/80 hover:text-foreground inline-flex items-center gap-1"
              >
                <FlaskConical className="h-3 w-3" />
                {mostrarDevToken ? "Esconder" : "Ou usar token rápido (DEV)"}
              </button>
            )}
          </CardFooter>
        </form>

        {mostrarDevToken && mode === "user" && (
          <CardContent className="border-t pt-4 space-y-3">
            <div className="text-xs text-muted-foreground">
              Modo desenvolvimento — gera JWT direto via{" "}
              <code className="font-mono">/auth/dev-token</code>, sem validar
              credencial. Indisponível em produção.
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input
                value={devTokenTenant}
                onChange={(e) => setDevTokenTenant(e.target.value)}
                placeholder="tenant"
                className="text-sm"
              />
              <Input
                value={devTokenUserId}
                onChange={(e) => setDevTokenUserId(e.target.value)}
                placeholder="user_id"
                className="text-sm"
              />
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={entrarComDevToken}
              disabled={enviando}
              className="w-full"
            >
              {enviando ? <Loader2 className="animate-spin" /> : <FlaskConical />}
              Gerar token DEV
            </Button>
          </CardContent>
        )}
      </Card>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}
