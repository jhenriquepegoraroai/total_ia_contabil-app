"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  Loader2,
  Plus,
  Save,
  Users as UsersIcon,
  X,
} from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  tenantAtualizarUsuario,
  tenantCriarUsuario,
  tenantListarUsuarios,
} from "@/lib/api";
import { lerSessao } from "@/lib/auth";
import type { TenantUser, TenantUserRoleAtribuivel } from "@/lib/types";


type Sessao = NonNullable<ReturnType<typeof lerSessao>>;


export default function UsuariosPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [sessao, setSessao] = useState<Sessao | null>(null);
  const [usuarios, setUsuarios] = useState<TenantUser[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  useEffect(() => {
    const s = lerSessao();
    if (!s) {
      router.replace("/login");
      return;
    }
    if (s.is_superadmin || s.tenant_id === "_system") {
      router.replace("/admin");
      return;
    }
    if (s.role !== "admin") {
      router.replace("/");
      return;
    }
    setSessao(s);
  }, [router]);

  async function carregar() {
    try {
      const data = await tenantListarUsuarios();
      setUsuarios(data);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    if (!sessao) return;
    carregar();
  }, [sessao]);

  async function toggleEnabled(u: TenantUser) {
    setTogglingId(u.id);
    try {
      await tenantAtualizarUsuario(u.id, { enabled: !u.enabled });
      toast.success(`${u.nome} ${u.enabled ? "desativado" : "reativado"}.`);
      await carregar();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    } finally {
      setTogglingId(null);
    }
  }

  if (!sessao) return null;

  return (
    <AppShell
      tenantId={sessao.tenant_id}
      role={sessao.role}
      modulos={sessao.modulos_contratados}
    >
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8">
        <header className="flex items-start justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-3">
              <UsersIcon className="h-6 w-6 text-primary" />
              <h1 className="text-2xl font-bold">Usuários do tenant</h1>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              Crie e gerencie acessos para síndicos, atendentes e moradores.
            </p>
          </div>
          <Button onClick={() => setModalOpen(true)}>
            <Plus className="h-4 w-4" /> Convidar usuário
          </Button>
        </header>

        {carregando ? (
          <div className="space-y-2">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        ) : usuarios.length === 0 ? (
          <Card>
            <CardContent className="p-10 text-center text-muted-foreground">
              <UsersIcon className="h-10 w-10 mx-auto mb-3 opacity-40" />
              <p className="font-medium text-foreground">Nenhum usuário ainda</p>
              <p className="text-sm mt-1">
                Comece convidando o primeiro síndico ou atendente.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-2">
            {usuarios.map((u) => (
              <UsuarioRow
                key={u.id}
                user={u}
                onToggle={() => toggleEnabled(u)}
                toggling={togglingId === u.id}
              />
            ))}
          </div>
        )}

        {modalOpen && (
          <ConvidarUsuarioModal
            onClose={() => setModalOpen(false)}
            onCriado={(nome) => {
              setModalOpen(false);
              toast.success(`Acesso criado para ${nome}.`);
              carregar();
            }}
          />
        )}
      </main>
    </AppShell>
  );
}


function UsuarioRow({
  user,
  onToggle,
  toggling,
}: {
  user: TenantUser;
  onToggle: () => void;
  toggling: boolean;
}) {
  const isAdmin = user.role === "admin";
  return (
    <Card className={user.enabled ? "" : "opacity-60"}>
      <CardContent className="p-4 flex items-center gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium">{user.nome}</span>
            <Badge variant={isAdmin ? "default" : "secondary"} className="text-[10px]">
              {user.role}
            </Badge>
            {!user.enabled && (
              <Badge variant="outline" className="text-[10px]">
                desativado
              </Badge>
            )}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5 truncate">
            {user.email}
            {user.referencia && (
              <>
                {" · cond. "}
                <code className="font-mono">{user.referencia}</code>
              </>
            )}
          </div>
        </div>
        {!isAdmin && (
          <Button
            variant={user.enabled ? "outline" : "default"}
            size="sm"
            onClick={onToggle}
            disabled={toggling}
          >
            {toggling ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : user.enabled ? (
              "Desativar"
            ) : (
              "Reativar"
            )}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}


function ConvidarUsuarioModal({
  onClose,
  onCriado,
}: {
  onClose: () => void;
  onCriado: (nome: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [role, setRole] = useState<TenantUserRoleAtribuivel>("morador");
  const [password, setPassword] = useState("");
  const [referencia, setReferencia] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // ESC fecha
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await tenantCriarUsuario({
        email: email.trim().toLowerCase(),
        nome: nome.trim(),
        role,
        password,
        referencia: referencia.trim() || null,
      });
      onCriado(nome.trim());
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/50"
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg bg-card border shadow-xl"
      >
        <header className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold">Convidar novo usuário</h2>
          <Button variant="ghost" size="icon" onClick={onClose} title="Fechar">
            <X />
          </Button>
        </header>

        <form onSubmit={onSubmit} className="p-4 space-y-3">
          <Field label="E-mail">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="usuario@cliente.com.br"
              required
              autoFocus
            />
          </Field>
          <Field label="Nome">
            <Input
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Nome completo"
              required
              minLength={2}
            />
          </Field>
          <Field label="Papel">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as TenantUserRoleAtribuivel)}
              className="w-full h-9 rounded-md border bg-background px-3 text-sm"
            >
              <option value="morador">Morador</option>
              <option value="sindico">Síndico</option>
              <option value="atendente">Atendente</option>
            </select>
          </Field>
          <Field label="Senha inicial" hint="Mínimo 8 caracteres. O usuário pode trocar depois.">
            <Input
              type="text"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              maxLength={128}
              required
              autoComplete="new-password"
              placeholder="ex: trocaragora123"
            />
          </Field>
          <Field label="Condomínio (opcional)" hint="Referência do cond. default desse usuário">
            <Input
              value={referencia}
              onChange={(e) => setReferencia(e.target.value)}
              placeholder="ex: 12345"
            />
          </Field>

          {erro && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {erro}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={enviando}>
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando}>
              {enviando ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Criando...
                </>
              ) : (
                <>
                  <Save className="h-3.5 w-3.5" /> Criar acesso
                </>
              )}
            </Button>
          </div>
          <p className="text-[11px] text-muted-foreground pt-1 inline-flex items-start gap-1">
            <CheckCircle2 className="h-3 w-3 mt-0.5 text-green-700 shrink-0" />
            <span>
              O usuário poderá entrar imediatamente em{" "}
              <code className="font-mono">/login</code> com este e-mail e senha.
            </span>
          </p>
        </form>
      </div>
    </>
  );
}


function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
