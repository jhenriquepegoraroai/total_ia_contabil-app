"use client";

import { useEffect, useRef } from "react";
import { Building2 } from "lucide-react";

import type { Message } from "@/lib/types";
import { MessageBubble } from "./message-bubble";

export function MessageList({ messages }: { messages: Message[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return <EmptyState />;
  }

  return (
    <div ref={ref} className="flex-1 overflow-y-auto p-4">
      <div className="max-w-3xl mx-auto space-y-4">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex-1 grid place-items-center p-8">
      <div className="text-center max-w-md">
        <div className="inline-flex h-14 w-14 rounded-full bg-primary/10 text-primary items-center justify-center mb-4">
          <Building2 className="h-7 w-7" />
        </div>
        <h2 className="text-xl font-bold mb-2">Como posso ajudar?</h2>
        <p className="text-sm text-muted-foreground mb-6">
          Pergunte sobre regras do seu condomínio, atas de assembleia, áreas comuns,
          editais de convocação ou dados cadastrais.
        </p>
        <div className="grid gap-2 text-sm text-left">
          {SUGESTOES.map((s) => (
            <div
              key={s}
              className="rounded-lg border bg-card px-3 py-2 text-muted-foreground italic"
            >
              &ldquo;{s}&rdquo;
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const SUGESTOES = [
  "Qual o horário de funcionamento do salão de festas?",
  "Quem é o síndico atual do condomínio?",
  "Posso ter cachorro no apartamento?",
  "Quando foi a última assembleia?",
];
