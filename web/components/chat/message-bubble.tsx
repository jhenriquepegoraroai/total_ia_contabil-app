import { Building2, AlertCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Message } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { CitationList } from "./citation-list";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <Avatar role={message.role} />
      <div
        className={cn(
          "max-w-[85%] rounded-lg px-4 py-3 text-sm shadow-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : message.error
              ? "bg-destructive/10 border border-destructive/30 text-foreground"
              : "bg-card border border-border text-card-foreground"
        )}
      >
        {message.pending ? (
          <div className="space-y-2 min-w-[200px]">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
            <Skeleton className="h-3 w-3/5" />
          </div>
        ) : (
          <>
            <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
            {!isUser && message.citacoes && (
              <CitationList citacoes={message.citacoes} />
            )}
            {!isUser && (message.via || message.duracao_ms) && (
              <div className="mt-2 pt-2 border-t border-border/60 flex flex-wrap gap-x-3 text-[10px] uppercase tracking-wider text-muted-foreground">
                {message.via && <span>via {message.via}</span>}
                {typeof message.categoria === "number" && (
                  <span>cat {message.categoria}</span>
                )}
                {typeof message.duracao_ms === "number" && (
                  <span>{message.duracao_ms} ms</span>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Avatar({ role }: { role: Message["role"] }) {
  if (role === "user") {
    return (
      <div className="h-8 w-8 rounded-full bg-secondary text-secondary-foreground grid place-items-center text-xs font-semibold shrink-0">
        Você
      </div>
    );
  }
  return (
    <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground grid place-items-center shrink-0">
      <Building2 className="h-4 w-4" />
    </div>
  );
}

export function MessageError({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
      <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
      <p>{children}</p>
    </div>
  );
}
