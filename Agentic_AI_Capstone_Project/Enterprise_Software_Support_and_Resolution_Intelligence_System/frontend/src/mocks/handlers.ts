import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "../api/client";
import {
  MOCK_CONVERSATIONS,
  MOCK_CONVERSATION_DETAILS,
  MOCK_CUSTOMERS,
  MOCK_DOCUMENTS,
  MOCK_METRICS,
  MOCK_USERS_BY_EMAIL,
  getMockAllUsers,
} from "./fixtures";
import { mockChatStreamBody } from "./chatStreamMock";
import { createMockAccessToken, createMockRefreshToken, decodeMockToken, roleFromAuthHeader } from "./mockAuth";
import type {
  ChatRequest,
  ConversationSummary,
  LoginRequest,
  RefreshRequest,
  RegisterRequest,
} from "../api/types";

function requireRole(request: Request, allowed: string[]): HttpResponse<Record<string, unknown>> | null {
  const role = roleFromAuthHeader(request);
  if (!role) {
    return HttpResponse.json({ detail: "Not authenticated" }, { status: 401 });
  }
  if (!allowed.includes(role)) {
    return HttpResponse.json({ detail: "Forbidden" }, { status: 403 });
  }
  return null;
}

// job_id -> number of times polled — simulates pending -> processing ->
// completed so IngestJobRow's progress UI has something real to show.
const ingestJobPolls = new Map<string, number>();

function slugify(filename: string): string {
  return filename.toLowerCase().replace(/\.[^.]+$/, "").replace(/[^a-z0-9]+/g, "_");
}

