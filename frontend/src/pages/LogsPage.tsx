import { useCallback, useEffect, useState } from "react";
import { ScrollText } from "lucide-react";
import { fetchLogs, fetchProcesses } from "@/lib/api";
import type { Process, ProcessLogEntry } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

const levelColors: Record<string, string> = {
  debug: "text-zinc-500",
  info: "text-green-300",
  warning: "text-amber-300",
  error: "text-red-400",
};

const LEVELS = ["all", "debug", "info", "warning", "error"];

export function LogsPage() {
  const [processes, setProcesses] = useState<Process[]>([]);
  const [logs, setLogs] = useState<ProcessLogEntry[]>([]);
  const [processId, setProcessId] = useState<string>("all");
  const [level, setLevel] = useState<string>("all");
  const [live, setLive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (pid: string) => {
    try {
      const data = await fetchLogs(pid === "all" ? undefined : pid);
      setLogs(data);
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProcesses()
      .then(setProcesses)
      .catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    setLoading(true);
    load(processId);
    if (!live) return;
    const timer = setInterval(() => load(processId), 5000);
    return () => clearInterval(timer);
  }, [processId, live, load]);

  const visible =
    level === "all" ? logs : logs.filter((log) => log.level === level);

  return (
    <div className="space-y-6 animate-enter">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">Logs</h1>
            {!loading && <Badge variant="secondary">{visible.length}</Badge>}
            {live && (
              <span className="flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-bold tracking-wide text-emerald-800">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-600" />
                </span>
                LIVE
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Newest first across all runs — filter by process or level.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setLive((v) => !v)}
          >
            {live ? "Pause" : "Resume"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLoading(true);
              load(processId);
            }}
          >
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <div className="space-y-1.5">
          <label htmlFor="log-process" className="text-sm font-medium">
            Process
          </label>
          <select
            id="log-process"
            value={processId}
            onChange={(e) => setProcessId(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="all">All processes</option>
            {processes.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label htmlFor="log-level" className="text-sm font-medium">
            Level
          </label>
          <select
            id="log-level"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {l === "all" ? "All levels" : l}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Card className="overflow-hidden border-emerald-900/20 py-0">
        <CardContent className="p-0">
          <div className="terminal-scroll h-[32rem] overflow-y-auto bg-zinc-950 p-4 font-mono text-xs leading-relaxed">
            {loading ? (
              <div className="text-zinc-500">Loading logs...</div>
            ) : visible.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
                <ScrollText className="h-6 w-6 text-zinc-600" />
                <div className="text-zinc-500">
                  No logs yet — run a process to stream output here.
                </div>
              </div>
            ) : (
              visible.map((log) => (
                <div key={log.id} className="flex gap-3">
                  <span className="shrink-0 text-zinc-500">
                    {new Date(log.timestamp).toLocaleString()}
                  </span>
                  {processId === "all" && (
                    <span className="shrink-0 text-emerald-400">
                      {log.process_name}
                    </span>
                  )}
                  <span className="w-16 shrink-0 text-zinc-400">
                    [{log.level.toUpperCase()}]
                  </span>
                  {log.source && (
                    <span className="shrink-0 text-sky-400">{log.source}</span>
                  )}
                  <span className={levelColors[log.level] ?? "text-green-300"}>
                    {log.message}
                  </span>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
