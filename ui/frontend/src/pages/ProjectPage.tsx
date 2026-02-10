import { useParams } from "react-router-dom";
import ConsoleLayout from "../components/layout/ConsoleLayout";
import ProgressPanel from "../components/ProgressPanel";
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
    <ConsoleLayout
      title={`Project Control Panel · ${resolvedId}`}
      description="Monitor autonomous delivery, agent decisions, and live system health."
      actions={<Badge tone="success">Running</Badge>}
      activityProjectId={resolvedId}
    >
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
              Pause
            </Button>
            <Button size="sm" variant="outline">
              Resume
            </Button>
            <Button size="sm" variant="outline">
              Cancel
            </Button>
          </div>
        </section>

        <ProgressPanel />

        <section className="rounded-2xl border border-white/10 bg-panel p-6">
          <div className="mt-2 grid gap-4 md:grid-cols-3">
            {[
              "Requirements",
              "Planning",
              "Implementation",
              "Verification",
              "Release",
              "Deployment"
            ].map((phase, index) => (
              <div key={phase} className="rounded-xl border border-white/10 bg-black/40 p-4">
                <p className="text-xs uppercase text-white/40">Phase {index + 1}</p>
                <p className="mt-2 text-sm text-white">{phase}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-6 md:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-panel p-6">
            <h3 className="text-sm font-semibold">What’s built so far</h3>
            <ul className="mt-4 space-y-2 text-sm text-white/60">
              <li>• Requirements locked and snapshot saved.</li>
              <li>• Architecture draft created.</li>
              <li>• Sprint backlog initialized.</li>
            </ul>
          </div>
          <div className="rounded-2xl border border-white/10 bg-panel p-6">
            <h3 className="text-sm font-semibold">What’s next</h3>
            <ul className="mt-4 space-y-2 text-sm text-white/60">
              <li>• Implement backlog story #12.</li>
              <li>• Run quality gates and security scan.</li>
              <li>• Prep release artifacts.</li>
            </ul>
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

        <section className="rounded-2xl border border-white/10 bg-panel p-6">
          <h2 className="text-lg font-semibold">Settings Reference</h2>
          <p className="mt-2 text-sm text-white/60">
            Not sure what a control means? Use this quick reference before changing project
            behavior.
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm text-white/70">
              <p className="font-medium text-white">Pause / Resume</p>
              <p className="mt-2">
                Pause stops autonomous actions safely. Resume continues from the latest validated
                state.
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm text-white/70">
              <p className="font-medium text-white">Cancel</p>
              <p className="mt-2">
                Cancel ends the current run and keeps artifacts for audit and restart planning.
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm text-white/70">
              <p className="font-medium text-white">Open Workspace</p>
              <p className="mt-2">
                Opens requirements, backlog, and logs in one place so you can inspect decisions.
              </p>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm text-white/70">
              <p className="font-medium text-white">Status badge</p>
              <p className="mt-2">
                Running means autonomous execution is active. Switch to Pause for manual review.
              </p>
            </div>
          </div>
        </section>
      </div>
    </ConsoleLayout>
  );
}
