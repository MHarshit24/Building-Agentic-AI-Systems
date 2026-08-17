import { NavLink } from "react-router-dom";
import { MessageSquarePlus, FileStack, Gauge, Users, Sparkles, Building2 } from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { ConversationHistoryPanel } from "../conversations/ConversationHistoryPanel";
import { UserMenu } from "./UserMenu";

function navClass(isActive: boolean): string {
  return `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive
      ? "bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-300"
      : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
  }`;
}

export function Sidebar() {
  const role = useAuthStore((s) => s.role);

  return (
    <aside className="flex h-screen w-72 shrink-0 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center gap-2.5 p-4">
        <div className="bg-gradient-brand flex h-8 w-8 shrink-0 items-center justify-center rounded-lg shadow-sm shadow-brand-600/30">
          <Sparkles size={16} className="text-white" />
        </div>
        <h1 className="text-sm font-semibold leading-tight text-slate-900 dark:text-white">
          Enterprise Support
          <br />
          Intelligence
        </h1>
      </div>

      <div className="px-3">
        <NavLink
          to="/"
          end
          className="bg-gradient-brand flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-white shadow-sm shadow-brand-600/20 transition-all hover:shadow-md hover:shadow-brand-600/30 hover:-translate-y-px"
        >
          <MessageSquarePlus size={16} />
          New chat
        </NavLink>
      </div>

      <nav className="mt-3 space-y-0.5 px-3">
        {/* GET /documents and /ingest are admin-only (§16.1); GET /metrics allows support_agent too. */}
        {role === "admin" && (
          <>
            <NavLink to="/documents" className={({ isActive }) => navClass(isActive)}>
              <FileStack size={16} /> Documents
            </NavLink>
            <NavLink to="/users" className={({ isActive }) => navClass(isActive)}>
              <Users size={16} /> Users
            </NavLink>
          </>
        )}
        <NavLink to="/customers" className={({ isActive }) => navClass(isActive)}>
          <Building2 size={16} /> Customers
        </NavLink>
        <NavLink to="/metrics" className={({ isActive }) => navClass(isActive)}>
          <Gauge size={16} /> Metrics
        </NavLink>
      </nav>

      <ConversationHistoryPanel />
      <UserMenu />
    </aside>
  );
}
