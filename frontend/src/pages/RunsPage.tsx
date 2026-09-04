import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Play } from "lucide-react";
import { fetchAgents, fetchProcesses, fetchRuns, runProcess } from "@/lib/api";
import type { Agent, Process, ProcessRunEntry } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMinRole } from "@/lib/auth";
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
  const [agents, setAgents] = useState<Agent[]>([]);
  const [runs, setRuns] = useState<ProcessRunEntry[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [newProcess, setNewProcess] = useState("");
  const [newAgent, setNewAgent] = useState("");
  const [creating, setCreating] = useState(false);
  const canOperator = useMinRole("operator");
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
    async function loadOptions() {
      try {
        const [processList, agentList] = await Promise.all([
          fetchProcesses(),
          fetchAgents(),
        ]);
        setProcesses(processList);
        setAgents(agentList);
        if (processList.length > 0) setNewProcess(processList[0].id);
        if (agentList.length > 0) setNewAgent(agentList[0].id);
      } catch (err) {
        setError(String(err));
      }
    }
    loadOptions();
  }, []);

  useEffect(() => {
    setLoading(true);
    load(processId, status);
    if (!live) return;
    const timer = setInterval(() => load(processId, status), 10000);
    return () => clearInterval(timer);
  }, [processId, status, live, load]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newProcess || !newAgent) return;
    setCreating(true);
    setError(null);
    try {
      await runProcess(newProcess, newAgent);
      setShowCreate(false);
      await load(processId, status);
    } catch (err) {
      setError(String(err));
    } finally {
      setCreating(false);
    }
  }

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
          {canOperator && (
            <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
              {showCreate ? "Cancel" : "New Run"}
            </Button>
          )}
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

      {canOperator && showCreate && (
        <Card>
          <CardHeader>
            <CardTitle>New Run</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label htmlFor="run-new-process" className="text-sm font-medium">
                    Process
                  </label>
                  <select
                    id="run-new-process"
                    value={newProcess}
                    onChange={(e) => setNewProcess(e.target.value)}
                    required
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none"
                  >
                    {processes.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="run-new-agent" className="text-sm font-medium">
                    Agent
                  </label>
                  <select
                    id="run-new-agent"
                    value={newAgent}
                    onChange={(e) => setNewAgent(e.target.value)}
                    required
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none"
                  >
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <Button type="submit" disabled={creating}>
                {creating ? "Starting..." : "Run"}
              </Button>
            </form>
          </CardContent>
        </Card>
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
