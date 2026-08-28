const VARIANTS = {
  amber: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  neutral: "bg-brown-700/40 text-cream/70 border-brown-700",
  danger: "bg-red-500/10 text-red-300 border-red-500/30",
  success: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
} as const;

export function Badge({
  children,
  variant = "neutral",
}: {
  children: React.ReactNode;
  variant?: keyof typeof VARIANTS;
}) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${VARIANTS[variant]}`}>
      {children}
    </span>
  );
}
