import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";

interface AuthLayoutProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}

/** Shared shell for the 4 auth pages (login/signup/forgot/reset) — logo
 * mark, gradient blobs + dot grid backdrop, and the card itself, so each
 * page only supplies its own form. */
export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-50 px-4 py-12 dark:bg-slate-950">
      <div className="bg-dot-grid absolute inset-0 text-slate-300 dark:text-slate-700" aria-hidden="true" />
      <div className="auth-blob -top-24 -left-20 h-72 w-72 bg-brand-400" aria-hidden="true" />
      <div className="auth-blob -bottom-28 -right-16 h-80 w-80 bg-violet-400" aria-hidden="true" />

      <div className="relative w-full max-w-sm space-y-6 rounded-2xl border border-slate-200/70 bg-white/90 p-8 shadow-xl shadow-slate-900/5 backdrop-blur-sm dark:border-slate-800 dark:bg-slate-900/90">
        <div className="flex flex-col items-center space-y-3 text-center">
          <div className="bg-gradient-brand flex h-11 w-11 items-center justify-center rounded-xl shadow-md shadow-brand-600/30">
            <Sparkles size={20} className="text-white" />
          </div>
          <div className="space-y-1">
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">{title}</h1>
            {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>}
          </div>
        </div>

        {children}

        {footer && <div className="text-center text-sm">{footer}</div>}
      </div>
    </div>
  );
}
