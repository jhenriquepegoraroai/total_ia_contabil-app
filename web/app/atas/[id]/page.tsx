"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  FileText,
  Loader2,
  Mic,
  Send,
  Sparkles,
  Upload,
  XCircle,
} from "lucide-react";

import { AtaEditor, AtaViewer } from "@/components/atas/editor";
import { AtaStatusBadge } from "@/components/atas/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  atasAprovarDiff,
  atasAtualizarInsumos,
  atasBuscar,
  atasBuscarDiff,
  atasBuscarVersao,
  atasConfirmarUploadAudio,
  atasCorrigir,
  atasDevolver,
  atasEditarConsultor,
  atasEnviarPresidente,
  atasEnviarSindico,
  atasFinalizar,
  atasGerar,
  atasListarAudios,
  atasListarVersoes,
  atasUploadAudioUrl,
  uploadDiretoAzure,
} from "@/lib/api";
import { lerSessao } from "@/lib/auth";
import type {
  AtaAudio,
  AtaDetail,
  AtaDiff,
  AtaVersaoSummary,
} from "@/lib/types";


// Polling enquanto algum job em background está rodando.
const STATUS_VIVOS = new Set([
  "aguardando_transcricao",
  "aguardando_geracao",
  "comparando",
  "corrigindo",
]);


