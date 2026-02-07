import { Link } from "react-router-dom";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import PageShell from "../components/layout/PageShell";

const sampleProjects = [
  {
    id: "alpha",
    name: "Helios OS",
    status: "running",
    environment: "staging",
    lastDeploy: "2h ago",
    health: "Healthy",
    incidents: 0,
    sprint: 0.62
  },
  {
    id: "orion",
    name: "Orion Commerce",
    status: "paused",
    environment: "dev",
    lastDeploy: "1d ago",
    health: "At Risk",
    incidents: 2,
    sprint: 0.38
  }
];

export default function DashboardPage() {
  return (
    <PageShell
      title="Portfolio Dashboard"
      description="All autonomous programs, in one real-time control plane."
      actions={
        <Link to="/new">
          <Button size="sm">New Project</Button>
        </Link>
      }
    >
      <section className="grid gap-6">
        {sampleProjects.map((project) => (
          <div
            key={project.id}
            className="rounded-2xl border border-white/10 bg-panel p-6 shadow-xl"
          >
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">{project.name}</h2>
                <p className="text-sm text-white/50">Environment: {project.environment}</p>
              </div>
              <Badge tone={project.status === "running" ? "success" : "warning"}>
                {project.status}
              </Badge>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4 text-sm text-white/70 md:grid-cols-4">
              <div>
                <p className="text-xs uppercase text-white/40">Last deploy</p>
                <p>{project.lastDeploy}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-white/40">Health</p>
                <p>{project.health}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-white/40">Incidents</p>
                <p>{project.incidents}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-white/40">Sprint Progress</p>
                <p>{Math.round(project.sprint * 100)}%</p>
              </div>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to={`/project/${project.id}`}>
                <Button size="sm">Open</Button>
              </Link>
              <Button size="sm" variant="outline">
                Patch
              </Button>
              <Button size="sm" variant="outline">
                Deploy
              </Button>
              <Button size="sm" variant="outline">
                Pause
              </Button>
              <Button size="sm" variant="outline">
                Resume
              </Button>
            </div>
          </div>
        ))}
      </section>
    </PageShell>
  );
}
