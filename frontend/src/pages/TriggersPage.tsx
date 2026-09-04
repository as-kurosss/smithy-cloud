import { useEffect, useState } from "react";
import { Timer } from "lucide-react";
import {
  fetchTriggers,
  createTrigger,
  updateTrigger,
  deleteTrigger,
  fetchAgents,
  fetchProcesses,
} from "@/lib/api";
import type { Trigger, Agent, Process } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useMinRole } from "@/lib/auth";
import { cn } from "@/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STATUS_STYLES: Record<Trigger["status"], string> = {
  scheduled: "bg-emerald-600 text-white",
  fired: "bg-slate-200 text-slate-700",
  disabled: "bg-amber-100 text-amber-700",
};

function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function TriggersPage() {
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [processes, setProcesses] = useState<Process[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAgent, setNewAgent] = useState("");
  const [newProcess, setNewProcess] = useState("");
  const [newRunAt, setNewRunAt] = useState(() =>
    toLocalInputValue(new Date(Date.now() + 60 * 60 * 1000)),
  );
  const [creating, setCreating] = useState(false);
  const canOperator = useMinRole("operator");

  async function loadTriggers(silent = false) {
    try {
      if (!silent) setLoading(true);
      setTriggers(await fetchTriggers());
      setError(null);
    } catch (err) {
      if (!silent) setError(String(err));
    } finally {
      if (!silent) setLoading(false);
    }
  }

  useEffect(() => {
    async function loadOptions() {
      try {
        const [agentList, processList] = await Promise.all([
          fetchAgents(),
          fetchProcesses(),
        ]);
        setAgents(agentList);
        setProcesses(processList);
        if (agentList.length > 0) setNewAgent(agentList[0].id);
        if (processList.length > 0) setNewProcess(processList[0].id);
      } catch (err) {
        setError(String(err));
      }
    }
    loadTriggers();
    loadOptions();
    const timer = setInterval(() => loadTriggers(true), 15000);
    return () => clearInterval(timer);
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim() || !newAgent || !newProcess || !newRunAt) return;
    setCreating(true);
    setError(null);
    try {
      // datetime-local is wall-clock local time — convert to tz-aware ISO.
      const runAt = new Date(newRunAt).toISOString();
      await createTrigger({
        name: newName.trim(),
        agent_id: newAgent,
        process_id: newProcess,
        run_at: runAt,
      });
      setNewName("");
      setShowCreate(false);
      await loadTriggers();
    } catch (err) {
      setError(String(err));
    } finally {
      setCreating(false);
    }
  }

  async function handleToggle(trigger: Trigger) {
    try {
      await updateTrigger(trigger.id, { enabled: !trigger.enabled });
      await loadTriggers();
    } catch (err) {
      setError(`Failed to toggle: ${err}`);
    }
  }

  async function handleDelete(trigger: Trigger) {
    if (!confirm(`Delete trigger "${trigger.name}"?`)) return;
    try {
      await deleteTrigger(trigger.id);
      await loadTriggers();
    } catch (err) {
      setError(`Failed to delete: ${err}`);
    }
  }

  return (
    <div className="space-y-6 animate-enter">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">Triggers</h1>
            {!loading && <Badge variant="secondary">{triggers.length}</Badge>}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            One-shot scheduled runs — pick an agent, a process and a launch
            time. Late triggers still fire on the next poll, never skipped.
          </p>
        </div>
        {canOperator && (
          <Button onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? "Cancel" : "New Trigger"}
          </Button>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-600">
          {error}
        </div>
      )}

      {canOperator && showCreate && (
        <Card>
          <CardHeader>
            <CardTitle>Create Trigger</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label htmlFor="trigger-name" className="text-sm font-medium">
                    Name
                  </label>
                  <Input
                    id="trigger-name"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="nightly-report"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="trigger-run-at" className="text-sm font-medium">
                    Run at
                  </label>
                  <Input
                    id="trigger-run-at"
                    type="datetime-local"
                    value={newRunAt}
                    onChange={(e) => setNewRunAt(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="trigger-agent" className="text-sm font-medium">
                    Agent
                  </label>
                  <select
                    id="trigger-agent"
                    value={newAgent}
                    onChange={(e) => setNewAgent(e.target.value)}
                    required
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none"
                  >
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="trigger-process" className="text-sm font-medium">
                    Process
                  </label>
                  <select
                    id="trigger-process"
                    value={newProcess}
                    onChange={(e) => setNewProcess(e.target.value)}
                    required
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs outline-none"
                  >
                    {processes.map((process) => (
                      <option key={process.id} value={process.id}>
                        {process.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <Button type="submit" disabled={creating}>
                {creating ? "Creating..." : "Create"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-xl bg-emerald-900/5"
            />
          ))}
        </div>
      ) : triggers.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <Timer className="h-7 w-7" />
            </span>
            <div className="space-y-1">
              <p className="font-semibold">No triggers yet</p>
              <p className="text-sm text-muted-foreground">
                Schedule a run for an agent and process at a specific time.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden py-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-emerald-50/60 hover:bg-emerald-50/60">
                <TableHead>Name</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead>Process</TableHead>
                <TableHead>Run at</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {triggers.map((trigger) => (
                <TableRow
                  key={trigger.id}
                  className="transition-colors hover:bg-emerald-50/50"
                >
                  <TableCell className="font-medium">{trigger.name}</TableCell>
                  <TableCell>{trigger.agent_name}</TableCell>
                  <TableCell>{trigger.process_name}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(trigger.run_at).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        STATUS_STYLES[trigger.status],
                      )}
                    >
                      {trigger.status}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    {canOperator && (
                      <div className="flex justify-end gap-2">
                        {trigger.fired_at === null && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleToggle(trigger)}
                          >
                            {trigger.enabled ? "Disable" : "Enable"}
                          </Button>
                        )}
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDelete(trigger)}
                        >
                          Delete
                        </Button>
                      </div>
                    )}
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
