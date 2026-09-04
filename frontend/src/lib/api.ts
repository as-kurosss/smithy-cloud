import type {
  Process,
  Agent,
  ProcessRun,
  ProcessLog,
  ProcessLogEntry,
  Queue,
  QueueWithCounts,
  QueueItemCreated,
  Trigger,
} from "./types";

const BASE_URL = "/api";

const ACCESS_KEY = "smithy.access_token";
const REFRESH_KEY = "smithy.refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return false;
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as TokenPair;
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function request<T>(url: string, options?: RequestInit, retry = true): Promise<T> {
  const token = getAccessToken();
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    ...options,
  });

  if (res.status === 401 && retry && !url.startsWith("/auth/")) {
    if (await refreshAccessToken()) {
      return request<T>(url, options, false);
    }
    clearTokens();
  }

  // DELETE endpoints answer 204 with an empty body — there is nothing to parse.
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${text}`);
  }
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

// Auth

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthUser {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export function fetchAuthStatus(): Promise<{ auth_enabled: boolean }> {
  return request<{ auth_enabled: boolean }>("/auth/status");
}

export async function loginUser(email: string, password: string): Promise<TokenPair> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    throw new Error(`Login failed (${res.status}): ${await res.text()}`);
  }
  const data = (await res.json()) as TokenPair;
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function registerUser(email: string, password: string): Promise<TokenPair> {
  const data = await request<TokenPair>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export function fetchMe(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}

export async function logoutUser(): Promise<void> {
  const refresh = localStorage.getItem(REFRESH_KEY);
  try {
    if (refresh) {
      await request("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh }),
      });
    }
  } finally {
    clearTokens();
  }
}

// Processes
export function fetchProcesses(): Promise<Process[]> {
  return request<Process[]>("/processes");
}

export function getProcess(id: string): Promise<Process> {
  return request<Process>(`/processes/${id}`);
}

export function createProcess(payload: Omit<Process, "id" | "created_at" | "updated_at">): Promise<Process> {
  return request<Process>("/processes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateProcess(id: string, payload: Partial<Omit<Process, "id" | "created_at" | "updated_at">>): Promise<Process> {
  return request<Process>(`/processes/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteProcess(id: string): Promise<void> {
  return request<void>(`/processes/${id}`, { method: "DELETE" });
}

export function fetchProcessRuns(processId: string): Promise<ProcessRun[]> {
  return request<ProcessRun[]>(`/processes/${processId}/runs`);
}

export function fetchProcessLogs(processId: string): Promise<ProcessLog[]> {
  return request<ProcessLog[]>(`/processes/${processId}/logs`);
}

export function fetchLogs(processId?: string, limit = 200): Promise<ProcessLogEntry[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (processId) params.set("process_id", processId);
  return request<ProcessLogEntry[]>(`/logs?${params.toString()}`);
}

// Agents
export function fetchAgents(): Promise<Agent[]> {
  return request<Agent[]>("/agents");
}

export function createAgent(payload: Omit<Agent, "id" | "status" | "last_heartbeat" | "capabilities" | "created_at">): Promise<Agent> {
  return request<Agent>("/agents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteAgent(id: string): Promise<void> {
  return request<void>(`/agents/${id}`, { method: "DELETE" });
}

// Queues (transactional, REFramework-style)
export function fetchQueues(): Promise<QueueWithCounts[]> {
  return request<QueueWithCounts[]>("/queues");
}

export function createQueue(payload: {
  name: string;
  max_attempts: number;
}): Promise<Queue> {
  return request<Queue>("/queues", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function addQueueItems(
  name: string,
  items: Array<{
    payload: Record<string, unknown>;
    idempotency_key?: string | null;
  }>,
): Promise<QueueItemCreated[]> {
  return request<QueueItemCreated[]>(`/queues/${encodeURIComponent(name)}/items`, {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

export function deleteQueue(name: string): Promise<void> {
  return request<void>(`/queues/${encodeURIComponent(name)}`, { method: "DELETE" });
}

// Triggers (one-shot or recurring scheduled runs)
export function fetchTriggers(): Promise<Trigger[]> {
  return request<Trigger[]>("/triggers");
}

export function createTrigger(payload: {
  name: string;
  agent_id: string;
  process_id: string;
  run_at: string;
  enabled?: boolean;
  repeat?: Trigger["repeat"];
  repeat_interval_hours?: number;
  days_of_week?: number[];
}): Promise<Trigger> {
  return request<Trigger>("/triggers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTrigger(
  id: string,
  payload: { enabled?: boolean; run_at?: string },
): Promise<Trigger> {
  return request<Trigger>(`/triggers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteTrigger(id: string): Promise<void> {
  return request<void>(`/triggers/${id}`, { method: "DELETE" });
}

// Deployment & Run
export function deployProcess(processId: string, agentId: string): Promise<void> {
  return request<void>(`/processes/${processId}/deploy`, {
    method: "POST",
    body: JSON.stringify({ agent_id: agentId }),
  });
}

export function runProcess(processId: string, agentId: string): Promise<ProcessRun> {
  return request<ProcessRun>(`/processes/${processId}/run`, {
    method: "POST",
    body: JSON.stringify({ agent_id: agentId }),
  });
}

export function stopProcess(processId: string): Promise<void> {
  return request<void>(`/processes/${processId}/stop`, { method: "POST" });
}

function wsUrl(path: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const token = getAccessToken();
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${protocol}//${window.location.host}${path}${query}`;
}

// Process WebSocket (channel: process id)
export function connectProcessLogs(
  processId: string,
  onMessage: (msg: { type: string; data: unknown }) => void,
  onClose?: () => void,
): WebSocket {
  const ws = new WebSocket(wsUrl(`/ws/processes/${processId}`));

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };

  ws.onclose = () => {
    onClose?.();
  };

  return ws;
}

// Run WebSocket (channel: run id)
export function connectRunLogs(
  runId: string,
  onMessage: (msg: { type: string; data: unknown }) => void,
  onClose?: () => void,
): WebSocket {
  const ws = new WebSocket(wsUrl(`/ws/runs/${runId}`));

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };

  ws.onclose = () => {
    onClose?.();
  };

  return ws;
}