export const handlers = [
  http.post(`${API_BASE_URL}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as LoginRequest;
    const entry = MOCK_USERS_BY_EMAIL[body.email.toLowerCase()];
    if (!entry || entry.password !== body.password) {
      return HttpResponse.json({ detail: "Invalid email or password" }, { status: 401 });
    }
    return HttpResponse.json({
      access_token: createMockAccessToken(entry.user),
      refresh_token: createMockRefreshToken(entry.user),
      role: entry.user.role,
      expires_in: 1800,
    });
  }),

  http.post(`${API_BASE_URL}/auth/register`, async ({ request }) => {
    const body = (await request.json()) as RegisterRequest;
    const email = body.email.toLowerCase();
    if (MOCK_USERS_BY_EMAIL[email]) {
      return HttpResponse.json({ detail: "A user with this email already exists" }, { status: 409 });
    }
    if (body.password.length < 8) {
      return HttpResponse.json({ detail: "Password must be at least 8 characters" }, { status: 422 });
    }
    const nextId = Math.max(0, ...getMockAllUsers().map((u) => u.user_id)) + 1;
    const newUser = {
      user_id: nextId,
      email,
      role: "support_agent" as const,
      is_active: true,
      created_at: new Date().toISOString(),
      last_login_at: new Date().toISOString(),
    };
    // Mutates the module-level fixture record directly — same "in-memory,
    // session-lifetime" mutability already used by MOCK_CONVERSATIONS'
    // archive/unarchive handlers above, so a newly registered account can
    // immediately log in and (if made admin later) be listed via /users.
    MOCK_USERS_BY_EMAIL[email] = { password: body.password, user: newUser };

    return HttpResponse.json(
      {
        access_token: createMockAccessToken(newUser),
        refresh_token: createMockRefreshToken(newUser),
        role: newUser.role,
        expires_in: 1800,
      },
      { status: 201 }
    );
  }),

  http.post(`${API_BASE_URL}/auth/logout`, () => HttpResponse.json({ status: "logged_out" })),

  http.post(`${API_BASE_URL}/auth/refresh`, async ({ request }) => {
    const body = (await request.json()) as RefreshRequest;
    const payload = decodeMockToken(body.refresh_token);
    if (!payload || payload.type !== "refresh") {
      return HttpResponse.json({ detail: "Invalid or expired refresh token" }, { status: 401 });
    }
    const user = getMockAllUsers().find((u) => u.user_id === payload.user_id);
    if (!user) {
      return HttpResponse.json({ detail: "Invalid or expired refresh token" }, { status: 401 });
    }
    return HttpResponse.json({
      access_token: createMockAccessToken(user),
      refresh_token: createMockRefreshToken(user),
      expires_in: 1800,
    });
  }),

  http.post(`${API_BASE_URL}/auth/password-reset/request`, () =>
    HttpResponse.json({ message: "If an account exists for that email, a reset link has been sent." }, { status: 202 })
  ),

  http.post(`${API_BASE_URL}/auth/password-reset/confirm`, () => HttpResponse.json({ status: "password_reset" })),

  http.post(`${API_BASE_URL}/chat/stream`, async ({ request }) => {
    const denied = requireRole(request, ["support_agent", "admin"]);
    if (denied) return denied;
    const body = (await request.json()) as ChatRequest;
    return new HttpResponse(mockChatStreamBody(body), {
      headers: { "Content-Type": "text/event-stream" },
    });
  }),

  http.get(`${API_BASE_URL}/conversations`, ({ request }) => {
    const denied = requireRole(request, ["support_agent", "admin"]);
    if (denied) return denied;
    const url = new URL(request.url);
    const includeArchived = url.searchParams.get("include_archived") === "true";
    const conversations = MOCK_CONVERSATIONS.filter((c) => includeArchived || c.status !== "archived");
    return HttpResponse.json({ conversations });
  }),

  http.get(`${API_BASE_URL}/conversations/:id`, ({ request, params }) => {
    const denied = requireRole(request, ["support_agent", "admin"]);
    if (denied) return denied;
    const detail = MOCK_CONVERSATION_DETAILS[params.id as string];
    if (!detail) return HttpResponse.json({ detail: "Conversation not found" }, { status: 404 });
    return HttpResponse.json(detail);
  }),

  http.post(`${API_BASE_URL}/conversations/:id/archive`, ({ request, params }) => {
    const denied = requireRole(request, ["support_agent", "admin"]);
    if (denied) return denied;
    const conversation = MOCK_CONVERSATIONS.find((c) => c.conversation_id === params.id);
    if (!conversation) return HttpResponse.json({ detail: "Conversation not found" }, { status: 404 });
    const updated: ConversationSummary = { ...conversation, status: "archived" };
    Object.assign(conversation, updated);
    return HttpResponse.json(conversation);
  }),

  http.post(`${API_BASE_URL}/conversations/:id/unarchive`, ({ request, params }) => {
    const denied = requireRole(request, ["support_agent", "admin"]);
    if (denied) return denied;
    const conversation = MOCK_CONVERSATIONS.find((c) => c.conversation_id === params.id);
    if (!conversation || conversation.status !== "archived") {
      return HttpResponse.json({ detail: "Conversation is not archived" }, { status: 400 });
    }
    conversation.status = "open";
    return HttpResponse.json(conversation);
  }),

  http.get(`${API_BASE_URL}/customers`, ({ request }) => {
    const denied = requireRole(request, ["support_agent", "admin"]);
    if (denied) return denied;
    const url = new URL(request.url);
    const search = url.searchParams.get("search")?.toLowerCase();
    const customers = search
      ? MOCK_CUSTOMERS.filter((c) => c.company_name.toLowerCase().includes(search))
      : MOCK_CUSTOMERS;
    return HttpResponse.json({ customers, total: customers.length });
  }),

  http.get(`${API_BASE_URL}/documents`, ({ request }) => {
    const denied = requireRole(request, ["admin"]);
    if (denied) return denied;
    return HttpResponse.json({ documents: MOCK_DOCUMENTS });
  }),

  http.post(`${API_BASE_URL}/ingest`, async ({ request }) => {
    const denied = requireRole(request, ["admin"]);
    if (denied) return denied;
    const form = await request.formData();
    const file = form.get("file");
    const filename = file instanceof File ? file.name : "uploaded_document.pdf";
    const jobId = `job_${slugify(filename)}_${Math.random().toString(16).slice(2, 8)}`;
    ingestJobPolls.set(jobId, 0);
    return HttpResponse.json({ job_id: jobId, status: "pending" }, { status: 202 });
  }),

  http.get(`${API_BASE_URL}/ingest/:jobId`, ({ request, params }) => {
    const denied = requireRole(request, ["admin"]);
    if (denied) return denied;
    const jobId = params.jobId as string;
    const polls = (ingestJobPolls.get(jobId) ?? 0) + 1;
    ingestJobPolls.set(jobId, polls);

    const status = polls === 1 ? "pending" : polls === 2 ? "processing" : "completed";
    return HttpResponse.json({
      job_id: jobId,
      document_id: jobId.replace(/^job_/, "").replace(/_[a-f0-9]{6}$/, ""),
      status,
      stats:
        status === "completed"
          ? { assets_new: 14, assets_unchanged_skipped: 0, assets_updated: 0, assets_retired: 0 }
          : null,
    });
  }),

  http.delete(`${API_BASE_URL}/ingest/:documentId`, ({ request, params }) => {
    const denied = requireRole(request, ["admin"]);
    if (denied) return denied;
    return HttpResponse.json({ document_id: params.documentId, assets_retired: 4 });
  }),

  http.get(`${API_BASE_URL}/metrics`, ({ request }) => {
    const denied = requireRole(request, ["support_agent", "admin"]);
    if (denied) return denied;
    return HttpResponse.json(MOCK_METRICS);
  }),

  http.get(`${API_BASE_URL}/users`, ({ request }) => {
    const denied = requireRole(request, ["admin"]);
    if (denied) return denied;
    const users = getMockAllUsers();
    return HttpResponse.json({ users, total: users.length });
  }),

  http.post(`${API_BASE_URL}/users`, async ({ request }) => {
    const denied = requireRole(request, ["admin"]);
    if (denied) return denied;
    const body = (await request.json()) as { email: string; password: string; role: "support_agent" | "admin" };
    const email = body.email.toLowerCase();
    if (MOCK_USERS_BY_EMAIL[email]) {
      return HttpResponse.json({ detail: "A user with this email already exists" }, { status: 409 });
    }
    const nextId = Math.max(0, ...getMockAllUsers().map((u) => u.user_id)) + 1;
    const newUser = {
      user_id: nextId,
      email,
      role: body.role,
      is_active: true,
      created_at: new Date().toISOString(),
      last_login_at: null,
    };
    MOCK_USERS_BY_EMAIL[email] = { password: body.password, user: newUser };
    return HttpResponse.json(newUser, { status: 201 });
  }),

  http.patch(`${API_BASE_URL}/users/:userId`, async ({ request, params }) => {
    const denied = requireRole(request, ["admin"]);
    if (denied) return denied;
    const requesterId = decodeMockToken(request.headers.get("Authorization")?.slice("Bearer ".length) ?? "")?.user_id;
    const userId = Number(params.userId);
    const entry = Object.values(MOCK_USERS_BY_EMAIL).find((e) => e.user.user_id === userId);
    if (!entry) return HttpResponse.json({ detail: "User not found" }, { status: 404 });

    const body = (await request.json()) as { email?: string; role?: "support_agent" | "admin" };
    const isDemotion = body.role != null && body.role !== "admin" && entry.user.role === "admin";
    if (isDemotion && requesterId === userId) {
      return HttpResponse.json({ detail: "Cannot demote or deactivate your own account" }, { status: 400 });
    }
    if (isDemotion) {
      const activeAdmins = getMockAllUsers().filter((u) => u.role === "admin" && u.is_active).length;
      if (activeAdmins <= 1) {
        return HttpResponse.json({ detail: "Cannot remove the last remaining active admin account" }, { status: 400 });
      }
    }
    if (body.email) entry.user.email = body.email.toLowerCase();
    if (body.role) entry.user.role = body.role;
    return HttpResponse.json(entry.user);
  }),

  http.post(`${API_BASE_URL}/users/:userId/deactivate`, ({ request, params }) => {
    const denied = requireRole(request, ["admin"]);
    if (denied) return denied;
    const requesterId = decodeMockToken(request.headers.get("Authorization")?.slice("Bearer ".length) ?? "")?.user_id;
    const userId = Number(params.userId);
    const entry = Object.values(MOCK_USERS_BY_EMAIL).find((e) => e.user.user_id === userId);
    if (!entry) return HttpResponse.json({ detail: "User not found" }, { status: 404 });
    if (requesterId === userId) {
      return HttpResponse.json({ detail: "Cannot demote or deactivate your own account" }, { status: 400 });
    }
    if (entry.user.role === "admin") {
      const activeAdmins = getMockAllUsers().filter((u) => u.role === "admin" && u.is_active).length;
      if (activeAdmins <= 1) {
        return HttpResponse.json({ detail: "Cannot remove the last remaining active admin account" }, { status: 400 });
      }
    }
    entry.user.is_active = false;
    return HttpResponse.json(entry.user);
  }),

  http.post(`${API_BASE_URL}/users/:userId/reactivate`, ({ request, params }) => {
    const denied = requireRole(request, ["admin"]);
    if (denied) return denied;
    const userId = Number(params.userId);
    const entry = Object.values(MOCK_USERS_BY_EMAIL).find((e) => e.user.user_id === userId);
    if (!entry) return HttpResponse.json({ detail: "User not found" }, { status: 404 });
    entry.user.is_active = true;
    return HttpResponse.json(entry.user);
  }),

  http.get(`${API_BASE_URL}/health`, () =>
    HttpResponse.json({ status: "ok", postgres: "ok", redis: "ok", azure_openai: "skipped (mock provider)" })
  ),
];
