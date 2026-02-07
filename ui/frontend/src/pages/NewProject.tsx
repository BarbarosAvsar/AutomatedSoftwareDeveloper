import { Button } from "../components/ui/button";
import ConsoleLayout from "../components/layout/ConsoleLayout";

export default function NewProjectPage() {
  return (
    <ConsoleLayout
      title="Requirements Studio"
      description="Chat, refine, and launch an autonomous build in minutes."
    >
      <div className="space-y-6">
        <section className="rounded-2xl border border-white/10 bg-panel p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">1. Conversational Ideation</h2>
              <p className="mt-2 text-sm text-white/60">
                Discuss the idea in chat or voice. The assistant will clarify ambiguities and
                draft structured requirements.
              </p>
            </div>
            <Button size="sm" variant="outline">
              🎙️ Voice Input
            </Button>
          </div>
          <div className="mt-4 space-y-3">
            <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm">
              <p className="text-white/60">User</p>
              <p>We need an AI-native engineering console for autonomous builds.</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm">
              <p className="text-white/60">Assistant</p>
              <p>
                Which teams will use this, and what compliance requirements apply (SOC2, GDPR,
                HIPAA)?
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button size="sm">Continue Conversation</Button>
              <Button size="sm" variant="outline">
                Upload Requirements
              </Button>
              <Button size="sm" variant="outline">
                Upload Sketch
              </Button>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-panel p-6">
          <h2 className="text-lg font-semibold">2. Requirements Editor</h2>
          <p className="mt-2 text-sm text-white/60">
            Edit structured requirements, validate completeness, and preview the plan.
          </p>
          <div className="mt-4 rounded-xl border border-white/10 bg-black/40 p-4 text-sm">
            <p className="text-xs uppercase text-white/40">Requirements Draft</p>
            <ul className="mt-3 space-y-2 text-white/70">
              <li>• Problem / Goals</li>
              <li>• Functional requirements</li>
              <li>• Non-functional requirements</li>
              <li>• Acceptance criteria</li>
            </ul>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button size="sm">Refine with AI</Button>
            <Button size="sm" variant="outline">
              Validate for completeness
            </Button>
            <Button size="sm" variant="outline">
              Generate Plan Preview
            </Button>
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-panel p-6">
          <h2 className="text-lg font-semibold">3. Plan Preview</h2>
          <p className="mt-2 text-sm text-white/60">
            Review architecture, sprint plan, risks, and ETA range before launch.
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm">
              <p className="text-xs uppercase text-white/40">Architecture</p>
              <p className="mt-2 text-white/70">Event-driven UI + API + Orchestrator</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm">
              <p className="text-xs uppercase text-white/40">ETA Range</p>
              <p className="mt-2 text-white/70">Most likely: 2–4 days · Wide: 1–7 days</p>
            </div>
          </div>
          <div className="mt-6">
            <Button size="lg" className="glow w-full">
              🚀 Approve &amp; Launch Autonomous Build
            </Button>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-panel p-6">
            <h3 className="text-sm font-semibold">Safety Checks</h3>
            <ul className="mt-4 space-y-3 text-sm text-white/60">
              <li>• Requirements locked before launch.</li>
              <li>• Policy + preauth snapshot stored.</li>
              <li>• Secrets redaction enforced.</li>
            </ul>
          </div>
          <div className="rounded-2xl border border-white/10 bg-panel p-6">
            <h3 className="text-sm font-semibold">Privacy &amp; Data</h3>
            <p className="mt-2 text-sm text-white/60">
              Telemetry is OFF by default. Voice processing stays local unless you opt in.
            </p>
          </div>
        </section>
      </div>
    </ConsoleLayout>
  );
}
