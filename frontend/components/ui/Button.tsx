import { ButtonHTMLAttributes } from "react";

const VARIANTS = {
  primary: "bg-amber-500 text-brown-950 hover:bg-amber-400 disabled:bg-amber-500/40",
  ghost: "bg-transparent text-cream/70 border border-brown-700 hover:bg-brown-900 disabled:opacity-40",
  danger: "bg-red-600/90 text-cream hover:bg-red-600 disabled:bg-red-600/40",
} as const;

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof VARIANTS;
}

export function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
