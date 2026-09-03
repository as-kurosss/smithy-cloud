import type { Process, Agent, ProcessRun, ProcessLog } from "./types";

const BASE_URL = "/api";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }

  return res.json() as Promise<T>;
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

// Process WebSocket (channel: process id)
export function connectProcessLogs(
  processId: string,
  onMessage: (msg: { type: string; data: unknown }) => void,
  onClose?: () => void,
): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws/processes/${processId}`);

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
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws/runs/${runId}`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    onMessage(data);
  };

  ws.onclose = () => {
    onClose?.();
  };

  return ws;
}
