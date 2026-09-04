import { useEffect, useState } from "react";
import { Inbox } from "lucide-react";
import {
  fetchQueues,
  createQueue,
  addQueueItems,
  deleteQueue,
} from "@/lib/api";
import type { QueueCounts, QueueWithCounts } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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

const COUNT_STYLES: Array<{ key: keyof QueueCounts; label: string; cls: string }> = [
  { key: "new", label: "new", cls: "bg-slate-200 text-slate-700" },
  { key: "in_progress", label: "in_progress", cls: "bg-emerald-100 text-emerald-700" },
  { key: "success", label: "success", cls: "bg-emerald-600 text-white" },
  { key: "business_failed", label: "business_failed", cls: "bg-amber-100 text-amber-700" },
  { key: "system_failed", label: "system_failed", cls: "bg-red-100 text-red-700" },
];

export function QueuesPage() {
  const [queues, setQueues] = useState<QueueWithCounts[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAttempts, setNewAttempts] = useState("3");
  const [creating, setCreating] = useState(false);
  const [itemsQueue, setItemsQueue] = useState<string | null>(null);
  const [itemsPayload, setItemsPayload] = useState("");
  const [itemsKey, setItemsKey] = useState("");
  const [adding, setAdding] = useState(false);
  const canOperator = useMinRole("operator");

  async function loadQueues() {
    try {
      setLoading(true);
      setQueues(await fetchQueues());
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadQueues();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createQueue({
        name: newName.trim(),
        max_attempts: Math.max(1, Number(newAttempts) || 3),
      });
      setNewName("");
      setNewAttempts("3");
      setShowCreate(false);
      await loadQueues();
    } catch (err) {
      setError(String(err));
    } finally {
      setCreating(false);
    }
  }

  async function handleAddItems(e: React.FormEvent) {
    e.preventDefault();
    if (!itemsQueue || !itemsPayload.trim()) return;
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(itemsPayload) as Record<string, unknown>;
    } catch {
      setError("Items payload must be valid JSON");
      return;
    }
    setAdding(true);
    setError(null);
    try {
      await addQueueItems(itemsQueue, [
        { payload, idempotency_key: itemsKey.trim() || null },
      ]);
      setItemsPayload("");
      setItemsKey("");
      setItemsQueue(null);
      await loadQueues();
    } catch (err) {
      setError(String(err));
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(name: string) {
    if (!confirm(`Delete queue "${name}" and all its items?`)) return;
    try {
      await deleteQueue(name);
      if (itemsQueue === name) setItemsQueue(null);
      await loadQueues();
    } catch (err) {
      setError(`Failed to delete: ${err}`);
    }
  }

  return (
    <div className="space-y-6 animate-enter">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">Queues</h1>
            {!loading && <Badge variant="secondary">{queues.length}</Badge>}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Transactional items, REFramework-style — agents claim work with a
            lease and report success or failure.
          </p>
        </div>
        {canOperator && (
          <Button onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? "Cancel" : "New Queue"}
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
            <CardTitle>Create Queue</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
                <div className="space-y-1.5">
                  <label htmlFor="queue-name" className="text-sm font-medium">
                    Name
                  </label>
                  <Input
                    id="queue-name"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="invoices"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <label htmlFor="queue-attempts" className="text-sm font-medium">
                    Max attempts
                  </label>
                  <Input
                    id="queue-attempts"
                    type="number"
                    min={1}
                    value={newAttempts}
                    onChange={(e) => setNewAttempts(e.target.value)}
                    required
                  />
                </div>
              </div>
              <Button type="submit" disabled={creating}>
                {creating ? "Creating..." : "Create"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {canOperator && itemsQueue && (
        <Card>
          <CardHeader>
            <CardTitle>Add items to “{itemsQueue}”</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAddItems} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="item-payload" className="text-sm font-medium">
                  Payload (JSON)
                </label>
                <Textarea
                  id="item-payload"
                  value={itemsPayload}
                  onChange={(e) => setItemsPayload(e.target.value)}
                  placeholder={JSON.stringify(
                    { url: "https://example.com/invoice/42", attempt: 1 },
                    null,
                    2,
                  )}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="item-key" className="text-sm font-medium">
                  Idempotency key (optional)
                </label>
                <Input
                  id="item-key"
                  value={itemsKey}
                  onChange={(e) => setItemsKey(e.target.value)}
                  placeholder="invoice-42"
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={adding}>
                  {adding ? "Adding..." : "Add item"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setItemsQueue(null)}
                >
                  Close
                </Button>
              </div>
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
      ) : queues.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <Inbox className="h-7 w-7" />
            </span>
            <div className="space-y-1">
              <p className="font-semibold">No queues yet</p>
              <p className="text-sm text-muted-foreground">
                Create a queue, add items, and your agents will claim them with
                a lease.
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
                <TableHead>Max attempts</TableHead>
                <TableHead>Counts</TableHead>
                <TableHead>Created</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queues.map((queue) => (
                <TableRow
                  key={queue.id}
                  className="transition-colors hover:bg-emerald-50/50"
                >
                  <TableCell className="font-medium">{queue.name}</TableCell>
                  <TableCell>{queue.max_attempts}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1.5">
                      {COUNT_STYLES.map(({ key, label, cls }) => (
                        <span
                          key={key}
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium",
                            cls,
                          )}
                        >
                          {label}: {queue.counts[key]}
                        </span>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(queue.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    {canOperator && (
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setItemsQueue(queue.name);
                            setItemsPayload("");
                            setItemsKey("");
                          }}
                        >
                          Add items
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDelete(queue.name)}
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