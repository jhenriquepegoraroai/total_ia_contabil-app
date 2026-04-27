"use client";

import * as React from "react";
import { Eye, EyeOff } from "lucide-react";

import { Input } from "./input";
import { cn } from "@/lib/utils";

type PasswordInputProps = Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  "type"
>;

export const PasswordInput = React.forwardRef<HTMLInputElement, PasswordInputProps>(
  function PasswordInput({ className, ...props }, ref) {
    const [visivel, setVisivel] = React.useState(false);
    return (
      <div className="relative">
        <Input
          {...props}
          ref={ref}
          type={visivel ? "text" : "password"}
          className={cn("pr-9", className)}
        />
        <button
          type="button"
          onClick={() => setVisivel((v) => !v)}
          aria-label={visivel ? "Esconder senha" : "Mostrar senha"}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
          tabIndex={-1}
        >
          {visivel ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    );
  }
);
