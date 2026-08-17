import type { ApiResponse, EventBrief, HealthResponse, PlanResponse, PlanSummary } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.code = code;
    this.name = "ApiError";
  }
}

async function unwrap<T>(response: Response): Promise<T> {
  let body: ApiResponse<T>;
  try {
    body = await response.json();
  } catch {
    throw new ApiError("NETWORK_ERROR", `Request failed with status ${response.status}`);
  }

  if (!body.success || body.data === null) {
    throw new ApiError(body.error?.code ?? "UNKNOWN_ERROR", body.error?.message ?? "Request failed");
  }

  return body.data;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
  return unwrap<HealthResponse>(response);
}

export async function createPlan(brief: EventBrief): Promise<PlanResponse> {
  const response = await fetch(`${API_BASE_URL}/plans`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(brief),
  });
  return unwrap<PlanResponse>(response);
}

export async function getPlan(planId: string): Promise<PlanResponse> {
  const response = await fetch(`${API_BASE_URL}/plans/${planId}`, {
    cache: "no-store",
  });
  return unwrap<PlanResponse>(response);
}

export async function listPlans(): Promise<PlanSummary[]> {
  const response = await fetch(`${API_BASE_URL}/plans`, {
    cache: "no-store",
  });
  return unwrap<PlanSummary[]>(response);
}

export async function refinePlan(
  planId: string,
  instruction: string,
  targetAgents: string[] | null
): Promise<PlanResponse> {
  const response = await fetch(`${API_BASE_URL}/plans/${planId}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction, target_agents: targetAgents }),
  });
  return unwrap<PlanResponse>(response);
}
