import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getProcess,
  fetchAgents,
  deployProcess,
  runProcess,
  stopProcess,
  fetchProcessRuns,
  connectProcessLogs,
} from "@/lib/api";
import type { Process, Agent, ProcessRun, ProcessLog } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

const statusStyles: Record<string, string> = {
  pending: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400 border-yellow-500/30",
  running: "bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30",
  completed: "bg-green-500/15 text-green-600 dark:text-green-400 border-green-500/30",
  failed: "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30",
  stopped: "bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/30",
};

const levelColors: Record<string, string> = {
  debug: "text-muted-foreground",
  info: "text-foreground",
  warning: "text-yellow-500",
  error: "text-red-500",
};

export function ProcessDetail() {
  const { id } = useParams<{ id: string }>();
  const [process, setProcess] = useState<Process | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [runs, setRuns] = useState<ProcessRun[]>([]);
  const [logs, setLogs] = useState<ProcessLog[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [deploying, setDeploying] = useState(false);
  const [running, setRunning] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!id) return;
    try {
      setLoading(true);
      const [proc, agentList, runList] = await Promise.all([
        getProcess(id),
        fetchAgents(),
        fetchProcessRuns(id),
      ]);
      setProcess(proc);
      setAgents(agentList);
      setRuns(runList);
      if (agentList.length > 0 && !selectedAgent) {
        setSelectedAgent(agentList[0].id);
      }
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  // WebSocket for live logs
  useEffect(() => {
    if (!id) return;
    const ws = connectProcessLogs(id, (msg) => {
      if (msg.type === "log") {
        const log = msg.data as ProcessLog;
        setLogs((prev) => [...prev, log]);
      } else if (msg.type === "run_update") {
        const updatedRun = msg.data as ProcessRun;
        setRuns((prev) =>
          prev.map((r) => (r.id === updatedRun.id ? updatedRun : r)),
        );
      }
    });
    return () => ws.close();
  }, [id]);

  async function handleDeploy() {
    if (!id || !selectedAgent) return;
    setDeploying(true);
    setError(null);
    try {
      await deployProcess(id, selectedAgent);
      alert("Process deployed successfully!");
    } catch (err) {
      setError(String(err));
    } finally {
      setDeploying(false);
    }
  }

  async function handleRun() {
    if (!id || !selectedAgent) return;
    setRunning(true);
    setError(null);
    try {
      const newRun = await runProcess(id, selectedAgent);
      setRuns((prev) => [newRun, ...prev]);
    } catch (err) {
      setError(String(err));
    } finally {
      setRunning(false);
    }
  }

  async function handleStop() {
    if (!id) return;
    setStopping(true);
    setError(null);
    try {
      await stopProcess(id);
    } catch (err) {
      setError(String(err));
    } finally {
      setStopping(false);
    }
  }

  if (loading) {
    return <div className="text-sm text-muted-foreground">Loading process...</div>;
  }

  if (!process) {
    return <div className="text-sm text-muted-foreground">Process not found.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">{process.name}</h1>
          {process.description && (
            <p className="text-sm text-muted-foreground">{process.description}</p>
          )}
        </div>
        <Button variant="ghost" size="sm" render={<Link to="/processes" />}>
          Back to Processes
        </Button>
      </div>

      {error && (
        <div className="text-sm text-red-500 p-4 bg-red-500/10 rounded-lg">
          {error}
        </div>
      )}

      {/* Process Info */}
      <Card>
        <CardHeader>
          <CardTitle>Process Info</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt className="text-muted-foreground">Entry Point</dt>
            <dd className="font-mono">{process.entry_point}</dd>
            <dt className="text-muted-foreground">Created</dt>
            <dd>{new Date(process.created_at).toLocaleString()}</dd>
            <dt className="text-muted-foreground">Updated</dt>
            <dd>{new Date(process.updated_at).toLocaleString()}</dd>
            <dt className="text-muted-foreground">Files</dt>
            <dd>{Object.keys(process.files).length}</dd>
          </dl>
          <div className="mt-4">
            <Button
              variant="ghost"
              size="sm"
              render={<Link to={`/processes/${process.id}/edit`} />}
            >
              Edit Process
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Deploy & Run */}
      <Card>
        <CardHeader>
          <CardTitle>Deploy & Run</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {agents.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No agents registered.{" "}
              <Link to="/agents" className="underline">
                Register one
              </Link>
              .
            </p>
          ) : (
            <>
              <div className="space-y-1.5">
                <label htmlFor="agent-select" className="text-sm font-medium">
                  Target Agent
                </label>
                <select
                  id="agent-select"
                  value={selectedAgent}
                  onChange={(e) => setSelectedAgent(e.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  {agents.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} ({agent.status})
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleDeploy}
                  disabled={deploying || !selectedAgent}
                >
                  {deploying ? "Deploying..." : "Deploy"}
                </Button>
                <Button
                  onClick={handleRun}
                  disabled={running || !selectedAgent}
                >
                  {running ? "Starting..." : "Run"}
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleStop}
                  disabled={stopping}
                >
                  {stopping ? "Stopping..." : "Stop"}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Runs History */}
      <Card>
        <CardHeader>
          <CardTitle>Runs</CardTitle>
        </CardHeader>
        <CardContent>
          {runs.length === 0 ? (
            <div className="text-sm text-muted-foreground py-4 text-center">
              No runs yet.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Agent</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Finished</TableHead>
                  <TableHead>Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => {
                  const agent = agents.find((a) => a.id === run.agent_id);
                  return (
                    <TableRow key={run.id}>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={statusStyles[run.status] ?? ""}
                        >
                          {run.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {agent?.name ?? run.agent_id}
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
                      <TableCell className="text-red-500 text-xs">
                        {run.error ?? ""}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Live Logs */}
      <Card>
        <CardHeader>
          <CardTitle>Logs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-h-96 overflow-y-auto font-mono text-xs space-y-1">
            {logs.length === 0 ? (
              <div className="text-muted-foreground">No logs yet...</div>
            ) : (
              logs.map((log) => (
                <div key={log.id} className="flex gap-3">
                  <span className="text-muted-foreground shrink-0">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="shrink-0 w-14 text-muted-foreground">
                    [{log.level.toUpperCase()}]
                  </span>
                  {log.source && (
                    <span className="shrink-0 text-blue-500 dark:text-blue-400">
                      {log.source}
                    </span>
                  )}
                  <span className={levelColors[log.level] ?? "text-foreground"}>
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
