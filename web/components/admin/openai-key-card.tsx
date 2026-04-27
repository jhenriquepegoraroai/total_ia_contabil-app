"use client";

import { useState } from "react";
import { Eye, EyeOff, KeyRound, Building2, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import type { TenantOpenAIConfig } from "@/lib/types";


/**
 * Card reutilizável para configurar a integração OpenAI do tenant.
 *
 * - mode='lello': a Lello paga o consumo (chave global do env).
 * - mode='custom': o próprio cliente fornece a chave OpenAI (billing dele).
 *
 * No edit, se o backend devolveu `api_key` mascarada (`sk-proj...wxyz`),
 * mostramos um badge "Chave configurada" e o input fica vazio até o user
 * escolher trocar. Isso evita re-input a cada save (o backend preserva
 * a chave salva quando o PUT vem sem nova chave).
 */
export function OpenAIKeyCard({
  value,
  onChange,
}: {
  value: TenantOpenAIConfig;
  onChange: (v: TenantOpenAIConfig) => void;
}) {
  const [showKey, setShowKey] = useState(false);
  const apiKeyMascarada = value.api_key && /\.\.\.|\*\*\*/.test(value.api_key);

  function setMode(mode: "lello" | "custom") {
    if (mode === "lello") {
      onChange({ mode: "lello", api_key: null, secret_name: value.secret_name });
    } else {
      onChange({ ...value, mode: "custom" });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-primary" /> Integração OpenAI
        </CardTitle>
        <CardDescription>
          Quem paga o consumo de IA deste tenant. Pode ser a chave da Lello
          (consumo entra na sua conta) ou uma chave própria do cliente.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid sm:grid-cols-2 gap-2">
          <ModeOption
            ativo={value.mode === "lello"}
            label="Chave Lello (default)"
            descricao="Lello paga o consumo. Não precisa configurar nada."
            icon={Building2}
            onClick={() => setMode("lello")}
          />
          <ModeOption
            ativo={value.mode === "custom"}
            label="Chave própria do cliente"
            descricao="Cliente fornece a chave; consumo entra na conta dele."
            icon={KeyRound}
            onClick={() => setMode("custom")}
          />
        </div>

        {value.mode === "custom" && (
          <div className="space-y-2 pt-2 border-t">
            {apiKeyMascarada && (
              <div className="flex items-center justify-between gap-2 rounded-md bg-green-500/10 border border-green-500/30 px-3 py-2 text-sm">
                <span className="inline-flex items-center gap-1.5 text-green-700">
                  <CheckCircle2 className="h-4 w-4" />
                  Chave configurada
                </span>
                <code className="text-xs text-muted-foreground">{value.api_key}</code>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onChange({ ...value, api_key: "" })}
                >
                  Trocar chave
                </Button>
              </div>
            )}

            {!apiKeyMascarada && (
              <div className="space-y-1">
                <label className="text-sm font-medium">Chave da OpenAI do cliente</label>
                <div className="flex gap-2">
                  <Input
                    type={showKey ? "text" : "password"}
                    value={value.api_key ?? ""}
                    onChange={(e) => onChange({ ...value, api_key: e.target.value })}
                    placeholder="sk-proj-..."
                    autoComplete="off"
                    spellCheck={false}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={() => setShowKey((s) => !s)}
                    title={showKey ? "Ocultar" : "Mostrar"}
                  >
                    {showKey ? <EyeOff /> : <Eye />}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  A chave começa com <code className="font-mono">sk-</code>. Após
                  salvar, ela aparecerá mascarada e ficará armazenada com segurança.
                </p>
              </div>
            )}
          </div>
        )}

        {value.mode === "lello" && (
          <div className="text-xs text-muted-foreground border-t pt-3">
            Modo padrão. O assistente usa a chave global configurada na Lello
            (variável <code className="font-mono">OPEN_AI_KEY</code> do servidor).
          </div>
        )}
      </CardContent>
    </Card>
  );
}


function ModeOption({
  ativo,
  label,
  descricao,
  icon: Icon,
  onClick,
}: {
  ativo: boolean;
  label: string;
  descricao: string;
  icon: React.ComponentType<{ className?: string }>;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`text-left rounded-md border p-3 transition-colors ${
        ativo ? "border-primary bg-primary/5" : "hover:bg-accent/30"
      }`}
    >
      <div className="font-medium text-sm flex items-center gap-2">
        <Icon className="h-4 w-4" /> {label}
        {ativo && <Badge variant="default" className="text-[9px] py-0">selecionado</Badge>}
      </div>
      <div className="text-xs text-muted-foreground mt-0.5">{descricao}</div>
    </button>
  );
}
