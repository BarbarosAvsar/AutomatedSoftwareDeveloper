import { Button } from "../components/ui/button";
import ConsoleLayout from "../components/layout/ConsoleLayout";

type CardData = {
  heading: string;
  description: string;
};

const REQUIREMENTS_ITEMS = [
  "Problem / Goals",
  "Functional requirements",
  "Non-functional requirements",
  "Acceptance criteria",
] as const;

const SAFETY_CHECKS = [
  "Requirements locked before launch.",
  "Policy + preauth snapshot stored.",
  "Secrets redaction enforced.",
] as const;

const SETTINGS_HELP = [
  {
    setting: "Autonomy level",
    explanation:
      "Controls how independently the agent can plan and execute work. Start with Assisted mode if you want approvals before major steps.",
  },
  {
    setting: "Quality gate strictness",
    explanation:
      "Defines how strict lint/type/test checks are before release. Keep this on Strict for production-grade reliability.",
  },
  {
    setting: "Deployment target",
    explanation:
      "Select where builds are shipped (dev, staging, production). Beginners should validate in staging before production.",
  },
  {
    setting: "Telemetry",
    explanation:
      "Telemetry is OFF by default. Enable only if you want operational insights; no user content should be collected.",
  },
] as const;

const PLAN_PREVIEW_CARDS: readonly CardData[] = [
  {
    heading: "Architecture",
    description: "Event-driven UI + API + Orchestrator",
  },
  {
    heading: "ETA Range",
    description: "Most likely: 2–4 days · Wide: 1–7 days",
  },
];

function PreviewCard({ heading, description }: CardData) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/40 p-4 text-sm">
      <p className="text-xs uppercase text-white/40">{heading}</p>
      <p className="mt-2 text-white/70">{description}</p>
    </div>
  );
}

function BulletList({ items }: { items: readonly string[] }) {
  return (
    <ul className="mt-4 space-y-3 text-sm text-white/60">
      {items.map((item) => (
        <li key={item}>• {item}</li>
      ))}
    </ul>
  );
}

export default function NewProjectPage() {
  return (
    <ConsoleLayout
      title="Requirements Studio"
      description="Chat, refine, and launch an autonomous build in minutes."
    >
      <div className="space-y-6">
        <section className="rounded-2xl border border-cyan-300/30 bg-cyan-500/5 p-6">
          <h2 className="text-lg font-semibold">New here? Start with this 90-second guide</h2>
          <ol className="mt-3 space-y-2 text-sm text-white/70">
            <li>1. Describe your idea in plain language (problem, users, and goal).</li>
            <li>2. Let AI suggest requirements, then edit anything inaccurate.</li>
            <li>3. Review plan + risks, then approve launch when it looks right.</li>
          </ol>
          <p className="mt-3 text-xs text-white/50">
            Tip: You can hover over any section title to understand what happens next.
          </p>
        </section>

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
              {REQUIREMENTS_ITEMS.map((item) => (
                <li key={item}>• {item}</li>
              ))}
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
            {PLAN_PREVIEW_CARDS.map((card) => (
              <PreviewCard key={card.heading} {...card} />
            ))}
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
            <BulletList items={SAFETY_CHECKS} />
          </div>
          <div className="rounded-2xl border border-white/10 bg-panel p-6">
            <h3 className="text-sm font-semibold">Privacy &amp; Data</h3>
            <p className="mt-2 text-sm text-white/60">
              Telemetry is OFF by default. Voice processing stays local unless you opt in.
            </p>
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-panel p-6">
          <h3 className="text-sm font-semibold">Settings explained (plain language)</h3>
          <p className="mt-2 text-sm text-white/60">
            Every project option below includes what it does and when to use it.
          </p>
          <div className="mt-4 space-y-3">
            {SETTINGS_HELP.map((item) => (
              <div key={item.setting} className="rounded-xl border border-white/10 bg-black/40 p-4">
                <p className="text-sm font-medium text-white">{item.setting}</p>
                <p className="mt-1 text-sm text-white/65">{item.explanation}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </ConsoleLayout>
  );
}
