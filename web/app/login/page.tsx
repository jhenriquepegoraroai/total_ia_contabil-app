"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { LogIn, Loader2 } from "lucide-react";

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
import { ApiError, devLogin, health } from "@/lib/api";
import { LelloLogo } from "@/components/lello-logo";

export default function LoginPage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState("lello");
  const [userId, setUserId] = useState("dev_user");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [tenantsDisponiveis, setTenantsDisponiveis] = useState<string[]>([]);

  useEffect(() => {
    health()
      .then((h) => setTenantsDisponiveis(h.tenants_enabled))
      .catch(() => setTenantsDisponiveis([]));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await devLogin({ tenant_id: tenantId.trim(), user_id: userId.trim(), role: "admin" });
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setErro(`${err.status}: ${err.message}`);
      } else {
        setErro(String(err));
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-accent/30 px-4">
      <Card className="w-full max-w-md">
        <CardHeader className="items-center text-center space-y-4">
          <LelloLogo className="h-10" />
          <div>
            <CardTitle className="text-2xl">Assistente Virtual de Condomínios</CardTitle>
            <CardDescription className="mt-2">
              Entre para tirar dúvidas sobre o seu condomínio.
            </CardDescription>
          </div>
        </CardHeader>
        <form onSubmit={onSubmit}>
          <CardContent className="space-y-4">
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
                autoFocus
              />
              {tenantsDisponiveis.length > 0 && (
                <p className="text-xs text-muted-foreground pt-1">
                  Disponíveis: {tenantsDisponiveis.join(", ")}
                </p>
              )}
            </div>

            <div className="space-y-1">
              <label htmlFor="user" className="text-sm font-medium">
                Usuário
              </label>
              <Input
                id="user"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="dev_user"
                required
              />
            </div>

            {erro && (
              <div className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
                {erro}
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Modo de desenvolvimento — autenticação simplificada via{" "}
              <code className="font-mono">/auth/dev-token</code>. Em produção, o login
              será com email e senha.
            </p>
          </CardContent>
          <CardFooter>
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
          </CardFooter>
        </form>
      </Card>
    </main>
  );
}
