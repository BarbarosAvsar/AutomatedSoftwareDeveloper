import { useEffect, useState } from "react";
import { Badge } from "./ui/badge";

interface ProgressPanelProps {
  initialPercent?: number;
}

export default function ProgressPanel({ initialPercent = 40 }: ProgressPanelProps) {
  const [percent, setPercent] = useState(initialPercent);

  useEffect(() => {
    const handler = (event: Event) => {
      if (!(event instanceof CustomEvent)) {
        return;
      }
      const next = event.detail?.percent;
      if (typeof next === "number" && next >= 0 && next <= 100) {
        setPercent(next);
      }
    };
    window.addEventListener("aec-progress", handler);
    return () => window.removeEventListener("aec-progress", handler);
  }, []);

  return (
    <section className="rounded-2xl border border-white/10 bg-panel p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Build Run Progress</h2>
        <Badge tone="success">Running</Badge>
      </div>
      <div className="mt-4">
        <div className="h-3 w-full rounded-full bg-white/10">
          <div
            className="h-3 rounded-full bg-neon transition-all"
            style={{ width: `${percent}%` }}
          />
        </div>
        <div className="mt-3 flex flex-wrap justify-between text-xs text-white/50">
          <span>Most likely: 2–4 days</span>
          <span>Wide range: 1–7 days · Confidence: Medium</span>
        </div>
      </div>
      <p className="mt-3 text-xs text-white/40">Progress: {percent.toFixed(0)}%</p>
    </section>
  );
}
