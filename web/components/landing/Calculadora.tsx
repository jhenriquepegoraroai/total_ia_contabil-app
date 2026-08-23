"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/* -------------------------------------------------------------------------- */
/* Módulos disponíveis para seleção                                             */
/* -------------------------------------------------------------------------- */
const MODULOS_OPCOES = [
  { slug: "chat",      label: "Agente Conversacional", precoPct: 0.05 },
  { slug: "atas",      label: "Agente de Atas",        precoPct: 0.04 },
  { slug: "cobrancas", label: "Agente Financeiro",     precoPct: 0.04 },
  { slug: "churn",     label: "Agente de Churn",       precoPct: 0.03 },
];

/* -------------------------------------------------------------------------- */
/* Helpers de formatação                                                        */
/* -------------------------------------------------------------------------- */
function formatBRL(valor: number): string {
  return valor.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

function formatNum(valor: number): string {
  return valor.toLocaleString("pt-BR");
}

/* -------------------------------------------------------------------------- */
/* Componente de slider com label                                               */
/* -------------------------------------------------------------------------- */
function SliderField({
  label,
  value,
  min,
  max,
  step,
  onChange,
  displayValue,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  displayValue: string;
}) {
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-baseline">
        <label className="text-sm font-medium text-foreground">{label}</label>
        <span className="text-lg font-bold text-primary">{displayValue}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 rounded-full appearance-none cursor-pointer"
        style={{
          background: `linear-gradient(to right, hsl(var(--primary)) ${pct}%, hsl(var(--muted)) ${pct}%)`,
        }}
      />
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{min.toLocaleString("pt-BR")}</span>
        <span>{max.toLocaleString("pt-BR")}</span>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Card de resultado                                                            */
/* -------------------------------------------------------------------------- */
function ResultCard({
  label,
  valor,
  destaque = false,
  sub,
}: {
  label: string;
  valor: string;
  destaque?: boolean;
  sub?: string;
}) {
  return (
    <div
      className={`rounded-xl p-5 flex flex-col gap-1 ${
        destaque
          ? "bg-primary text-primary-foreground"
          : "bg-muted text-foreground"
      }`}
    >
      <p className={`text-xs font-semibold uppercase tracking-wider ${destaque ? "opacity-75" : "text-muted-foreground"}`}>
        {label}
      </p>
      <p className={`text-2xl font-extrabold ${destaque ? "" : "text-primary"}`}>
        {valor}
      </p>
      {sub && (
        <p className={`text-xs ${destaque ? "opacity-70" : "text-muted-foreground"}`}>
          {sub}
        </p>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Calculadora principal                                                        */
/* -------------------------------------------------------------------------- */
export function Calculadora() {
  const [condominios, setCondominios] = useState(200);
  const [ticket, setTicket] = useState(150);
  // Premissa de economia operacional. É editável de propósito: era uma
  // constante escondida no cálculo, e premissa que o leitor não consegue
  // mexer não é estimativa, é afirmação.
  const [horasPorCondominio, setHorasPorCondominio] = useState(2);
  const [modulosSelecionados, setModulosSelecionados] = useState<Set<string>>(
    new Set(["chat", "atas"])
  );

  function toggleModulo(slug: string) {
    setModulosSelecionados((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) {
        if (next.size > 1) next.delete(slug); // pelo menos 1 sempre selecionado
      } else {
        next.add(slug);
      }
      return next;
    });
  }

  const resultado = useMemo(() => {
    const receitaMensal = condominios * ticket;

    // Custo de IA = soma dos % dos módulos selecionados aplicado sobre receita
    const custoPct = MODULOS_OPCOES.filter((m) => modulosSelecionados.has(m.slug))
      .reduce((acc, m) => acc + m.precoPct, 0);
    const custoIA = receitaMensal * custoPct;

    const margemBruta = receitaMensal - custoIA;
    const margemPct = receitaMensal > 0 ? (margemBruta / receitaMensal) * 100 : 0;

    // Horas salvas por mês, a partir da premissa editável acima.
    const horasSalvas = condominios * horasPorCondominio * modulosSelecionados.size;

    // NOTA: aqui existia um "payback em meses" calculado como
    // `ceil((custoIA * 3) / custoIA)` — o custoIA cancela e o resultado era
    // sempre 3, qualquer que fosse o input. Foi removido em vez de corrigido:
    // payback honesto exige investimento inicial e custo evitado, que não
    // temos. Métrica vazia numa tela que o cliente mexe ao vivo custa a
    // credibilidade do resto.

    return {
      receitaMensal,
      custoIA,
      margemBruta,
      margemPct,
      horasSalvas,
    };
  }, [condominios, ticket, horasPorCondominio, modulosSelecionados]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-start">
      {/* ---- INPUTS ---- */}
      <Card className="border border-border shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Configure sua operação</CardTitle>
        </CardHeader>
        <CardContent className="space-y-8 pt-4">
          <SliderField
            label="Condomínios na carteira"
            value={condominios}
            min={10}
            max={2000}
            step={10}
            onChange={setCondominios}
            displayValue={formatNum(condominios)}
          />

          <SliderField
            label="Ticket médio mensal por condomínio"
            value={ticket}
            min={50}
            max={500}
            step={10}
            onChange={setTicket}
            displayValue={formatBRL(ticket)}
          />

          <div className="space-y-1">
            <SliderField
              label="Horas/mês economizadas por condomínio, por módulo"
              value={horasPorCondominio}
              min={0.5}
              max={8}
              step={0.5}
              onChange={setHorasPorCondominio}
              displayValue={`${horasPorCondominio.toLocaleString("pt-BR")} h`}
            />
            <p className="text-xs text-muted-foreground">
              Premissa de economia operacional — ajuste conforme a realidade da
              sua operação. Não é medição; é a estimativa que entra na conta.
            </p>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-medium">Módulos contratados</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {MODULOS_OPCOES.map((m) => {
                const ativo = modulosSelecionados.has(m.slug);
                return (
                  <button
                    key={m.slug}
                    onClick={() => toggleModulo(m.slug)}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors text-left ${
                      ativo
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-background text-muted-foreground hover:border-primary/50"
                    }`}
                  >
                    <span
                      className={`w-4 h-4 rounded flex items-center justify-center border text-xs flex-shrink-0 ${
                        ativo
                          ? "bg-primary border-primary text-white"
                          : "border-border"
                      }`}
                    >
                      {ativo ? "✓" : ""}
                    </span>
                    {m.label}
                  </button>
                );
              })}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ---- RESULTADOS ---- */}
      <div className="space-y-4">
        <h3 className="text-base font-semibold text-muted-foreground uppercase tracking-wide">
          Projeção mensal
        </h3>

        <div className="grid grid-cols-2 gap-3">
          <ResultCard
            label="Receita potencial"
            valor={formatBRL(resultado.receitaMensal)}
            sub={`${formatNum(condominios)} cond. × ${formatBRL(ticket)}`}
          />
          <ResultCard
            label="Custo estimado de IA"
            valor={formatBRL(resultado.custoIA)}
            sub={`${(
              MODULOS_OPCOES.filter((m) => modulosSelecionados.has(m.slug))
                .reduce((a, m) => a + m.precoPct, 0) * 100
            ).toFixed(0)}% da receita`}
          />
          <ResultCard
            label="Margem bruta estimada"
            valor={formatBRL(resultado.margemBruta)}
            destaque
            sub={`${resultado.margemPct.toFixed(0)}% de margem`}
          />
          <ResultCard
            label="Horas salvas/mês"
            valor={`~${formatNum(resultado.horasSalvas)}h`}
            sub="atendimento manual substituído"
          />
        </div>

        <div className="rounded-xl border border-border bg-background p-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Premissas desta simulação
          </p>
          <ul className="mt-2 text-xs text-muted-foreground space-y-1 list-disc pl-4">
            <li>
              Custo de IA como percentual do faturamento da carteira, por módulo
              contratado.
            </li>
            <li>
              {horasPorCondominio.toLocaleString("pt-BR")} h/mês economizadas por
              condomínio, por módulo — premissa ajustável acima.
            </li>
            <li>
              Números de receita e margem derivam apenas dos valores informados
              nesta tela.
            </li>
          </ul>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed">
          * Estimativas ilustrativas para fins de demonstração. Custos reais
          dependem do volume de uso, modelo de LLM e infraestrutura escolhidos.
        </p>
      </div>
    </div>
  );
}
