import type { Capabilities, CreateSwarmRequest, SwarmDetail } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = API_URL.replace(/^http/, "ws");

export class ApiError extends Error {
  constructor(public status: number, message: string, public missing?: string[]) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers }, cache: "no-store" });
  } catch {
    throw new ApiError(0, `Can't reach the server at ${API_URL}. Start the backend (or npm run mock) and retry.`);
  }
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = (await res.json()).detail;
    } catch {}
    const message = typeof detail === "string" ? detail : (detail as { message?: string } | null)?.message ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, message, (detail as { missing?: string[] } | null)?.missing);
  }
  return res.json() as Promise<T>;
}

export const api = {
  capabilities: () => request<Capabilities>("/api/capabilities"),
  createSwarm: (body: CreateSwarmRequest) => request<{ swarm_id: string }>("/api/swarms", { method: "POST", body: JSON.stringify(body) }),
  listSwarms: () => request<{ id: string; query: string; mode: string; status: string; created_at: number }[]>("/api/swarms?limit=6"),
  getSwarm: (id: string) => request<SwarmDetail>(`/api/swarms/${id}`),
  cancel: (id: string) => request<{ ok: boolean }>(`/api/swarms/${id}/cancel`, { method: "POST" }),
  reserve: (id: string, callId: string) => request<{ ok: boolean; reserve_call_id: string }>(`/api/swarms/${id}/reserve/${callId}`, { method: "POST" }),
};
