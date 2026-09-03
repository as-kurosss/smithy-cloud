import { useEffect, useState } from "react";
import { Cpu } from "lucide-react";
import { fetchAgents, createAgent, deleteAgent } from "@/lib/api";
import type { Agent } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/StatusBadge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AgentList() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showRegister, setShowRegister] = useState(false);
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [registering, setRegistering] = useState(false);

  async function loadAgents() {
    try {
      setLoading(true);
      const data = await fetchAgents();
      setAgents(data);
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAgents();
  }, []);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim() || !newUrl.trim()) return;
    setRegistering(true);
    setError(null);
    try {
      const agent = await createAgent({ name: newName, url: newUrl });
      setAgents((prev) => [...prev, agent]);
      setNewName("");
      setNewUrl("");
      setShowRegister(false);
    } catch (err) {
      setError(String(err));
    } finally {
      setRegistering(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this agent?")) return;
    try {
      await deleteAgent(id);
      setAgents((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
      setError(`Failed to delete: ${err}`);
    }
  }

  return (
    <div className="space-y-6 animate-enter">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight">Agents</h1>
          {!loading && <Badge variant="secondary">{agents.length}</Badge>}
        </div>
        <Button onClick={() => setShowRegister(!showRegister)}>
          {showRegister ? "Cancel" : "Register Agent"}
        </Button>
      </div>

      {error && (
        <div className="text-sm text-red-600 p-4 bg-red-500/10 rounded-xl border border-red-500/20">
          {error}
        </div>
      )}

      {showRegister && (
        <Card>
          <CardHeader>
            <CardTitle>Register New Agent</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleRegister} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="agent-name" className="text-sm font-medium">
                  Name
                </label>
                <Input
                  id="agent-name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="my-agent"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="agent-url" className="text-sm font-medium">
                  URL
                </label>
                <Input
                  id="agent-url"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="http://localhost:8001"
                  required
                />
              </div>
              <Button type="submit" disabled={registering}>
                {registering ? "Registering..." : "Register"}
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
      ) : agents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <Cpu className="h-7 w-7" />
            </span>
            <div className="space-y-1">
              <p className="font-semibold">No agents yet</p>
              <p className="text-sm text-muted-foreground">
                Register an agent below, then point it at the orchestrator to go
                online.
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
                <TableHead>URL</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Heartbeat</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {agents.map((agent) => (
                <TableRow
                  key={agent.id}
                  className="transition-colors hover:bg-emerald-50/50"
                >
                  <TableCell className="font-medium">{agent.name}</TableCell>
                  <TableCell className="font-mono text-sm text-muted-foreground">
                    {agent.url}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={agent.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {agent.last_heartbeat
                      ? new Date(agent.last_heartbeat).toLocaleString()
                      : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDelete(agent.id)}
                    >
                      Delete
                    </Button>
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
