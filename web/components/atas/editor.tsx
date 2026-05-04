"use client";

/**
 * Editor de texto rico do Bella Atas.
 *
 * Implementação escolhida: `contentEditable` nativo + toolbar com
 * `document.execCommand`. Motivo:
 *
 *   - Preserva 100% do HTML produzido pelo LLM (spans com inline styles
 *     coloridos, placeholders verde, tabelas) sem precisar de extensões
 *     customizadas.
 *   - Zero dependências novas (TipTap precisaria 4-5 pacotes).
 *   - Suficiente pra MVP — síndico/presidente fazem ajustes pequenos.
 *
 * `execCommand` está formalmente deprecado mas ainda funciona em todos
 * os browsers atuais. Caso vire problema (ex: Firefox parar de suportar),
 * trocar por TipTap ou Lexical.
 */

import { Bold, Italic, List, ListOrdered, Underline as UnderlineIcon } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";


interface AtaEditorProps {
  /** HTML inicial. Setado quando o componente monta. */
  conteudoInicial: string;
  /** Disparado a cada edição (após oninput). HTML completo do editor. */
  onChange: (html: string) => void;
  /** Modo somente-leitura (visualização sem edição). */
  readOnly?: boolean;
  /** Altura mínima da área editável. Default 400px. */
  minHeight?: number;
}


export function AtaEditor({
  conteudoInicial,
  onChange,
  readOnly = false,
  minHeight = 400,
}: AtaEditorProps) {
  const ref = useRef<HTMLDivElement>(null);
  const ultimoHtmlRef = useRef<string>("");

  // Inicializa o conteúdo na montagem (e quando conteudoInicial muda
  // externamente — ex: após carregar versão diferente).
  useEffect(() => {
    if (!ref.current) return;
    if (ref.current.innerHTML === conteudoInicial) return;
    ref.current.innerHTML = conteudoInicial;
    ultimoHtmlRef.current = conteudoInicial;
  }, [conteudoInicial]);

  function handleInput() {
    if (!ref.current) return;
    const html = ref.current.innerHTML;
    if (html !== ultimoHtmlRef.current) {
      ultimoHtmlRef.current = html;
      onChange(html);
    }
  }

  function exec(cmd: string, value?: string) {
    if (readOnly) return;
    document.execCommand(cmd, false, value);
    handleInput();
    ref.current?.focus();
  }

  return (
    <div className="border rounded-md bg-background overflow-hidden">
      {!readOnly && (
        <div className="flex items-center gap-1 border-b px-2 py-1 bg-muted/40">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => exec("bold")}
            title="Negrito (Ctrl+B)"
            className="h-8 w-8 p-0"
          >
            <Bold className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => exec("italic")}
            title="Itálico (Ctrl+I)"
            className="h-8 w-8 p-0"
          >
            <Italic className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => exec("underline")}
            title="Sublinhado (Ctrl+U)"
            className="h-8 w-8 p-0"
          >
            <UnderlineIcon className="h-4 w-4" />
          </Button>
          <div className="w-px h-5 bg-border mx-1" />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => exec("insertUnorderedList")}
            title="Lista"
            className="h-8 w-8 p-0"
          >
            <List className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => exec("insertOrderedList")}
            title="Lista numerada"
            className="h-8 w-8 p-0"
          >
            <ListOrdered className="h-4 w-4" />
          </Button>
        </div>
      )}
      <div
        ref={ref}
        contentEditable={!readOnly}
        suppressContentEditableWarning
        onInput={handleInput}
        onBlur={handleInput}
        spellCheck
        className="prose prose-sm max-w-none p-4 focus:outline-none [&_table]:border-collapse [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:px-2 [&_th]:py-1 [&_th]:bg-muted/50 [&_p]:my-2"
        style={{ minHeight: `${minHeight}px` }}
      />
    </div>
  );
}


/**
 * Visualização read-only de uma versão da ata (ou diff). Não tem toolbar,
 * não permite edição. Aceita o mesmo HTML.
 */
export function AtaViewer({
  conteudoHtml,
  minHeight = 400,
}: {
  conteudoHtml: string;
  minHeight?: number;
}) {
  return (
    <div
      className="border rounded-md bg-background prose prose-sm max-w-none p-4 [&_table]:border-collapse [&_td]:border [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:px-2 [&_th]:py-1 [&_th]:bg-muted/50 [&_p]:my-2"
      style={{ minHeight: `${minHeight}px` }}
      dangerouslySetInnerHTML={{ __html: conteudoHtml }}
    />
  );
}
