import { useEffect, useState } from "react";
import { Badge } from "../ui/badge";

interface ActivityEvent {
  event_id: string;
  event_type: string;
  message: string;
  timestamp: string;
  reason?: string | null;
  artifact_url?: string | null;
}

interface ActivityStreamProps {
  projectId: string;
}

export default function ActivityStream({ projectId }: ActivityStreamProps) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);

  useEffect(() => {
    const stream = new EventSource(`/api/events/${projectId}/sse`);
    stream.onmessage = (event) => {
      const payload = JSON.parse(event.data) as ActivityEvent;
      setEvents((prev) => [payload, ...prev].slice(0, 12));
    };
    return () => stream.close();
  }, [projectId]);

  return (
    <aside className="w-full rounded-2xl border border-white/10 bg-panel p-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Agent Activity Stream</h3>
        <Badge tone="success">Live</Badge>
      </div>
      <div className="mt-4 space-y-4">
        {events.length === 0 ? (
          <p className="text-sm text-white/50">Waiting for activity...</p>
        ) : (
          events.map((event) => (
            <div key={event.event_id} className="space-y-1 border-b border-white/5 pb-3">
              <p className="text-sm text-white">{event.message}</p>
              <p className="text-xs text-white/40">{new Date(event.timestamp).toLocaleString()}</p>
              {event.reason ? <p className="text-xs text-white/50">Reason: {event.reason}</p> : null}
              {event.artifact_url ? (
                <a className="text-xs text-neon" href={event.artifact_url}>
                  View artifact
                </a>
              ) : null}
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
