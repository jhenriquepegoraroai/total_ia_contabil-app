"use client";

import {
  Banknote,
  Bot,
  FileText,
  MessageCircle,
  TrendingDown,
  type LucideProps,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ModuloCardProps {
  slug: string;
  nome_produto: string;
  tagline: string;
  descricao: string;
  icone: string;
  status: "disponivel" | "preview";
  modalidades: string[];
}

type IconComp = React.FC<LucideProps>;

const ICONE_MAP: Record<string, IconComp> = {
  "message-circle": MessageCircle,
  "file-text": FileText,
  banknote: Banknote,
  "trending-down": TrendingDown,
};

const MODALIDADE_LABEL: Record<string, string> = {
  A: "Acoplada",
  B: "Standalone",
  C: "Dados de Mercado",
};

export function ModuloCard({
  nome_produto,
  tagline,
  icone,
  status,
  modalidades,
}: ModuloCardProps) {
  const Icon: IconComp = ICONE_MAP[icone] ?? Bot;

  return (
    <Card className="flex flex-col h-full border border-border hover:shadow-md transition-shadow duration-200">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Icon className="h-6 w-6" />
          </div>
          {status === "disponivel" ? (
            <span className="text-xs font-medium px-2 py-1 rounded-full bg-green-100 text-green-800 whitespace-nowrap">
              Disponível
            </span>
          ) : (
            <span className="text-xs font-medium px-2 py-1 rounded-full bg-amber-100 text-amber-800 whitespace-nowrap">
              Preview
            </span>
          )}
        </div>
        <CardTitle className="text-lg mt-3">{nome_produto}</CardTitle>
      </CardHeader>

      <CardContent className="flex-1">
        <p className="text-sm text-muted-foreground leading-relaxed">{tagline}</p>
      </CardContent>

      <CardFooter className="pt-3 flex flex-wrap gap-1.5">
        {modalidades.map((m) => (
          <Badge
            key={m}
            variant="secondary"
            className="text-xs px-2 py-0.5 rounded-full font-normal"
          >
            {m} — {MODALIDADE_LABEL[m] ?? m}
          </Badge>
        ))}
      </CardFooter>
    </Card>
  );
}
