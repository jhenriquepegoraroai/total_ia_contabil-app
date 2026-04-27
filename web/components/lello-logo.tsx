import { cn } from "@/lib/utils";

/**
 * Logo placeholder da Lello — desenho cursivo aproximado, na cor primary.
 * Substituir pelo SVG oficial quando disponível em /public/themes/lello/logo.svg.
 */
export function LelloLogo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <svg
        viewBox="0 0 120 36"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Lello"
        className="h-full w-auto"
      >
        <text
          x="0"
          y="26"
          fontFamily="Georgia, 'Times New Roman', serif"
          fontStyle="italic"
          fontSize="32"
          fontWeight="700"
          fill="currentColor"
          className="text-primary"
        >
          lello
        </text>
      </svg>
      <span className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground font-semibold">
        Condomínios
      </span>
    </div>
  );
}
