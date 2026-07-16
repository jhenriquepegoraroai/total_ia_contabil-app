/**
 * Seção estática "Escolha sua modalidade".
 *
 * VITRINE VISUAL — sem preços, sem checkout, sem fluxo funcional. O modelo de
 * cobrança ainda não existe. Na apresentação, esta tela é verbalizada como
 * "assim o cliente vai contratar" (futuro), nunca como funcionalidade pronta.
 *
 * Só modalidades A e B ganham card de contratação; a C (dados de mercado) é
 * tratada como visão em outra seção, sem card de plano.
 */

import { Check } from "lucide-react";

interface PlanoInfo {
  letra: string;
  titulo: string;
  subtitulo: string;
  ideal: string;
  destaque: boolean;
  itens: string[];
}

const PLANOS: PlanoInfo[] = [
  {
    letra: "A",
    titulo: "Acoplada",
    subtitulo: "White-label sobre a plataforma Lello",
    ideal: "Administradoras que operam integradas à Lello.",
    destaque: false,
    itens: [
      "Implantação rápida, sem trocar infraestrutura",
      "Todos os agentes disponíveis",
      "Identidade visual da sua marca",
      "Suporte e evolução contínua",
    ],
  },
  {
    letra: "B",
    titulo: "Standalone",
    subtitulo: "Infraestrutura e marca próprias",
    ideal: "Administradoras independentes que querem IA própria.",
    destaque: true,
    itens: [
      "Ambiente isolado e domínio próprio",
      "Controle total sobre os dados",
      "Todos os agentes disponíveis",
      "Onboarding assistido de uma nova administradora",
    ],
  },
];

export function ModalidadePlanos() {
  return (
    <section id="planos" className="bg-background py-20 sm:py-28">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-extrabold">
            Escolha sua modalidade
          </h2>
          <p className="mt-3 text-lg text-muted-foreground max-w-xl mx-auto">
            Dois caminhos para levar a plataforma à sua operação. Nosso time
            desenha o plano com você.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {PLANOS.map((plano) => (
            <div
              key={plano.letra}
              className={`relative bg-background rounded-2xl border p-8 flex flex-col gap-5 ${
                plano.destaque
                  ? "border-primary shadow-lg ring-1 ring-primary/20"
                  : "border-border hover:shadow-md transition-shadow"
              }`}
            >
              {plano.destaque && (
                <span className="absolute -top-3 left-8 text-xs font-semibold uppercase tracking-wider bg-primary text-primary-foreground px-3 py-1 rounded-full">
                  Mais escolhida
                </span>
              )}

              <div>
                <span className="text-xs font-semibold text-primary uppercase tracking-wider">
                  Modalidade {plano.letra}
                </span>
                <h3 className="text-2xl font-bold mt-1">{plano.titulo}</h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {plano.subtitulo}
                </p>
              </div>

              <ul className="flex flex-col gap-3 flex-1">
                {plano.itens.map((item) => (
                  <li key={item} className="flex items-start gap-2 text-sm">
                    <Check className="h-5 w-5 text-primary flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>

              <div className="pt-4 border-t border-border">
                <p className="text-xs text-muted-foreground mb-3">
                  <span className="font-medium text-foreground">Ideal para:</span>{" "}
                  {plano.ideal}
                </p>
                <span className="inline-flex items-center justify-center w-full rounded-md bg-primary text-primary-foreground font-semibold h-11 px-6 opacity-90">
                  Falar com o time
                </span>
              </div>
            </div>
          ))}
        </div>

        <p className="text-center text-xs text-muted-foreground mt-8">
          Planos e condições comerciais em definição — apresentados como direção,
          não como oferta fechada.
        </p>
      </div>
    </section>
  );
}
