"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ChatInput } from "@/components/chat/chat-input";
import { MessageList } from "@/components/chat/message-list";
import { AppShell } from "@/components/layout/app-shell";
import { ApiError, chat } from "@/lib/api";
import { lerSessao } from "@/lib/auth";
import type { Message } from "@/lib/types";

type Sessao = NonNullable<ReturnType<typeof lerSessao>>;

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [pergunta, setPergunta] = useState("");
  const [referencia, setReferencia] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [sessao, setSessao] = useState<Sessao | null>(null);
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
    setSessao(s);
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

  if (!sessao) {
    return null; // aguardando redirect ou hidratação
  }

  return (
    <AppShell
      tenantId={sessao.tenant_id}
      role={sessao.role}
      modulos={sessao.modulos_contratados}
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
          referenciaTrancada={!!sessao.referencia}
        />
      </div>
    </AppShell>
  );
}
