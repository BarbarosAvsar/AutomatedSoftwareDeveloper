import { useParams } from "react-router-dom";
import ActivityStream from "../components/layout/ActivityStream";
import PageShell from "../components/layout/PageShell";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";

const tabs = [
  "Overview",
  "Backlog",
  "Sprints",
  "Agents",
  "Deployments",
  "Incidents",
  "Metrics",
  "Logs",
  "Settings"
];

export default function ProjectPage() {
  const { projectId } = useParams();
  const resolvedId = projectId ?? "alpha";

  return (
    <PageShell
      title={`Project Control Panel · ${resolvedId}`}
      description="Monitor autonomous delivery, agent decisions, and live system health."
      actions={<Badge tone="success">Running</Badge>}
    >
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <section className="rounded-2xl border border-white/10 bg-panel p-6">
            <div className="flex flex-wrap items-center gap-3">
              {tabs.map((tab) => (
                <button
                  key={tab}
                  className="rounded-full border border-white/10 px-4 py-2 text-sm text-white/60 hover:text-white"
                >
                  {tab}
                </button>
              ))}
            </div>
            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                <p className="text-xs uppercase text-white/40">Last Commit</p>
                <p className="mt-2 text-sm text-white">feat: enable autonomous UI console</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                <p className="text-xs uppercase text-white/40">Environment</p>
                <p className="mt-2 text-sm text-white">Staging · v0.1.0</p>
              </div>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button size="sm">Open Workspace</Button>
              <Button size="sm" variant="outline">
                Rollback
              </Button>
              <Button size="sm" variant="outline">
                Promote
              </Button>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-panel p-6">
            <h2 className="text-lg font-semibold">Live Logs</h2>
            <div className="mt-3 space-y-2 text-sm text-white/60">
              <p>[10:42] ENG · Implementing story #23</p>
              <p>[10:43] OPS · Deploying staging</p>
              <p>[10:44] SEC · Scanning dependencies</p>
            </div>
          </section>
        </div>

        <ActivityStream projectId={resolvedId} />
      </div>
    </PageShell>
  );
}
