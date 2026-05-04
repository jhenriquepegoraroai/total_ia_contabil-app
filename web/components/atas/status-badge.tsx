"use client";

/**
 * Badge de status da ata — cor + label legível por status da máquina.
 * Cores derivadas da paleta do tema (primary/secondary/muted).
 */

import { Badge } from "@/components/ui/badge";
import type { AtaStatus } from "@/lib/types";


const LABELS: Record<AtaStatus, { label: string; tone: "default" | "secondary" | "outline" | "destructive" }> = {
  rascunho: { label: "Rascunho", tone: "outline" },
  aguardando_transcricao: { label: "Transcrevendo áudio", tone: "secondary" },
  aguardando_geracao: { label: "Gerando ata", tone: "secondary" },
  gerada: { label: "Gerada — pronta pra revisão", tone: "default" },
  revisao_consultor: { label: "Em revisão (consultor)", tone: "default" },
  aguardando_sindico: { label: "Aguardando síndico", tone: "secondary" },
  revisao_sindico: { label: "Em revisão (síndico)", tone: "secondary" },
  comparando: { label: "Comparando alterações", tone: "secondary" },
  revisao_consultor_diff: { label: "Aguardando aprovação do diff", tone: "default" },
  aguardando_presidente: { label: "Aguardando presidente", tone: "secondary" },
  revisao_presidente: { label: "Em revisão (presidente)", tone: "secondary" },
  revisao_consultor_final: { label: "Revisão final do consultor", tone: "default" },
  corrigindo: { label: "Corrigindo ortografia", tone: "secondary" },
  registrada: { label: "Registrada", tone: "default" },
  arquivada: { label: "Arquivada", tone: "outline" },
  falhou: { label: "Falhou", tone: "destructive" },
};


export function AtaStatusBadge({ status }: { status: AtaStatus }) {
  const cfg = LABELS[status] ?? { label: status, tone: "outline" as const };
  return <Badge variant={cfg.tone}>{cfg.label}</Badge>;
}
