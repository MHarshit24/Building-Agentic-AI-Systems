import { Outlet } from "react-router-dom";
import { Sidebar } from "../components/layout/Sidebar";

export default function AppShell() {
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      <Sidebar />
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
