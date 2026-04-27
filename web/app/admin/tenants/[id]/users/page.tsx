"use client";

import { use, useEffect, useState } from "react";
import {
  CheckCircle2,
  CircleSlash,
  KeyRound,
  Loader2,
  Plus,
  ShieldCheck,
  Trash2,
  Users as UsersIcon,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ApiError,
  adminAtualizarUsuario,
  adminCriarUsuario,
  adminDeletarUsuario,
  adminListarUsuarios,
  adminResetarSenha,
} from "@/lib/api";
import type { TenantUser, UserRole } from "@/lib/types";


const ROLES: { value: UserRole; label: string }[] = [
  { value: "morador", label: "Morador" },
  { value: "sindico", label: "Síndico" },
  { value: "atendente", label: "Atendente" },
  { value: "admin", label: "Admin" },
];

const ROLE_LABEL: Record<UserRole, string> = Object.fromEntries(
  ROLES.map((r) => [r.value, r.label])
) as Record<UserRole, string>;


export default function UsersPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: tenantId } = use(params);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [criando, setCriando] = useState(false);

  async function carregar() {
    try {
      const data = await adminListarUsuarios(tenantId);
      setUsers(data);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregar();
  }, [tenantId]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <UsersIcon className="h-5 w-5 text-primary" /> Usuários
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Quem pode acessar o assistente em nome desta administradora. O login
            é por e-mail + senha. Superadmins não aparecem aqui — são gerenciados
            via CLI.
          </p>
        </div>
        <Button onClick={() => setCriando(true)} disabled={criando}>
          <Plus className="h-4 w-4" /> Novo usuário
        </Button>
      </div>

      {erro && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      )}

      {criando && (
        <NovoUsuarioForm
          tenantId={tenantId}
          onCancel={() => setCriando(false)}
          onCreated={() => {
            setCriando(false);
            carregar();
          }}
        />
      )}

      {carregando ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : users.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-muted-foreground">
            <UsersIcon className="h-10 w-10 mx-auto mb-3 opacity-40" />
            <p className="font-medium text-foreground">Nenhum usuário cadastrado</p>
            <p className="text-sm mt-1">
              Crie o primeiro pra que síndicos ou moradores possam logar.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <ul className="divide-y">
              {users.map((u) => (
                <UserRow key={u.id} tenantId={tenantId} user={u} onChanged={carregar} />
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}


function NovoUsuarioForm({
  tenantId,
  onCancel,
  onCreated,
}: {
  tenantId: string;
  onCancel: () => void;
  onCreated: () => void;
}) {
  const [email, setEmail] = useState("");
  const [nome, setNome] = useState("");
  const [role, setRole] = useState<UserRole>("morador");
  const [password, setPassword] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await adminCriarUsuario(tenantId, {
        email: email.trim().toLowerCase(),
        nome: nome.trim(),
        role,
        password,
      });
      onCreated();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Card className="border-primary/30">
      <CardContent className="p-5">
        <form onSubmit={onSubmit} className="space-y-3">
          <h3 className="font-medium text-sm">Novo usuário</h3>
          <div className="grid sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium">E-mail</label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="usuario@empresa.com.br"
                required
                autoFocus
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Nome</label>
              <Input
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                placeholder="João da Silva"
                required
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Papel</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                {ROLES.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Senha (mín. 8)</label>
              <PasswordInput
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
                autoComplete="new-password"
              />
            </div>
          </div>

          {erro && (
            <p className="text-sm text-destructive">{erro}</p>
          )}

          <div className="flex gap-2 justify-end pt-2">
            <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={enviando}>
              Cancelar
            </Button>
            <Button type="submit" size="sm" disabled={enviando}>
              {enviando ? <Loader2 className="animate-spin" /> : <Plus />}
              Criar
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}


function UserRow({
  tenantId,
  user,
  onChanged,
}: {
  tenantId: string;
  user: TenantUser;
  onChanged: () => void;
}) {
  const [resetando, setResetando] = useState(false);
  const [novaSenha, setNovaSenha] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function toggle() {
    setBusy(true);
    setErro(null);
    try {
      await adminAtualizarUsuario(tenantId, user.id, { enabled: !user.enabled });
      onChanged();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function deletar() {
    if (!confirm(`Remover usuário "${user.email}"? Esta ação não pode ser desfeita.`)) return;
    setBusy(true);
    setErro(null);
    try {
      await adminDeletarUsuario(tenantId, user.id);
      onChanged();
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
      setBusy(false);
    }
  }

  async function confirmarReset() {
    if (novaSenha.length < 8) {
      setErro("Senha precisa ter pelo menos 8 caracteres.");
      return;
    }
    setBusy(true);
    setErro(null);
    try {
      await adminResetarSenha(tenantId, user.id, novaSenha);
      setNovaSenha("");
      setResetando(false);
      setFeedback("Senha alterada");
      setTimeout(() => setFeedback(null), 4000);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="px-4 py-3 text-sm">
      <div className="flex items-start gap-3">
        <div className="h-9 w-9 rounded-full bg-secondary text-secondary-foreground grid place-items-center font-semibold text-xs shrink-0">
          {(user.nome || user.email).slice(0, 2).toUpperCase()}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-medium truncate">{user.nome}</span>
            <span className="text-xs text-muted-foreground truncate">{user.email}</span>
            {user.is_superadmin && (
              <Badge variant="default" className="text-[9px] py-0 gap-1">
                <ShieldCheck className="h-2.5 w-2.5" /> superadmin
              </Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground mt-0.5">
            <span>{ROLE_LABEL[user.role] || user.role}</span>
            <span>·</span>
            {user.enabled ? (
              <span className="text-green-700 inline-flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3" /> ativo
              </span>
            ) : (
              <span className="inline-flex items-center gap-1">
                <CircleSlash className="h-3 w-3" /> desativado
              </span>
            )}
            {!user.tem_senha && (
              <>
                <span>·</span>
                <span className="text-amber-700">sem senha definida</span>
              </>
            )}
          </div>
        </div>

        {!user.is_superadmin && (
          <div className="flex items-center gap-1 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setResetando((r) => !r)}
              disabled={busy}
              title="Resetar senha"
            >
              <KeyRound className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Senha</span>
            </Button>
            <Button
              variant={user.enabled ? "ghost" : "default"}
              size="sm"
              onClick={toggle}
              disabled={busy}
            >
              {user.enabled ? "Desativar" : "Ativar"}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={deletar}
              disabled={busy}
              title="Remover"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            </Button>
          </div>
        )}
      </div>

      {feedback && (
        <p className="text-xs text-green-700 mt-2 ml-12">✓ {feedback}</p>
      )}

      {resetando && (
        <div className="mt-3 ml-12 flex items-center gap-2">
          <PasswordInput
            value={novaSenha}
            onChange={(e) => setNovaSenha(e.target.value)}
            placeholder="nova senha (mín. 8)"
            className="max-w-xs"
            autoFocus
            minLength={8}
          />
          <Button size="sm" onClick={confirmarReset} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : null}
            Confirmar
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setResetando(false);
              setNovaSenha("");
              setErro(null);
            }}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {erro && (
        <p className="text-xs text-destructive mt-2 ml-12">{erro}</p>
      )}
    </li>
  );
}
