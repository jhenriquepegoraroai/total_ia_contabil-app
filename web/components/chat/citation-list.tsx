import { FileText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Citacao } from "@/lib/types";

export function CitationList({ citacoes }: { citacoes: Citacao[] }) {
  if (!citacoes || citacoes.length === 0) return null;

  return (
    <div className="mt-3 pt-3 border-t border-border/60">
      <p className="text-xs font-semibold text-muted-foreground mb-2">Fontes:</p>
      <ul className="flex flex-wrap gap-2">
        {citacoes.map((c, i) => (
          <li key={`${c.file_name}-${c.record_id ?? i}`}>
            <Badge variant="outline" className="gap-1.5 font-normal">
              <FileText className="h-3 w-3" />
              <span className="font-medium">{c.file_name}</span>
              {c.data_valida && (
                <span className="text-muted-foreground">
                  · {formatarData(c.data_valida)}
                </span>
              )}
              {typeof c.similarity === "number" && (
                <span className="text-muted-foreground">
                  · {(c.similarity * 100).toFixed(0)}%
                </span>
              )}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatarData(iso: string): string {
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  return `${d}/${m}/${y}`;
}
