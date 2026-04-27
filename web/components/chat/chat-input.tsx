"use client";

import { Send, Loader2 } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface ChatInputProps {
  pergunta: string;
  setPergunta: (v: string) => void;
  referencia: string;
  setReferencia: (v: string) => void;
  enviando: boolean;
  onSubmit: () => void;
  desabilitado?: boolean;
}

export function ChatInput({
  pergunta,
  setPergunta,
  referencia,
  setReferencia,
  enviando,
  onSubmit,
  desabilitado,
}: ChatInputProps) {
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    // Ctrl/Cmd+Enter envia; Enter sozinho quebra linha (textarea normal)
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      onSubmit();
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit();
  }

  const podeEnviar = !enviando && !desabilitado && pergunta.trim() && referencia.trim();

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t bg-card/50 backdrop-blur supports-[backdrop-filter]:bg-card/50 p-4 space-y-3"
    >
      <div className="flex items-center gap-2 max-w-3xl mx-auto">
        <label htmlFor="ref" className="text-xs font-medium text-muted-foreground shrink-0">
          Condomínio:
        </label>
        <Input
          id="ref"
          value={referencia}
          onChange={(e) => setReferencia(e.target.value)}
          placeholder="ex: 12345"
          className="h-7 text-xs max-w-[120px]"
          disabled={enviando}
        />
        <span className="text-[10px] text-muted-foreground/70 ml-auto">
          Ctrl/⌘ + Enter para enviar
        </span>
      </div>

      <div className="flex gap-2 max-w-3xl mx-auto">
        <Textarea
          value={pergunta}
          onChange={(e) => setPergunta(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Faça uma pergunta sobre o seu condomínio..."
          className="resize-none min-h-[60px] max-h-[200px]"
          disabled={enviando}
          rows={2}
        />
        <Button type="submit" disabled={!podeEnviar} className="self-end" size="icon">
          {enviando ? <Loader2 className="animate-spin" /> : <Send />}
        </Button>
      </div>
    </form>
  );
}
