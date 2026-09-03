import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchProcesses, deleteProcess } from "@/lib/api";
import type { Process } from "@/lib/types";
import { Button } from "@/components/ui/button";
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
      alert(`Failed to delete: ${err}`);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Processes</h1>
        <Button render={<Link to="/processes/new" />}>New Process</Button>
      </div>

      {error && (
        <div className="text-sm text-red-500 p-4 bg-red-500/10 rounded-lg">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading...</div>
      ) : processes.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No processes yet. Create one to get started.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
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
                  className="cursor-pointer"
                  onClick={() => navigate(`/processes/${process.id}`)}
                >
                  <TableCell className="font-medium">{process.name}</TableCell>
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
