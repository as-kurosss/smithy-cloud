export type WebSocketMessage =
  | { type: "log"; data: ProcessLog }
  | { type: "run_update"; data: ProcessRun };

export interface Process {
  id: string;
  name: string;
  description: string | null;
  entry_point: string;
  files: Record<string, string>;
  requirements: string[];
  created_at: string;
  updated_at: string;
}

export interface Agent {
  id: string;
  name: string;
  url: string;
  status: string;
  last_heartbeat: string | null;
  capabilities: string[];
  created_at: string;
}

export interface ProcessRun {
  id: string;
  process_id: string;
  agent_id: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export interface ProcessLog {
  id: string;
  run_id: string;
  timestamp: string;
  level: string;
  source: string;
  message: string;
  details: Record<string, unknown> | null;
}

export interface ProcessLogEntry extends ProcessLog {
  process_id: string;
  process_name: string;
}

export interface Queue {
  id: string;
  name: string;
  max_attempts: number;
  created_at: string;
}

export interface QueueCounts {
  new: number;
  in_progress: number;
  success: number;
  business_failed: number;
  system_failed: number;
}

export interface QueueWithCounts extends Queue {
  counts: QueueCounts;
}

export interface QueueItemCreated {
  id: string;
  status: string;
  attempts: number;
}
