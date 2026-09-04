import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getProcess,
  fetchAgents,
  deployProcess,
  runProcess,
  stopProcess,
  connectProcessLogs,
} from "@/lib/api";
import type { Process, Agent, ProcessLog } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMinRole } from "@/lib/auth";
import { Play, Rocket, Square } from "lucide-react";

const levelColors: Record<string, string> = {
  debug: "text-zinc-500",
  info: "text-green-300",
  warning: "text-amber-300",
  error: "text-red-400",
};

export function ProcessDetail() {
  const { id } = useParams<{ id: string }>();
  const [process, setProcess] = useState<Process | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [logs, setLogs] = useState<ProcessLog[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [deploying, setDeploying] = useState(false);
  const [running, setRunning] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const logRef = useRef<HTMLDivElement>(null);
  const canOperate = useMinRole("operator");

  async function load() {
    if (!id) return;
    try {
      setLoading(true);
      const [proc, agentList] = await Promise.all([
        getProcess(id),
        fetchAgents(),
      ]);
      setProcess(proc);
      setAgents(agentList);
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
      }
    });
    return () => ws.close();
  }, [id]);

  // Auto-scroll the terminal to the bottom as new logs arrive
  useEffect(() => {
    const el = logRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [logs]);

  async function handleDeploy() {
    if (!id || !selectedAgent) return;
    setDeploying(true);
    setError(null);
    setNotice(null);
    try {
      await deployProcess(id, selectedAgent);
      setNotice("Deployed — the agent will pick it up in a few seconds.");
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
    setNotice(null);
    try {
      await runProcess(id, selectedAgent);
      setNotice("Run started — streaming logs live below.");
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
    <div className="space-y-6 animate-enter">
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
        <div className="text-sm text-red-600 p-4 bg-red-500/10 rounded-xl border border-red-500/20">
          {error}
        </div>
      )}

      {notice && (
        <div className="text-sm text-emerald-800 p-4 bg-emerald-500/10 rounded-xl border border-emerald-500/25 animate-enter">
          {notice}
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
          {canOperate && (
            <div className="mt-4">
              <Button
                variant="ghost"
                size="sm"
                render={<Link to={`/processes/${process.id}/edit`} />}
              >
                Edit Process
              </Button>
            </div>
          )}
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
              {canOperate ? (
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={handleDeploy}
                    disabled={deploying || !selectedAgent}
                  >
                    <Rocket className="h-4 w-4" />
                    {deploying ? "Deploying..." : "Deploy"}
                  </Button>
                  <Button
                    onClick={handleRun}
                    disabled={running || !selectedAgent}
                  >
                    <Play className="h-4 w-4" />
                    {running ? "Starting..." : "Run"}
                  </Button>
                  <Button
                    variant="destructive"
                    onClick={handleStop}
                    disabled={stopping}
                  >
                    <Square className="h-4 w-4" />
                    {stopping ? "Stopping..." : "Stop"}
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Read-only access — your role does not allow deploy or run.
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Runs live on their own tab now — link keeps one click away. */}
      <div className="text-sm">
        <Link
          to={`/runs?process_id=${process.id}`}
          className="font-medium text-emerald-700 hover:underline"
        >
          View runs of this process →
        </Link>
      </div>

      {/* Live Logs */}
      <Card className="overflow-hidden border-emerald-900/20">
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <CardTitle>Logs</CardTitle>
          <span className="flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] font-bold tracking-wide text-emerald-800">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-600" />
            </span>
            LIVE
          </span>
        </CardHeader>
        <CardContent>
          <div
            ref={logRef}
            className="terminal-scroll h-96 overflow-y-auto rounded-xl bg-zinc-950 p-4 font-mono text-xs leading-relaxed"
          >
            {logs.length === 0 ? (
              <div className="text-zinc-500">
                Waiting for logs — deploy & run the process to stream output
                here.
              </div>
            ) : (
              logs.map((log) => (
                <div key={log.id} className="flex gap-3">
                  <span className="shrink-0 text-zinc-500">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="w-16 shrink-0 text-zinc-400">
                    [{log.level.toUpperCase()}]
                  </span>
                  {log.source && (
                    <span className="shrink-0 text-sky-400">
                      {log.source}
                    </span>
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
