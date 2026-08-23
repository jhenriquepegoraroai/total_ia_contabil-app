"use client";

import {
  Activity,
  Banknote,
  Bot,
  FileText,
  MessageCircle,
  ShieldAlert,
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
  status: StatusProduto;
  modalidades: string[];
  fatoOperacional?: string;
}

export type StatusProduto = "em_implantacao" | "em_operacao_lello" | "roadmap";

/**
 * Um selo por estado. "Em operação na Lello" é um selo mais forte que
 * "Construído", não mais fraco: diz que o modelo já roda, só não está
 * exposto aqui. Colapsar os dois em "Em breve" achatava ativo em produção
 * no mesmo nível de item de roadmap.
 */
const SELO: Record<StatusProduto, { texto: string; classe: string }> = {
  em_implantacao: {
    texto: "Construído — em implantação",
    classe: "bg-green-100 text-green-800",
  },
  em_operacao_lello: {
    texto: "Em operação na Lello",
    classe: "bg-emerald-100 text-emerald-800",
  },
  roadmap: {
    texto: "Roadmap",
    classe: "bg-gray-100 text-gray-700",
  },
};

type IconComp = React.FC<LucideProps>;

const ICONE_MAP: Record<string, IconComp> = {
  "message-circle": MessageCircle,
  "file-text": FileText,
  banknote: Banknote,
  "trending-down": TrendingDown,
  "shield-alert": ShieldAlert,
  activity: Activity,
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
  fatoOperacional,
}: ModuloCardProps) {
  const Icon: IconComp = ICONE_MAP[icone] ?? Bot;
  const selo = SELO[status];

  return (
    <Card className="flex flex-col h-full border border-border hover:shadow-md transition-shadow duration-200">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Icon className="h-6 w-6" />
          </div>
          <span
            className={`text-xs font-medium px-2 py-1 rounded-full whitespace-nowrap ${selo.classe}`}
          >
            {selo.texto}
          </span>
        </div>
        <CardTitle className="text-lg mt-3">{nome_produto}</CardTitle>
      </CardHeader>

      <CardContent className="flex-1 space-y-2">
        <p className="text-sm text-muted-foreground leading-relaxed">{tagline}</p>
        {fatoOperacional && (
          <p className="text-xs text-muted-foreground/80">{fatoOperacional}</p>
        )}
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
