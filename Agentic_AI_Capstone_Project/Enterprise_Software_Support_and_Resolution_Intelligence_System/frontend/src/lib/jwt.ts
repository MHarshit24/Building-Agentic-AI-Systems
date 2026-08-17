// Non-verifying JWT payload decode — purely for presentation (showing
// "logged in as X" in the UI). The backend is the only party that ever
// verifies a token's signature; nothing here is a security decision.

export interface AccessTokenPayload {
  user_id: number;
  role: string;
  email: string;
  exp: number;
  jti: string;
  type: "access" | "refresh";
}

export function decodeJwtPayload<T = AccessTokenPayload>(token: string): T | null {
  try {
    const payloadSegment = token.split(".")[1];
    if (!payloadSegment) return null;
    const base64 = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = decodeURIComponent(
      atob(padded)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json) as T;
  } catch {
    return null;
  }
}
