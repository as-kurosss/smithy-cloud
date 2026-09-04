import { useEffect, useState } from "react";
import { KeyRound, Lock } from "lucide-react";
import {
  createAsset,
  deleteAsset,
  fetchAssets,
  updateAsset,
} from "@/lib/api";
import type { Asset } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newImmutable, setNewImmutable] = useState(false);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [editImmutable, setEditImmutable] = useState(false);
  const [saving, setSaving] = useState(false);
  const canOperator = useMinRole("operator");

  async function load() {
    try {
      setLoading(true);
      setAssets(await fetchAssets());
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await createAsset({
        name: newName.trim(),
        value: newValue,
        immutable: newImmutable,
      });
      setNewName("");
      setNewValue("");
      setNewImmutable(false);
      setShowCreate(false);
      await load();
    } catch (err) {
      setError(String(err));
    } finally {
      setCreating(false);
    }
  }

  function startEdit(asset: Asset) {
    setEditing(asset.name);
    setEditValue(asset.value);
    setEditImmutable(asset.immutable);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setSaving(true);
    setError(null);
    try {
      await updateAsset(editing, {
        value: editValue,
        immutable: editImmutable,
      });
      setEditing(null);
      await load();
    } catch (err) {
      setError(String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(name: string) {
    if (!confirm(`Delete asset "${name}"?`)) return;
    try {
      await deleteAsset(name);
      if (editing === name) setEditing(null);
      await load();
    } catch (err) {
      setError(`Failed to delete: ${err}`);
    }
  }

  return (
    <div className="space-y-6 animate-enter">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight">Assets</h1>
            {!loading && <Badge variant="secondary">{assets.length}</Badge>}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Named key-value pairs for processes — immutable ones are locked
            against changes.
          </p>
        </div>
        {canOperator && (
          <Button onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? "Cancel" : "New Asset"}
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
            <CardTitle>Create Asset</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="asset-name" className="text-sm font-medium">
                  Key
                </label>
                <Input
                  id="asset-name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="api-url"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="asset-value" className="text-sm font-medium">
                  Value
                </label>
                <Textarea
                  id="asset-value"
                  value={newValue}
                  onChange={(e) => setNewValue(e.target.value)}
                  placeholder="http://agent:9000"
                  rows={3}
                />
              </div>
              <label
                htmlFor="asset-immutable"
                className="flex cursor-pointer items-center gap-2 text-sm font-medium"
              >
                <input
                  id="asset-immutable"
                  type="checkbox"
                  checked={newImmutable}
                  onChange={(e) => setNewImmutable(e.target.checked)}
                  className="h-4 w-4 accent-emerald-600"
                />
                Immutable — lock against future changes
              </label>
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
      ) : assets.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <KeyRound className="h-7 w-7" />
            </span>
            <div className="space-y-1">
              <p className="font-semibold">No assets yet</p>
              <p className="text-sm text-muted-foreground">
                Create a key-value pair to share data with processes.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden py-0">
          <Table>
            <TableHeader>
              <TableRow className="bg-emerald-50/60 hover:bg-emerald-50/60">
                <TableHead>Key</TableHead>
                <TableHead>Value</TableHead>
                <TableHead>Lock</TableHead>
                {canOperator && <TableHead className="text-right">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {assets.map((asset) => (
                <TableRow
                  key={asset.id}
                  className="transition-colors hover:bg-emerald-50/50"
                >
                  <TableCell className="font-medium">{asset.name}</TableCell>
                  <TableCell className="max-w-96">
                    {canOperator && editing === asset.name && !asset.immutable ? (
                      <form onSubmit={handleSave} className="space-y-2">
                        <Textarea
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          rows={2}
                        />
                        <label className="flex cursor-pointer items-center gap-2 text-xs font-medium">
                          <input
                            type="checkbox"
                            checked={editImmutable}
                            onChange={(e) => setEditImmutable(e.target.checked)}
                            className="h-4 w-4 accent-emerald-600"
                          />
                          Lock as immutable
                        </label>
                        <div className="flex gap-2">
                          <Button type="submit" size="sm" disabled={saving}>
                            {saving ? "Saving..." : "Save"}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => setEditing(null)}
                          >
                            Cancel
                          </Button>
                        </div>
                      </form>
                    ) : (
                      <span className="block truncate font-mono text-xs text-muted-foreground">
                        {asset.value || "—"}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    {asset.immutable && (
                      <Badge variant="secondary" className="gap-1">
                        <Lock className="h-3 w-3" />
                        immutable
                      </Badge>
                    )}
                  </TableCell>
                  {canOperator && (
                    <TableCell className="text-right">
                      {!asset.immutable && editing !== asset.name && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="mr-2"
                          onClick={() => startEdit(asset)}
                        >
                          Edit
                        </Button>
                      )}
                      {!asset.immutable && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDelete(asset.name)}
                        >
                          Delete
                        </Button>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
