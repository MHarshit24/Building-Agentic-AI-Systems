import { useState } from "react";
import { LogOut, ChevronUp } from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { logout } from "../../api/endpoints";
import { Badge } from "../ui/Badge";

export function UserMenu() {
  const [open, setOpen] = useState(false);
  const email = useAuthStore((s) => s.email);
  const role = useAuthStore((s) => s.role);
  const clearSession = useAuthStore((s) => s.clearSession);

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // Logout still proceeds client-side even if the backend call fails
      // (e.g. token already expired) — there's nothing meaningful to
      // retry here, and staying "logged in" locally would be worse.
    }
    clearSession();
    // A hard redirect, not react-router's navigate(). Found via QA browser
    // testing: an SPA navigate() here races React's own scheduling —
    // zustand's useSyncExternalStore-driven re-render of ProtectedRoute
    // (seeing accessToken already null) can commit BEFORE react-router's
    // own internal state catches up to the new location, so
    // ProtectedRoute's OWN guard redirect fires first with
    // state={{from: location}} still pointing at whatever conversation
    // was on screen — meaning the NEXT login (even as a different user)
    // landed back on the PREVIOUS session's conversation instead of "/".
    // Reordering clearSession()/navigate() didn't fix it (verified) since
    // the race is between two independent subscription systems, not call
    // order in this function. A full page reload sidesteps the entire
    // category of bug: it discards all in-memory router state, matching
    // the same pattern api/client.ts's refresh-failure path already uses.
    window.location.href = "/login";
  };

  return (
    <div className="relative border-t border-slate-200 p-3 dark:border-slate-700">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 rounded-lg p-2 text-left transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
      >
        <div className="bg-gradient-brand flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold text-white shadow-sm shadow-brand-600/30">
          {email ? email[0]!.toUpperCase() : "?"}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-900 dark:text-white">{email ?? "Unknown user"}</p>
          {role && (
            <Badge tone={role === "admin" ? "info" : "neutral"} className="mt-0.5">
              {role === "admin" ? "Admin" : "Support Agent"}
            </Badge>
          )}
        </div>
        <ChevronUp size={16} className={`shrink-0 text-slate-400 transition-transform ${open ? "" : "rotate-180"}`} />
      </button>

      {open && (
        <button
          type="button"
          onClick={handleLogout}
          className="mt-1 flex w-full items-center gap-2 rounded-lg p-2 text-left text-sm text-red-600 transition-colors hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
        >
          <LogOut size={16} />
          Sign out
        </button>
      )}
    </div>
  );
}