export default function AtaDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const ataId = params.id;

  const [sessao, setSessao] = useState<ReturnType<typeof lerSessao>>(null);
  const [ata, setAta] = useState<AtaDetail | null>(null);
  const [versoes, setVersoes] = useState<AtaVersaoSummary[]>([]);
  const [audios, setAudios] = useState<AtaAudio[]>([]);
  const [conteudoEditor, setConteudoEditor] = useState<string>("");
  const [diff, setDiff] = useState<AtaDiff | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [enviando, setEnviando] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auth + módulo
  useEffect(() => {
    const s = lerSessao();
    if (!s) {
      router.replace("/login");
      return;
    }
    if (s.is_superadmin || s.tenant_id === "_system") {
      router.replace("/admin");
      return;
    }
    if (!s.modulos_contratados.atas) {
      router.replace("/");
      return;
    }
    setSessao(s);
  }, [router]);

  // Carregamento inicial + recarregamento quando ata muda
  async function carregar(silencioso = false) {
    if (!silencioso) setCarregando(true);
    try {
      setErro(null);
      const [a, vs, au] = await Promise.all([
        atasBuscar(ataId),
        atasListarVersoes(ataId),
        atasListarAudios(ataId),
      ]);
      setAta(a);
      setVersoes(vs);
      setAudios(au);

      // Se há versão atual, baixa o conteúdo HTML pro editor.
      if (a.versao_atual_id) {
        try {
          const v = await atasBuscarVersao(ataId, a.versao_atual_id);
          setConteudoEditor(v.conteudo_html);
        } catch {
          /* ignora — versão pode ter sumido em race */
        }
      }

      // Se status implica diff disponível, busca.
      if (a.status === "revisao_consultor_diff" || a.status === "revisao_consultor_final") {
        try {
          const d = await atasBuscarDiff(ataId);
          setDiff(d);
        } catch {
          setDiff(null);
        }
      } else {
        setDiff(null);
      }
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    if (sessao) carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessao, ataId]);

  // Polling em estados vivos
  useEffect(() => {
    if (!ata) return;
    if (!STATUS_VIVOS.has(ata.status)) return;
    const id = setInterval(() => carregar(true), 3000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ata?.status]);

  // Helpers de papel do user nesta ata
  const papel = useMemo(() => {
    if (!ata || !sessao) return null;
    const uid = sessao.user_id;
    if (ata.consultor_user_id === uid) return "consultor";
    if (ata.sindico_user_id === uid) return "sindico";
    if (ata.presidente_user_id === uid) return "presidente";
    return null;
  }, [ata, sessao]);

  // Wrappers de ação — mostra feedback + recarrega
  async function executar(acao: string, fn: () => Promise<unknown>) {
    setEnviando(acao);
    setErro(null);
    setFeedback(null);
    try {
      await fn();
      await carregar(true);
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : String(err));
    } finally {
      setEnviando(null);
    }
  }

  async function handleSalvarInsumos(patch: Record<string, string | null>) {
    await executar("insumos", async () => {
      await atasAtualizarInsumos(ataId, patch);
      setFeedback("Insumos salvos.");
    });
  }

  async function handleGerar() {
    await executar("gerar", async () => {
      await atasGerar(ataId);
      setFeedback("Geração agendada — aguarde alguns segundos.");
    });
  }

  async function handleSalvarEdicaoConsultor() {
    await executar("editar", async () => {
      await atasEditarConsultor(ataId, conteudoEditor);
      setFeedback("Edição salva.");
    });
  }

  async function handleEnviarSindico() {
    await executar("enviar-sindico", async () => {
      await atasEnviarSindico(ataId);
      setFeedback("Enviada pro síndico — e-mail em rota.");
    });
  }

  async function handleEnviarPresidente() {
    await executar("enviar-presidente", async () => {
      await atasEnviarPresidente(ataId);
      setFeedback("Enviada pro presidente — e-mail em rota.");
    });
  }

  async function handleDevolver() {
    await executar("devolver", async () => {
      await atasDevolver(ataId, conteudoEditor);
      setFeedback("Ata devolvida ao consultor.");
    });
  }

  async function handleAprovarDiff(decisao: "aceitar" | "rejeitar") {
    const motivo =
      decisao === "rejeitar"
        ? prompt("Motivo da rejeição (opcional):") || null
        : null;
    await executar(`diff-${decisao}`, async () => {
      await atasAprovarDiff(ataId, { decisao, motivo });
      setFeedback(decisao === "aceitar" ? "Diff aceito." : "Diff rejeitado.");
    });
  }

  async function handleCorrigir() {
    await executar("corrigir", async () => {
      await atasCorrigir(ataId);
      setFeedback("Correção agendada.");
    });
  }

  async function handleFinalizar() {
    if (!confirm("Confirmar registro da ata? Essa ação não pode ser desfeita.")) return;
    await executar("finalizar", async () => {
      await atasFinalizar(ataId);
      setFeedback("Ata registrada.");
    });
  }

  async function handleUploadAudio(file: File) {
    await executar("audio", async () => {
      const sas = await atasUploadAudioUrl(ataId, {
        file_name: file.name,
        file_size_bytes: file.size,
        content_type: file.type,
      });
      await uploadDiretoAzure(sas.upload_url, file);
      await atasConfirmarUploadAudio(ataId, sas.audio_id);
      setFeedback("Áudio enviado — transcrição agendada.");
    });
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // ---------------------------------------------------------------- render
  if (carregando && !ata) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </main>
    );
  }
  if (!ata) {
    return (
      <main className="flex-1 max-w-3xl mx-auto px-4 py-8">
        <Button asChild variant="ghost" size="sm" className="mb-4">
          <Link href="/atas"><ArrowLeft className="h-4 w-4" /> Voltar</Link>
        </Button>
        <Card>
          <CardContent className="p-8 text-center text-muted-foreground">
            Ata não encontrada.
          </CardContent>
        </Card>
      </main>
    );
  }

  const editavelPeloConsultor =
    papel === "consultor" &&
    ["gerada", "revisao_consultor", "revisao_consultor_diff", "revisao_consultor_final"].includes(
      ata.status
    );
  const editavelPeloSindico =
    papel === "sindico" && ["aguardando_sindico", "revisao_sindico"].includes(ata.status);
  const editavelPeloPresidente =
    papel === "presidente" && ["aguardando_presidente", "revisao_presidente"].includes(ata.status);
  const podeEditar = editavelPeloConsultor || editavelPeloSindico || editavelPeloPresidente;

  return (
    <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-8">
      {/* Header + ações --------------------------------------------------- */}
      <Button asChild variant="ghost" size="sm" className="mb-4">
        <Link href="/atas"><ArrowLeft className="h-4 w-4" /> Voltar</Link>
      </Button>

      <header className="mb-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <FileText className="h-6 w-6 text-primary shrink-0" />
              <h1 className="text-2xl font-bold truncate">{ata.titulo}</h1>
              <AtaStatusBadge status={ata.status} />
            </div>
            {ata.referencia && (
              <p className="text-sm text-muted-foreground mt-1 ml-9">
                Condomínio {ata.referencia}
              </p>
            )}
            {ata.erro_detalhe && (
              <p className="text-sm text-destructive mt-2 ml-9">{ata.erro_detalhe}</p>
            )}
          </div>
        </div>
      </header>

      {feedback && (
        <div className="mb-4 rounded-md bg-green-50 border border-green-200 px-3 py-2 text-sm text-green-900">
          {feedback}
        </div>
      )}
      {erro && (
        <div className="mb-4 rounded-md bg-destructive/10 border border-destructive/30 px-3 py-2 text-sm text-destructive">
          {erro}
        </div>
      )}

      {/* Insumos (consultor edita) ---------------------------------------- */}
      {papel === "consultor" && ata.status !== "registrada" && (
        <SecaoInsumos
          ata={ata}
          enviando={enviando === "insumos"}
          onSalvar={handleSalvarInsumos}
        />
      )}

      {/* Áudio (consultor sobe) ------------------------------------------- */}
      {papel === "consultor" && (
        <Card className="mb-6">
          <CardContent className="p-6">
            <h2 className="font-semibold mb-3 flex items-center gap-2">
              <Mic className="h-4 w-4" /> Áudio da assembleia
            </h2>
            {audios.length === 0 ? (
              <p className="text-sm text-muted-foreground mb-3">
                Nenhum áudio enviado. O upload é opcional — você também pode colar
                a transcrição direto no campo "Resumo" acima.
              </p>
            ) : (
              <ul className="space-y-1 mb-3 text-sm">
                {audios.map((a) => (
                  <li key={a.id} className="flex items-center gap-2">
                    {a.status === "done" ? (
                      <CheckCircle2 className="h-4 w-4 text-green-700" />
                    ) : a.status === "failed" ? (
                      <XCircle className="h-4 w-4 text-destructive" />
                    ) : (
                      <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    )}
                    <span className="truncate">{a.file_name}</span>
                    <span className="text-xs text-muted-foreground">
                      {a.status === "done" && a.duracao_segundos
                        ? `${Math.round(a.duracao_segundos / 60)} min · ${a.qtde_chunks ?? "?"} chunks · $${a.custo_estimado_usd?.toFixed(3) ?? "-"}`
                        : a.status}
                    </span>
                    {a.error_detail && (
                      <span className="text-xs text-destructive truncate" title={a.error_detail}>
                        {a.error_detail}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleUploadAudio(f);
                }}
                disabled={enviando === "audio"}
                className="text-sm"
              />
              {enviando === "audio" && <Loader2 className="h-4 w-4 animate-spin" />}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Diff (consultor avalia) ------------------------------------------ */}
      {diff && papel === "consultor" && (
        <Card className="mb-6">
          <CardContent className="p-6">
            <h2 className="font-semibold mb-3">Comparação — alterações do ator externo</h2>
            <p className="text-sm text-muted-foreground mb-3">
              Vermelho riscado = removido pelo ator. Azul = adicionado. Você pode
              <strong> aceitar</strong> (segue o fluxo) ou <strong>rejeitar</strong>
              (volta pro mesmo ator pra revisar com motivo).
            </p>
            <AtaViewer conteudoHtml={diff.conteudo_html} minHeight={300} />
            <div className="flex justify-end gap-2 mt-4">
              <Button
                variant="outline"
                onClick={() => handleAprovarDiff("rejeitar")}
                disabled={enviando !== null}
              >
                {enviando === "diff-rejeitar" ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                Rejeitar e devolver
              </Button>
              <Button
                onClick={() => handleAprovarDiff("aceitar")}
                disabled={enviando !== null}
              >
                {enviando === "diff-aceitar" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                Aceitar e seguir
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Editor / viewer da versão atual ---------------------------------- */}
      <Card className="mb-6">
        <CardContent className="p-6">
          <h2 className="font-semibold mb-3">
            {podeEditar ? "Editar ata" : "Versão atual"}
          </h2>
          {ata.versao_atual_id ? (
            podeEditar ? (
              <>
                <AtaEditor
                  conteudoInicial={conteudoEditor}
                  onChange={setConteudoEditor}
                />
                <div className="flex justify-end gap-2 mt-3 flex-wrap">
                  {editavelPeloConsultor && (
                    <Button
                      variant="outline"
                      onClick={handleSalvarEdicaoConsultor}
                      disabled={enviando !== null}
                    >
                      {enviando === "editar" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                      Salvar edição
                    </Button>
                  )}
                  {(editavelPeloSindico || editavelPeloPresidente) && (
                    <Button onClick={handleDevolver} disabled={enviando !== null}>
                      {enviando === "devolver" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                      Devolver ao consultor
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <AtaViewer conteudoHtml={conteudoEditor} />
            )
          ) : (
            <p className="text-sm text-muted-foreground">
              Sem versão ainda. Preencha os insumos acima e clique em "Gerar ata".
            </p>
          )}
        </CardContent>
      </Card>

      {/* Botões de fluxo (consultor) -------------------------------------- */}
      {papel === "consultor" && (
        <Card className="mb-6">
          <CardContent className="p-6">
            <h2 className="font-semibold mb-3">Próximas ações</h2>
            <div className="flex gap-2 flex-wrap">
              {(ata.status === "rascunho" || ata.status === "falhou") && (
                <Button onClick={handleGerar} disabled={enviando !== null}>
                  {enviando === "gerar" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Gerar ata
                </Button>
              )}
              {["gerada", "revisao_consultor"].includes(ata.status) && ata.sindico_user_id && (
                <Button onClick={handleEnviarSindico} disabled={enviando !== null}>
                  <Send className="h-4 w-4" /> Enviar pro síndico
                </Button>
              )}
              {["gerada", "revisao_consultor"].includes(ata.status) && ata.presidente_user_id && (
                <Button onClick={handleEnviarPresidente} disabled={enviando !== null}>
                  <Send className="h-4 w-4" /> Enviar pro presidente
                </Button>
              )}
              {["gerada", "revisao_consultor", "revisao_consultor_final"].includes(ata.status) && (
                <Button variant="outline" onClick={handleCorrigir} disabled={enviando !== null}>
                  {enviando === "corrigir" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  Pular pra correção ortográfica
                </Button>
              )}
              {ata.status === "revisao_consultor_final" && (
                <Button onClick={handleFinalizar} disabled={enviando !== null}>
                  <CheckCircle2 className="h-4 w-4" /> Registrar ata
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Histórico de versões --------------------------------------------- */}
      <Card>
        <CardContent className="p-6">
          <h2 className="font-semibold mb-3">Histórico de versões</h2>
          {versoes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma versão ainda.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {versoes.map((v) => (
                <li key={v.id} className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {new Date(v.criada_em).toLocaleString("pt-BR")}
                  </span>
                  <span className="font-medium">{v.tipo}</span>
                  {v.id === ata.versao_atual_id && (
                    <span className="text-xs px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                      atual
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </main>
  );
}


// =============================================================================
// Subcomponente — formulário de insumos (consultor edita antes de gerar)
// =============================================================================
function SecaoInsumos({
  ata,
  enviando,
  onSalvar,
}: {
  ata: AtaDetail;
  enviando: boolean;
  onSalvar: (patch: Record<string, string | null>) => Promise<void>;
}) {
  const [cabecalho, setCabecalho] = useState(ata.insumos_json.cabecalho ?? "");
  const [edital, setEdital] = useState(ata.insumos_json.edital ?? "");
  const [resumo, setResumo] = useState(ata.insumos_json.resumo ?? "");
  const [complemento, setComplemento] = useState(ata.insumos_json.complemento ?? "");
  const [nomePresidente, setNomePresidente] = useState(ata.insumos_json.nome_presidente ?? "");
  const [nomeSecretario, setNomeSecretario] = useState(ata.insumos_json.nome_secretario ?? "");
  const [cnpj, setCnpj] = useState(ata.insumos_json.cnpj_condominio ?? "");

  // Resincroniza quando a ata recarrega (ex: transcrição preencheu resumo).
  useEffect(() => {
    setCabecalho(ata.insumos_json.cabecalho ?? "");
    setEdital(ata.insumos_json.edital ?? "");
    setResumo(ata.insumos_json.resumo ?? "");
    setComplemento(ata.insumos_json.complemento ?? "");
    setNomePresidente(ata.insumos_json.nome_presidente ?? "");
    setNomeSecretario(ata.insumos_json.nome_secretario ?? "");
    setCnpj(ata.insumos_json.cnpj_condominio ?? "");
  }, [ata.insumos_json]);

  function salvar() {
    onSalvar({
      cabecalho: cabecalho || null,
      edital: edital || null,
      resumo: resumo || null,
      complemento: complemento || null,
      nome_presidente: nomePresidente || null,
      nome_secretario: nomeSecretario || null,
      cnpj_condominio: cnpj || null,
    });
  }

  return (
    <Card className="mb-6">
      <CardContent className="p-6 space-y-3">
        <h2 className="font-semibold flex items-center gap-2">
          <Upload className="h-4 w-4" /> Insumos da geração
        </h2>
        <p className="text-xs text-muted-foreground">
          Cabeçalho e Resumo são obrigatórios pra gerar. Edital, Complemento e
          dados adicionais são opcionais.
        </p>

        <div className="space-y-1">
          <label className="text-sm font-medium">Cabeçalho (HTML — dados oficiais do condomínio)</label>
          <Textarea
            rows={4}
            value={cabecalho}
            onChange={(e) => setCabecalho(e.target.value)}
            placeholder="HTML com nome, CNPJ, endereço, data, horário..."
          />
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium">Resumo da assembleia (texto)</label>
          <Textarea
            rows={6}
            value={resumo}
            onChange={(e) => setResumo(e.target.value)}
            placeholder="Cole aqui o resumo. Se você subir áudio, a transcrição preenche este campo automaticamente."
          />
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium">Edital / pauta (HTML — opcional)</label>
          <Textarea
            rows={3}
            value={edital}
            onChange={(e) => setEdital(e.target.value)}
            placeholder="HTML do edital com a lista de itens da pauta."
          />
        </div>

        <div className="space-y-1">
          <label className="text-sm font-medium">Complemento (texto — opcional)</label>
          <Textarea
            rows={3}
            value={complemento}
            onChange={(e) => setComplemento(e.target.value)}
            placeholder="Dados factuais adicionais (votos, eleições, datas) que não estão no resumo."
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-sm font-medium">Presidente (nome)</label>
            <Input value={nomePresidente} onChange={(e) => setNomePresidente(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">Secretário (nome)</label>
            <Input value={nomeSecretario} onChange={(e) => setNomeSecretario(e.target.value)} />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">CNPJ do condomínio</label>
            <Input value={cnpj} onChange={(e) => setCnpj(e.target.value)} />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <Button onClick={salvar} disabled={enviando}>
            {enviando ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Salvar insumos
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
