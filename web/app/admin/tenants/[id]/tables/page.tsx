"use client";

import { use, useEffect, useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Database,
  Loader2,
  Search,
  Table2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import {
  ApiError,
  adminListarRowsTabela,
  adminListarTabelas,
} from "@/lib/api";
import type { TableRows, TableSummary } from "@/lib/types";


export default function TablesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: tenantId } = use(params);

  const [tabelas, setTabelas] = useState<TableSummary[]>([]);
  const [carregandoLista, setCarregandoLista] = useState(true);
  const [erroLista, setErroLista] = useState<string | null>(null);

  const [tabelaAtiva, setTabelaAtiva] = useState<string | null>(null);
  const [filtroRef, setFiltroRef] = useState("");
  const [filtroQ, setFiltroQ] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const [data, setData] = useState<TableRows | null>(null);
  const [carregandoRows, setCarregandoRows] = useState(false);
  const [erroRows, setErroRows] = useState<string | null>(null);

  // Carrega lista de tabelas (uma vez).
  useEffect(() => {
    adminListarTabelas(tenantId)
      .then((t) => {
        setTabelas(t);
        if (!tabelaAtiva && t.length) setTabelaAtiva(t[0].name);
      })
      .catch((err) =>
        setErroLista(err instanceof ApiError ? err.message : String(err))
      )
      .finally(() => setCarregandoLista(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId]);

  // Recarrega rows quando muda tabela / filtro / paginação.
  useEffect(() => {
    if (!tabelaAtiva) return;
    setCarregandoRows(true);
    setErroRows(null);
    adminListarRowsTabela(tenantId, tabelaAtiva, {
      referencia: filtroRef.trim() || undefined,
      q: filtroQ.trim() || undefined,
      offset,
      limit,
    })
      .then(setData)
      .catch((err) =>
        setErroRows(err instanceof ApiError ? err.message : String(err))
      )
      .finally(() => setCarregandoRows(false));
  }, [tenantId, tabelaAtiva, filtroRef, filtroQ, offset]);

  // Reset paginação ao trocar tabela ou filtro.
  function selecionarTabela(nome: string) {
    setTabelaAtiva(nome);
    setOffset(0);
    setFiltroRef("");
    setFiltroQ("");
  }

  function aplicarFiltroRef(v: string) {
    setFiltroRef(v);
    setOffset(0);
  }

  function aplicarFiltroQ(v: string) {
    setFiltroQ(v);
    setOffset(0);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Table2 className="h-5 w-5 text-primary" /> Tabelas
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Inspecione o conteúdo das tabelas multi-tenant deste cliente.
          Read-only — útil pra debugar &quot;por que esse cond não respondeu X&quot;
          ou conferir se a ingestão criou os chunks esperados.
        </p>
      </div>

      {erroLista && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {erroLista}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6">
        {/* Picker */}
        <aside className="space-y-1">
          {carregandoLista ? (
            [0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12" />)
          ) : (
            tabelas.map((t) => (
              <button
                key={t.name}
                onClick={() => selecionarTabela(t.name)}
                className={`w-full text-left rounded-md p-2.5 transition-colors ${
                  tabelaAtiva === t.name
                    ? "bg-primary/10 border border-primary/30"
                    : "hover:bg-accent/40 border border-transparent"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-sm">{t.label}</span>
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                    {t.qtde_linhas}
                  </Badge>
                </div>
                <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                  {t.descricao}
                </p>
              </button>
            ))
          )}
        </aside>

        {/* Grid */}
        <section className="min-w-0">
          {!tabelaAtiva ? (
            <Card>
              <CardContent className="p-10 text-center text-muted-foreground">
                <Database className="h-10 w-10 mx-auto mb-3 opacity-40" />
                <p>Selecione uma tabela para ver os dados.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {/* Filtros */}
              <div className="flex flex-wrap gap-2 items-center">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground shrink-0">Cond:</span>
                  <Input
                    value={filtroRef}
                    onChange={(e) => aplicarFiltroRef(e.target.value)}
                    placeholder="ex: 99999"
                    className="h-8 text-sm w-32"
                  />
                </div>
                <div className="flex items-center gap-1.5 flex-1 max-w-md">
                  <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <Input
                    value={filtroQ}
                    onChange={(e) => aplicarFiltroQ(e.target.value)}
                    placeholder="busca textual…"
                    className="h-8 text-sm"
                  />
                </div>
                {data && (
                  <span className="text-xs text-muted-foreground ml-auto">
                    {data.total === 0
                      ? "0 linhas"
                      : `${offset + 1}–${Math.min(offset + limit, data.total)} de ${data.total}`}
                  </span>
                )}
              </div>

              {erroRows && (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {erroRows}
                </div>
              )}

              {/* Grid */}
              <Card>
                <CardContent className="p-0 overflow-x-auto">
                  {carregandoRows ? (
                    <div className="p-6 text-sm text-muted-foreground inline-flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" /> Carregando…
                    </div>
                  ) : data && data.rows.length > 0 ? (
                    <Grid data={data} />
                  ) : (
                    <div className="p-10 text-center text-muted-foreground">
                      <Database className="h-8 w-8 mx-auto mb-2 opacity-40" />
                      <p className="text-sm">Nenhuma linha com esses filtros.</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Paginação */}
              {data && data.total > limit && (
                <div className="flex items-center justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset === 0 || carregandoRows}
                    onClick={() => setOffset(Math.max(0, offset - limit))}
                  >
                    <ChevronLeft className="h-3.5 w-3.5" /> Anterior
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={offset + limit >= data.total || carregandoRows}
                    onClick={() => setOffset(offset + limit)}
                  >
                    Próxima <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}


function Grid({ data }: { data: TableRows }) {
  const cols = useMemo(() => data.columns, [data.columns]);

  return (
    <table className="w-full text-xs">
      <thead className="bg-muted/40 sticky top-0">
        <tr>
          {cols.map((c) => (
            <th
              key={c}
              className="text-left px-3 py-2 font-medium text-muted-foreground border-b whitespace-nowrap"
            >
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.rows.map((row, i) => (
          <tr key={i} className="border-b hover:bg-accent/30">
            {cols.map((c) => (
              <td key={c} className="px-3 py-1.5 align-top max-w-[400px]">
                <CellValue value={row[c]} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}


function CellValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground/50 italic">null</span>;
  }
  if (typeof value === "boolean") {
    return <span className={value ? "text-green-700" : "text-muted-foreground"}>
      {value ? "true" : "false"}
    </span>;
  }
  if (typeof value === "number") {
    return <span className="font-mono">{value}</span>;
  }
  const str = String(value);
  // Datas ISO ficam mais legíveis sem timezone.
  if (/^\d{4}-\d{2}-\d{2}/.test(str)) {
    return <span className="font-mono whitespace-nowrap">{str.replace("T", " ").slice(0, 19)}</span>;
  }
  return <span className="break-words">{str}</span>;
}
