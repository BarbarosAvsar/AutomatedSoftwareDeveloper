import { Button } from "../components/ui/button";
import PageShell from "../components/layout/PageShell";

export default function NewProjectPage() {
  return (
    <PageShell
      title="New Autonomous Project"
      description="Chat, refine, and launch an autonomous build in minutes."
    >
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-6">
          <section className="rounded-2xl border border-white/10 bg-panel p-6">
            <h2 className="text-lg font-semibold">1. Chat-based Ideation</h2>
            <p className="mt-2 text-sm text-white/60">
              Start with a conversation. The assistant will detect domain, suggest architecture,
              and draft requirements.
            </p>
            <div className="mt-4 space-y-3">
              <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm">
                <p className="text-white/60">User</p>
                <p>We need an AI-native engineering console for autonomous builds.</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm">
                <p className="text-white/60">Assistant</p>
                <p>
                  What platforms should the console manage, and which compliance requirements
                  apply (SOC2, GDPR, HIPAA)?
                </p>
              </div>
              <Button size="sm">Continue Conversation</Button>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-panel p-6">
            <h2 className="text-lg font-semibold">2. Requirements Editor</h2>
            <p className="mt-2 text-sm text-white/60">
              Edit structured requirements. Upload or paste existing specs and refine with AI.
            </p>
            <div className="mt-4 rounded-xl border border-white/10 bg-black/40 p-4 text-sm">
              <p className="text-xs uppercase text-white/40">Requirements Draft</p>
              <ul className="mt-3 space-y-2 text-white/70">
                <li>• Chat-first ideation with clarification questions.</li>
                <li>• Real-time agent activity stream and audit trail.</li>
                <li>• One-click autonomous build launch.</li>
              </ul>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <Button size="sm">Refine with AI</Button>
              <Button size="sm" variant="outline">
                Validate
              </Button>
              <Button size="sm" variant="outline">
                Continue
              </Button>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-panel p-6">
            <h2 className="text-lg font-semibold">3. Plan Preview</h2>
            <p className="mt-2 text-sm text-white/60">
              Review architecture, sprint plan, risks, and costs before launch.
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm">
                <p className="text-xs uppercase text-white/40">Architecture</p>
                <p className="mt-2 text-white/70">Event-driven UI + API + Orchestrator</p>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm">
                <p className="text-xs uppercase text-white/40">Sprint Plan</p>
                <p className="mt-2 text-white/70">3 sprints · 3 weeks · medium confidence</p>
              </div>
            </div>
            <div className="mt-6">
              <Button size="lg" className="glow w-full">
                🚀 Launch Autonomous Build
              </Button>
            </div>
          </section>
        </div>

        <aside className="space-y-6">
          <section className="rounded-2xl border border-white/10 bg-panel p-6">
            <h3 className="text-sm font-semibold">Safety Checks</h3>
            <ul className="mt-4 space-y-3 text-sm text-white/60">
              <li>• Requirements locked before launch.</li>
              <li>• Policy + preauth snapshot stored.</li>
              <li>• Secrets redaction enforced.</li>
            </ul>
          </section>
          <section className="rounded-2xl border border-white/10 bg-panel p-6">
            <h3 className="text-sm font-semibold">Autonomous Build Preview</h3>
            <p className="mt-2 text-sm text-white/60">
              Agents will execute with bounded budgets and safe-by-default guardrails.
            </p>
          </section>
        </aside>
      </div>
    </PageShell>
  );
}
