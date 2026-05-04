"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Loader2, Plus } from "lucide-react";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError, atasCriar } from "@/lib/api";
import { lerSessao } from "@/lib/auth";


type Sessao = NonNullable<ReturnType<typeof lerSessao>>;


/**
 * Form de criação de ata. Apenas título + condomínio (referência).
 *
 * Síndico e presidente são opcionais e podem ser atribuídos depois (na
 * tela de detalhe — ainda não implementado nesta fase). Por ora a ata
 * nasce sem atores externos e o consultor pode disparar o gerador
 * direto, ir pro corretor sem passar pelo síndico/presidente, etc.
 */
export default function NovaAtaPage() {
  const router = useRouter();
  const [sessao, setSessao] = useState<Sessao | null>(null);
  const [titulo, setTitulo] = useState("");
  const [referencia, setReferencia] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

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
    if (!s.modulos_contratados.atas) {
      router.replace("/");
      return;
    }
    setSessao(s);
  }, [router]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!titulo.trim()) return;
    setErro(null);
    setEnviando(true);
    try {
      const ata = await atasCriar({
        titulo: titulo.trim(),
        referencia: referencia.trim() || null,
      });
      router.replace(`/atas/${ata.id}`);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
      setEnviando(false);
    }
  }

  if (!sessao) return null;

  return (
    <AppShell tenantId={sessao.tenant_id} role={sessao.role} modulos={sessao.modulos_contratados}>
    <main className="flex-1 max-w-2xl w-full mx-auto px-4 py-8">
      <Button asChild variant="ghost" size="sm" className="mb-4">
        <Link href="/atas">
          <ArrowLeft className="h-4 w-4" /> Voltar
        </Link>
      </Button>

      <h1 className="text-2xl font-bold mb-6">Nova ata</h1>

      <Card>
        <CardContent className="p-6">
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-1">
              <label htmlFor="titulo" className="text-sm font-medium">
                Título da assembleia
              </label>
              <Input
                id="titulo"
                value={titulo}
                onChange={(e) => setTitulo(e.target.value)}
                placeholder="Ex: AGO de 22/06/2026 — Edifício Carima"
                required
                autoFocus
                maxLength={200}
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="referencia" className="text-sm font-medium">
                Condomínio (referência)
              </label>
              <Input
                id="referencia"
                value={referencia}
                onChange={(e) => setReferencia(e.target.value)}
                placeholder="Opcional — ex: 10458"
              />
              <p className="text-xs text-muted-foreground">
                Se preencher, vai aparecer junto com o título na listagem e
                ajuda a buscar.
              </p>
            </div>

            {erro && (
              <div className="rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
                {erro}
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button asChild variant="outline" type="button">
                <Link href="/atas">Cancelar</Link>
              </Button>
              <Button type="submit" disabled={enviando || !titulo.trim()}>
                {enviando ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Criar
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </main>
    </AppShell>
  );
}
