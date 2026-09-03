import { useEffect, useState } from "react";
import { fetchAgents, createAgent, deleteAgent } from "@/lib/api";
import type { Agent } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
      alert(`Failed to delete: ${err}`);
    }
  }

  function getStatusIndicator(status: string) {
    const isOnline = status === "online" || status === "active";
    return (
      <span className="flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${isOnline ? "bg-green-500" : "bg-red-500"}`}
        />
        {status}
      </span>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
        <Button onClick={() => setShowRegister(!showRegister)}>
          {showRegister ? "Cancel" : "Register Agent"}
        </Button>
      </div>

      {error && (
        <div className="text-sm text-red-500 p-4 bg-red-500/10 rounded-lg">
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
        <div className="text-sm text-muted-foreground">Loading...</div>
      ) : agents.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No agents registered yet.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>URL</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Heartbeat</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {agents.map((agent) => (
                <TableRow key={agent.id}>
                  <TableCell className="font-medium">{agent.name}</TableCell>
                  <TableCell className="font-mono text-sm text-muted-foreground">
                    {agent.url}
                  </TableCell>
                  <TableCell>
                    {getStatusIndicator(agent.status)}
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
