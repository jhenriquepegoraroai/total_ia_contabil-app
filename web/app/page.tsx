"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageList } from "@/components/chat/message-list";
import { LelloLogo } from "@/components/lello-logo";
import { ApiError, chat, logout as logoutApi } from "@/lib/api";
import { lerSessao } from "@/lib/auth";
import type { Message } from "@/lib/types";

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [pergunta, setPergunta] = useState("");
  const [referencia, setReferencia] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [sessaoCheck, setSessaoCheck] = useState<{
    tenant_id: string;
    user_id: string;
    referencia: string | null;
  } | null>(null);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);

  useEffect(() => {
    const s = lerSessao();
    if (!s) {
      router.replace("/login");
      return;
    }
    // Superadmin não tem tenant real — `_system` é reservado e não pode
    // chatar. Redireciona pra /admin (área dele).
    if (s.is_superadmin || s.tenant_id === "_system") {
      router.replace("/admin");
      return;
    }
    setSessaoCheck({
      tenant_id: s.tenant_id,
      user_id: s.user_id,
      referencia: s.referencia,
    });
    // Se o cadastro do usuário já tem condomínio, pré-preenche o campo.
    if (s.referencia) {
      setReferencia(s.referencia);
    }
  }, [router]);

  async function enviar() {
    const perguntaTrim = pergunta.trim();
    const refTrim = referencia.trim();
    if (!perguntaTrim || !refTrim || enviando) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: perguntaTrim,
    };
    const pendingMsg: Message = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      pending: true,
    };

    setMessages((prev) => [...prev, userMsg, pendingMsg]);
    setPergunta("");
    setEnviando(true);

    try {
      const resp = await chat({
        pergunta: perguntaTrim,
        referencia: refTrim,
        session_id: sessionId,
      });

      setSessionId(resp.session_id);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingMsg.id
            ? {
                ...m,
                content: resp.resposta,
                citacoes: resp.citacoes,
                categoria: resp.categoria,
                via: resp.via,
                trace_id: resp.trace_id,
                duracao_ms: resp.duracao_ms,
                pending: false,
              }
            : m
        )
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      const msg = err instanceof Error ? err.message : String(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingMsg.id
            ? { ...m, content: `Erro: ${msg}`, pending: false, error: true }
            : m
        )
      );
    } finally {
      setEnviando(false);
    }
  }

  async function logout() {
    await logoutApi();
    router.replace("/login");
  }

  if (!sessaoCheck) {
    return null; // aguardando redirect ou hidratação
  }

  return (
    <main className="min-h-screen flex flex-col bg-background">
      <header className="border-b bg-card/50 backdrop-blur supports-[backdrop-filter]:bg-card/50 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <LelloLogo className="h-7" />
          <div className="flex items-center gap-3 text-sm">
            <div className="text-right hidden sm:block">
              <div className="text-xs text-muted-foreground">Administradora</div>
              <div className="font-medium">{sessaoCheck.tenant_id}</div>
            </div>
            <Button variant="ghost" size="icon" onClick={logout} title="Sair">
              <LogOut />
            </Button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col max-w-5xl w-full mx-auto">
        <MessageList messages={messages} />
      </div>

      <div className="sticky bottom-0">
        <ChatInput
          pergunta={pergunta}
          setPergunta={setPergunta}
          referencia={referencia}
          setReferencia={setReferencia}
          enviando={enviando}
          onSubmit={enviar}
          referenciaTrancada={!!sessaoCheck.referencia}
        />
      </div>
    </main>
  );
}
