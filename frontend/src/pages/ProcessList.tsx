import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bot, Plus } from "lucide-react";
import { fetchProcesses, deleteProcess } from "@/lib/api";
import type { Process } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useMinRole } from "@/lib/auth";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent } from "@/components/ui/card";

export function ProcessList() {
  const [processes, setProcesses] = useState<Process[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const canWrite = useMinRole("operator");

  async function loadProcesses() {
    try {
      setLoading(true);
      const data = await fetchProcesses();
      setProcesses(data);
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProcesses();
  }, []);

  async function handleDelete(id: string) {
    if (!confirm("Delete this process?")) return;
    try {
      await deleteProcess(id);
      setProcesses((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(`Failed to delete: ${err}`);
    }
  }

  return (
    <div className="space-y-6 animate-enter">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight">Processes</h1>
          {!loading && <Badge variant="secondary">{processes.length}</Badge>}
        </div>
        {canWrite && (
          <Button render={<Link to="/processes/new" />}>
            <Plus className="h-4 w-4" />
            New Process
          </Button>
        )}
      </div>

      {error && (
        <div className="text-sm text-red-600 p-4 bg-red-500/10 rounded-xl border border-red-500/20">
          {error}
        </div>
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
      ) : processes.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <Bot className="h-7 w-7" />
            </span>
            <div className="space-y-1">
              <p className="font-semibold">No processes yet</p>
              <p className="text-sm text-muted-foreground">
                Create your first bot process, then deploy it to an agent.
              </p>
            </div>
            {canWrite && (
              <Button render={<Link to="/processes/new" />}>
                <Plus className="h-4 w-4" />
                New Process
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden py-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-emerald-50/60 hover:bg-emerald-50/60">
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Entry Point</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {processes.map((process) => (
                <TableRow
                  key={process.id}
                  className="cursor-pointer transition-colors hover:bg-emerald-50/50"
                  onClick={() => navigate(`/processes/${process.id}`)}
                >
                  <TableCell>
                    <span className="flex items-center gap-2 font-medium">
                      <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500" />
                      {process.name}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {process.description || "—"}
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {process.entry_point}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(process.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    {canWrite && (
                    <div className="flex gap-1 justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        render={
                          <Link
                            to={`/processes/${process.id}/edit`}
                            onClick={(e) => e.stopPropagation()}
                          />
                        }
                      >
                        Edit
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(process.id);
                        }}
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
