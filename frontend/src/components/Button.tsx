import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "destructive";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-primary text-white hover:bg-primary/90",
  secondary: "border border-slate-300 bg-surface text-foreground hover:bg-slate-50",
  destructive: "bg-status-denied text-white hover:bg-status-denied/90",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
