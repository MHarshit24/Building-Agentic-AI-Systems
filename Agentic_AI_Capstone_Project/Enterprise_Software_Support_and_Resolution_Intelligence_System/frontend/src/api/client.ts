import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { authStore } from "../store/authStore";
import type { RefreshResponse } from "./types";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const apiClient = axios.create({ baseURL: API_BASE_URL });

apiClient.interceptors.request.use((config) => {
  const token = authStore.getState().accessToken;
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

// Single-flight refresh (approved plan, A2 note): POST /auth/refresh
// rotates the refresh token on every call, so two requests hitting 401
// concurrently can't each independently redeem the same (about-to-be-
// stale) refresh token — the second would genuinely fail. Every
// concurrent 401 awaits this one shared promise instead of triggering
// its own refresh call; it's cleared once the refresh settles (success
// or failure) so the next natural expiry starts a fresh cycle.
let refreshPromise: Promise<string> | null = null;

async function performRefresh(): Promise<string> {
  const { refreshToken, role } = authStore.getState();
  if (!refreshToken || !role) {
    throw new Error("No refresh token available");
  }
  const response = await axios.post<RefreshResponse>(`${API_BASE_URL}/auth/refresh`, {
    refresh_token: refreshToken,
  });
  authStore.setSession(response.data.access_token, response.data.refresh_token, role);
  return response.data.access_token;
}

/** Exported so non-axios callers (chatStream.ts's raw fetch) share the same
 * single-flight dedupe instead of racing their own independent refresh. */
export function getRefreshedAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = performRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retried?: boolean;
}

function isAuthEndpoint(url: string | undefined): boolean {
  return !!url && (url.includes("/auth/login") || url.includes("/auth/refresh"));
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    const status = error.response?.status;

    if (status !== 401 || !original || original._retried || isAuthEndpoint(original.url)) {
      return Promise.reject(error);
    }

    original._retried = true;

    try {
      const newAccessToken = await getRefreshedAccessToken();
      original.headers = original.headers ?? {};
      original.headers.set("Authorization", `Bearer ${newAccessToken}`);
      return apiClient.request(original);
    } catch (refreshError) {
      authStore.clearSession();
      window.location.href = "/login";
      return Promise.reject(refreshError);
    }
  }
);
