import { ReactNode } from "react";
import { Link } from "react-router-dom";
import ActivityStream from "./ActivityStream";
import { Button } from "../ui/button";

interface ConsoleLayoutProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  activityProjectId?: string;
  children: ReactNode;
}

const navigationItems = [
  { label: "Portfolio", href: "/" },
  { label: "New Project", href: "/new" },
  { label: "Requirements Studio", href: "/requirements" },
  { label: "Sprints", href: "/project/alpha" },
  { label: "Deployments", href: "/project/alpha" },
  { label: "Incidents", href: "/project/alpha" },
  { label: "Metrics", href: "/project/alpha" },
  { label: "Plugins", href: "/project/alpha" },
  { label: "Settings", href: "/project/alpha" }
];

export default function ConsoleLayout({
  title,
  description,
  actions,
  activityProjectId,
  children
}: ConsoleLayoutProps) {
  return (
    <div className="min-h-screen bg-surface text-white">
      <div className="flex min-h-screen">
        <aside className="hidden w-64 flex-col border-r border-white/10 bg-panel/40 p-6 lg:flex">
          <p className="text-xs uppercase tracking-[0.3em] text-white/40">AEC</p>
          <h2 className="mt-3 text-lg font-semibold text-white">Autonomous Console</h2>
          <nav className="mt-8 space-y-2 text-sm text-white/60">
            {navigationItems.map((item) => (
              <Link
                key={item.label}
                to={item.href}
                className="block rounded-xl px-3 py-2 transition hover:bg-white/5 hover:text-white"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="mt-auto space-y-3 pt-6 text-xs text-white/50">
            <p>Telemetry: OFF</p>
            <p>Policy: Safe-by-default</p>
          </div>
        </aside>

        <div className="flex flex-1 flex-col">
          <header className="flex flex-col gap-4 border-b border-white/10 bg-panel/30 px-6 py-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="rounded-full border border-white/10 px-3 py-1 text-xs text-white/60">
                  Project: Helios OS
                </div>
                <div className="hidden items-center gap-2 rounded-full border border-white/10 px-3 py-1 text-xs text-white/60 md:flex">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  Live monitoring
                </div>
              </div>
              <div className="flex items-center gap-3">
                <input
                  className="h-9 w-56 rounded-full border border-white/10 bg-black/30 px-3 text-sm text-white/80 placeholder:text-white/30"
                  placeholder="Search projects, runs, artifacts..."
                />
                {actions}
                <Button size="sm" variant="outline">
                  Policy Guardrails
                </Button>
              </div>
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-white">{title}</h1>
              {description ? <p className="mt-1 text-sm text-white/60">{description}</p> : null}
            </div>
          </header>

          <main className="flex flex-1 flex-col gap-6 px-6 py-6 lg:flex-row">
            <section className="flex-1">{children}</section>
            <aside className="w-full lg:w-[320px]">
              {activityProjectId ? (
                <ActivityStream projectId={activityProjectId} />
              ) : (
                <div className="rounded-2xl border border-white/10 bg-panel p-5">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold">Live Activity</h3>
                    <span className="text-xs text-white/40">Idle</span>
                  </div>
                  <p className="mt-4 text-sm text-white/50">
                    Connect to a running project to view real-time agent events.
                  </p>
                </div>
              )}
            </aside>
          </main>
        </div>
      </div>
    </div>
  );
}
