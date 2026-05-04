"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageList } from "@/components/chat/message-list";
import { ApiError, chat } from "@/lib/api";
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
    role: string;
    modulos_contratados: Record<string, boolean>;
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
      role: s.role,
      modulos_contratados: s.modulos_contratados,
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

  if (!sessaoCheck) {
    return null; // aguardando redirect ou hidratação
  }

  return (
    <AppShell
      tenantId={sessaoCheck.tenant_id}
      role={sessaoCheck.role}
      modulos={sessaoCheck.modulos_contratados}
    >
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
    </AppShell>
  );
}
