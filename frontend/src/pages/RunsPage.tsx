import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Play } from "lucide-react";
import { fetchProcesses, fetchRuns } from "@/lib/api";
import type { Process, ProcessRunEntry } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const STATUSES = [
  "all",
  "pending",
  "dispatched",
  "running",
  "stopping",
  "completed",
  "failed",
  "stopped",
];

export function RunsPage() {
  const [searchParams] = useSearchParams();
  const [processes, setProcesses] = useState<Process[]>([]);
  const [runs, setRuns] = useState<ProcessRunEntry[]>([]);
  const [processId, setProcessId] = useState<string>(
    searchParams.get("process_id") ?? "all",
  );
  const [status, setStatus] = useState<string>("all");
  const [live, setLive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (pid: string, st: string) => {
    try {
      const data = await fetchRuns({
        processId: pid === "all" ? undefined : pid,
        status: st === "all" ? undefined : st,
      });
      setRuns(data);
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
    load(processId, status);
    if (!live) return;
    const timer = setInterval(() => load(processId, status), 10000);
    return () => clearInterval(timer);
  }, [processId, status, live, load]);

  return (
    <div className="space-y-6 animate-enter">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">Runs</h1>
            {!loading && <Badge variant="secondary">{runs.length}</Badge>}
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
            Newest first across all processes — filter by process or status.
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
              load(processId, status);
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
          <label htmlFor="run-process" className="text-sm font-medium">
            Process
          </label>
          <select
            id="run-process"
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
          <label htmlFor="run-status" className="text-sm font-medium">
            Status
          </label>
          <select
            id="run-status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s === "all" ? "All statuses" : s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-xl bg-emerald-900/5"
            />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <Play className="h-7 w-7" />
            </span>
            <div className="space-y-1">
              <p className="font-semibold">No runs yet</p>
              <p className="text-sm text-muted-foreground">
                Open a process and press Run to launch it on an agent.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden py-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-emerald-50/60 hover:bg-emerald-50/60">
                <TableHead>Status</TableHead>
                <TableHead>Process</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Finished</TableHead>
                <TableHead>Error</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runs.map((run) => (
                <TableRow
                  key={run.id}
                  className="transition-colors hover:bg-emerald-50/50"
                >
                  <TableCell>
                    <StatusBadge status={run.status} />
                  </TableCell>
                  <TableCell className="font-medium">
                    <Link
                      to={`/processes/${run.process_id}`}
                      className="hover:underline"
                    >
                      {run.process_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {run.agent_name}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {run.started_at
                      ? new Date(run.started_at).toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {run.finished_at
                      ? new Date(run.finished_at).toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell className="max-w-64 truncate text-xs text-red-500">
                    {run.error ?? ""}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
