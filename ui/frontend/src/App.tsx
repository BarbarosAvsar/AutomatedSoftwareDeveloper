import { Route, Routes } from "react-router-dom";
import DashboardPage from "./pages/Dashboard";
import NewProjectPage from "./pages/NewProject";
import ProjectPage from "./pages/ProjectPage";

export default function App() {
  return (
    <div className="min-h-screen bg-surface text-white">
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/new" element={<NewProjectPage />} />
        <Route path="/project/:projectId" element={<ProjectPage />} />
      </Routes>
    </div>
  );
}
