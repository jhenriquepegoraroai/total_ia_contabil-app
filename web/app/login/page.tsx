"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect, Suspense } from "react";
import { LogIn, Loader2, FlaskConical } from "lucide-react";

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
import { PasswordInput } from "@/components/ui/password-input";
import { ApiError, devLogin, health, login } from "@/lib/api";
import { LelloLogo } from "@/components/lello-logo";


function LoginInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next");

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
        if (h.tenants_enabled.length) {
          setDevTokenTenant(h.tenants_enabled[0]);
        }
      })
      .catch(() => setTenantsDisponiveis([]));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      // Email é único globalmente — backend resolve tenant + is_superadmin
      // a partir da combinação email+senha.
      const resp = await login({ email: email.trim(), password });

      if (resp.is_superadmin) {
        router.push(next && next.startsWith("/admin") ? next : "/admin");
      } else {
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
              Entre com seu email e senha.
            </CardDescription>
          </div>
        </CardHeader>

        <form onSubmit={onSubmit}>
          <CardContent className="space-y-4">
            <div className="space-y-1">
              <label htmlFor="email" className="text-sm font-medium">
                E-mail
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="seu@email.com"
                required
                autoFocus
                autoComplete="email"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="password" className="text-sm font-medium">
                Senha
              </label>
              <PasswordInput
                id="password"
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
              404 e o link some na prática (devLogin levanta ApiError).
            */}
            <button
              type="button"
              onClick={() => setMostrarDevToken((m) => !m)}
              className="text-xs text-muted-foreground/80 hover:text-foreground inline-flex items-center gap-1"
            >
              <FlaskConical className="h-3 w-3" />
              {mostrarDevToken ? "Esconder" : "Ou usar token rápido (DEV)"}
            </button>
          </CardFooter>
        </form>

        {mostrarDevToken && (
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
                list="tenants-disponiveis"
              />
              <datalist id="tenants-disponiveis">
                {tenantsDisponiveis.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
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
