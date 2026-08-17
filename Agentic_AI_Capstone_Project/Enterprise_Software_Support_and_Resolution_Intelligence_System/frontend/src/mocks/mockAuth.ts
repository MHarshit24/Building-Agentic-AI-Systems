// Structurally JWT-shaped (three base64url segments) mock tokens — not
// signed, never meant to be — so the real app's decodeJwtPayload() (used
// to show "logged in as X") works identically against mock and real
// tokens without any mock-mode branching in app code.

import type { UserResponse } from "../api/types";

interface MockPayload {
  user_id: number;
  role: string;
  email: string;
  exp: number;
  jti: string;
  type: "access" | "refresh";
}

function base64UrlEncode(value: unknown): string {
  const json = JSON.stringify(value);
  const base64 = btoa(unescape(encodeURIComponent(json)));
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlDecode(segment: string): string {
  const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
  return decodeURIComponent(
    atob(padded)
      .split("")
      .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
      .join("")
  );
}

function buildToken(user: UserResponse, type: "access" | "refresh", ttlSeconds: number): string {
  const header = base64UrlEncode({ alg: "none", typ: "JWT" });
  const payload: MockPayload = {
    user_id: user.user_id,
    role: user.role,
    email: user.email,
    exp: Math.floor(Date.now() / 1000) + ttlSeconds,
    jti: crypto.randomUUID(),
    type,
  };
  return `${header}.${base64UrlEncode(payload)}.mocksig`;
}

export function createMockAccessToken(user: UserResponse): string {
  return buildToken(user, "access", 30 * 60);
}

export function createMockRefreshToken(user: UserResponse): string {
  return buildToken(user, "refresh", 7 * 24 * 60 * 60);
}

export function decodeMockToken(token: string): MockPayload | null {
  try {
    const segment = token.split(".")[1];
    if (!segment) return null;
    return JSON.parse(base64UrlDecode(segment)) as MockPayload;
  } catch {
    return null;
  }
}

export function roleFromAuthHeader(request: Request): string | null {
  const header = request.headers.get("Authorization");
  if (!header?.startsWith("Bearer ")) return null;
  return decodeMockToken(header.slice("Bearer ".length))?.role ?? null;
}
