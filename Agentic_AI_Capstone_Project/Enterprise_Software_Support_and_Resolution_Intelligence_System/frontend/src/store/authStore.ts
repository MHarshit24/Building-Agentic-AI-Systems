import { create } from "zustand";
import { decodeJwtPayload } from "../lib/jwt";
import type { UserRole } from "../api/types";

const STORAGE_KEY = "esri_auth";

interface PersistedAuth {
  accessToken: string;
  refreshToken: string;
  role: UserRole;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  role: UserRole | null;
  email: string | null;
  userId: number | null;
  setSession: (accessToken: string, refreshToken: string, role: UserRole) => void;
  clearSession: () => void;
}

function readPersisted(): PersistedAuth | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as PersistedAuth) : null;
  } catch {
    return null;
  }
}

function writePersisted(auth: PersistedAuth | null) {
  if (auth) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

const initial = readPersisted();
const initialPayload = initial ? decodeJwtPayload(initial.accessToken) : null;

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: initial?.accessToken ?? null,
  refreshToken: initial?.refreshToken ?? null,
  role: initial?.role ?? null,
  email: initialPayload?.email ?? null,
  userId: initialPayload?.user_id ?? null,

  setSession: (accessToken, refreshToken, role) => {
    writePersisted({ accessToken, refreshToken, role });
    const payload = decodeJwtPayload(accessToken);
    set({
      accessToken,
      refreshToken,
      role,
      email: payload?.email ?? null,
      userId: payload?.user_id ?? null,
    });
  },

  clearSession: () => {
    writePersisted(null);
    set({ accessToken: null, refreshToken: null, role: null, email: null, userId: null });
  },
}));

// Read/write outside React (for the axios interceptor, which isn't a
// component and can't call the useAuthStore() hook).
export const authStore = {
  getState: useAuthStore.getState,
  setSession: (accessToken: string, refreshToken: string, role: UserRole) =>
    useAuthStore.getState().setSession(accessToken, refreshToken, role),
  clearSession: () => useAuthStore.getState().clearSession(),
};
