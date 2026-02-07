import { ReactNode } from "react";
import { Button } from "../ui/button";

interface PageShellProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}

export default function PageShell({ title, description, actions, children }: PageShellProps) {
  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-white/40">Autonomous Engineering Console</p>
          <h1 className="text-3xl font-semibold text-white">{title}</h1>
          {description ? <p className="mt-2 text-white/60">{description}</p> : null}
        </div>
        <div className="flex items-center gap-3">
          {actions}
          <Button variant="outline" size="sm">
            Policy Guardrails
          </Button>
        </div>
      </header>
      {children}
    </div>
  );
}
