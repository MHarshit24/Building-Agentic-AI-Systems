import { apiClient } from "./client";
import type {
  ChatRequest,
  ChatResponse,
  ConversationDetailResponse,
  ConversationListResponse,
  ConversationSummary,
  CustomerListResponse,
  DocumentListResponse,
  HealthResponse,
  IngestDeleteResponse,
  IngestResponse,
  IngestStatusResponse,
  LoginRequest,
  LoginResponse,
  LogoutResponse,
  MetricsResponse,
  PasswordResetConfirmRequest,
  PasswordResetConfirmResponse,
  PasswordResetRequestRequest,
  PasswordResetRequestResponse,
  RegisterRequest,
  UserCreateRequest,
  UserListResponse,
  UserResponse,
  UserUpdateRequest,
} from "./types";

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login", body);
  return data;
}

export async function register(body: RegisterRequest): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/auth/register", body);
  return data;
}

export async function logout(): Promise<LogoutResponse> {
  const { data } = await apiClient.post<LogoutResponse>("/auth/logout");
  return data;
}

export async function requestPasswordReset(
  body: PasswordResetRequestRequest
): Promise<PasswordResetRequestResponse> {
  const { data } = await apiClient.post<PasswordResetRequestResponse>("/auth/password-reset/request", body);
  return data;
}

export async function confirmPasswordReset(
  body: PasswordResetConfirmRequest
): Promise<PasswordResetConfirmResponse> {
  const { data } = await apiClient.post<PasswordResetConfirmResponse>("/auth/password-reset/confirm", body);
  return data;
}

// ---------------------------------------------------------------------------
// Chat (unary fallback — the chat page itself uses chatStream.ts's SSE path)
// ---------------------------------------------------------------------------

export async function sendChatMessage(body: ChatRequest): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>("/chat", body);
  return data;
}

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

export async function listConversations(params?: {
  limit?: number;
  offset?: number;
  include_archived?: boolean;
}): Promise<ConversationListResponse> {
  const { data } = await apiClient.get<ConversationListResponse>("/conversations", { params });
  return data;
}

export async function getConversation(conversationId: string): Promise<ConversationDetailResponse> {
  const { data } = await apiClient.get<ConversationDetailResponse>(`/conversations/${conversationId}`);
  return data;
}

export async function archiveConversation(conversationId: string): Promise<ConversationSummary> {
  const { data } = await apiClient.post<ConversationSummary>(`/conversations/${conversationId}/archive`);
  return data;
}

export async function unarchiveConversation(conversationId: string): Promise<ConversationSummary> {
  const { data } = await apiClient.post<ConversationSummary>(`/conversations/${conversationId}/unarchive`);
  return data;
}

// ---------------------------------------------------------------------------
// Customers
// ---------------------------------------------------------------------------

export async function listCustomers(params?: { search?: string }): Promise<CustomerListResponse> {
  const { data } = await apiClient.get<CustomerListResponse>("/customers", { params });
  return data;
}

// ---------------------------------------------------------------------------
// Ingest / Documents
// ---------------------------------------------------------------------------

export async function ingestDocument(
  file: File,
  meta?: { doc_title?: string; product_version?: string; category?: string }
): Promise<IngestResponse> {
  const form = new FormData();
  form.append("file", file);
  if (meta?.doc_title) form.append("doc_title", meta.doc_title);
  if (meta?.product_version) form.append("product_version", meta.product_version);
  if (meta?.category) form.append("category", meta.category);

  const { data } = await apiClient.post<IngestResponse>("/ingest", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getIngestStatus(jobId: string): Promise<IngestStatusResponse> {
  const { data } = await apiClient.get<IngestStatusResponse>(`/ingest/${jobId}`);
  return data;
}

export async function deleteDocument(documentId: string): Promise<IngestDeleteResponse> {
  const { data } = await apiClient.delete<IngestDeleteResponse>(`/ingest/${documentId}`);
  return data;
}

export async function listDocuments(): Promise<DocumentListResponse> {
  const { data } = await apiClient.get<DocumentListResponse>("/documents");
  return data;
}

// ---------------------------------------------------------------------------
// Users (admin management)
// ---------------------------------------------------------------------------

export async function listUsers(params?: {
  limit?: number;
  offset?: number;
  role?: string;
  is_active?: boolean;
}): Promise<UserListResponse> {
  const { data } = await apiClient.get<UserListResponse>("/users", { params });
  return data;
}

export async function createUser(body: UserCreateRequest): Promise<UserResponse> {
  const { data } = await apiClient.post<UserResponse>("/users", body);
  return data;
}

export async function updateUser(userId: number, body: UserUpdateRequest): Promise<UserResponse> {
  const { data } = await apiClient.patch<UserResponse>(`/users/${userId}`, body);
  return data;
}

export async function deactivateUser(userId: number): Promise<UserResponse> {
  const { data } = await apiClient.post<UserResponse>(`/users/${userId}/deactivate`);
  return data;
}

export async function reactivateUser(userId: number): Promise<UserResponse> {
  const { data } = await apiClient.post<UserResponse>(`/users/${userId}/reactivate`);
  return data;
}

// ---------------------------------------------------------------------------
// Metrics / Health
// ---------------------------------------------------------------------------

export async function getMetrics(): Promise<MetricsResponse> {
  const { data } = await apiClient.get<MetricsResponse>("/metrics");
  return data;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>("/health");
  return data;
}
