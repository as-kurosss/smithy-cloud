import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createProcess, getProcess, updateProcess } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function ProcessEditor() {
  const { id } = useParams<{ id: string }>();
  const isEditing = Boolean(id);
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [entryPoint, setEntryPoint] = useState("main.py");
  const [files, setFiles] = useState<Record<string, string>>({
    "main.py": "",
  });
  const [selectedFile, setSelectedFile] = useState("main.py");
  const [requirements, setRequirements] = useState("");
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(isEditing);
  const [error, setError] = useState<string | null>(null);
  const [editingFilename, setEditingFilename] = useState<string | null>(null);
  const [editingFilenameValue, setEditingFilenameValue] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fileNames = Object.keys(files);
  const currentContent = files[selectedFile] ?? "";

  const handleAddFile = useCallback(() => {
    const filename = prompt("Enter filename (e.g. utils.py)");
    if (!filename) return;
    const trimmed = filename.trim();
    if (!trimmed || trimmed in files) return;
    setFiles((prev) => ({ ...prev, [trimmed]: "" }));
    setSelectedFile(trimmed);
  }, [files]);

  const handleDeleteFile = useCallback(
    (filename: string) => {
      if (fileNames.length <= 1) return;
      const next = { ...files };
      delete next[filename];
      setFiles(next);
      if (selectedFile === filename) {
        setSelectedFile(Object.keys(next)[0]);
      }
      if (entryPoint === filename) {
        setEntryPoint(Object.keys(next)[0]);
      }
    },
    [files, fileNames.length, selectedFile, entryPoint],
  );

  const handleRenameStart = useCallback(
    (filename: string) => {
      setEditingFilename(filename);
      setEditingFilenameValue(filename);
    },
    [],
  );

  const handleRenameCommit = useCallback(() => {
    if (!editingFilename) return;
    const newName = editingFilenameValue.trim();
    if (!newName || newName === editingFilename || newName in files) {
      setEditingFilename(null);
      return;
    }
    const next: Record<string, string> = {};
    for (const [k, v] of Object.entries(files)) {
      next[k === editingFilename ? newName : k] = v;
    }
    setFiles(next);
    if (selectedFile === editingFilename) setSelectedFile(newName);
    if (entryPoint === editingFilename) setEntryPoint(newName);
    setEditingFilename(null);
  }, [editingFilename, editingFilenameValue, files, selectedFile, entryPoint]);

  const handleFileUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const fileList = e.target.files;
      if (!fileList) return;
      Array.from(fileList).forEach((file) => {
        const reader = new FileReader();
        reader.onload = () => {
          const content = typeof reader.result === "string" ? reader.result : "";
          setFiles((prev) => ({ ...prev, [file.name]: content }));
          setSelectedFile(file.name);
        };
        reader.readAsText(file);
      });
      // Reset so the same file can be re-uploaded
      e.target.value = "";
    },
    [],
  );

  useEffect(() => {
    if (!id) return;
    getProcess(id)
      .then((process) => {
        setName(process.name);
        setDescription(process.description ?? "");
        setEntryPoint(process.entry_point);
        setFiles(process.files);
        const first = Object.keys(process.files)[0];
        if (first) setSelectedFile(first);
        setRequirements(process.requirements.join("\n"));
      })
      .catch((err) => setError(String(err)))
      .finally(() => setFetching(false));
  }, [id]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        name,
        description: description || null,
        entry_point: entryPoint,
        files,
        requirements: requirements
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      };
      if (isEditing && id) {
        await updateProcess(id, payload);
        navigate(`/processes/${id}`);
      } else {
        await createProcess(payload);
        navigate("/processes");
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  if (fetching) {
    return <div className="text-sm text-muted-foreground">Loading process...</div>;
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">
        {isEditing ? "Edit Process" : "New Process"}
      </h1>

      {error && (
        <div className="text-sm text-red-500 p-4 bg-red-500/10 rounded-lg">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Details</CardTitle>
            <CardDescription>Configure your process.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="name" className="text-sm font-medium">
                Name
              </label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My process"
                required
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="description" className="text-sm font-medium">
                Description
              </label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="entry_point" className="text-sm font-medium">
                Entry Point
              </label>
              <Input
                id="entry_point"
                value={entryPoint}
                onChange={(e) => setEntryPoint(e.target.value)}
                placeholder="main.py"
                required
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Files</CardTitle>
                <CardDescription>
                  Edit your process files. Entry point:{" "}
                  <code>{entryPoint}</code>.
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddFile}
                >
                  + Add File
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Upload
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  multiple
                  onChange={handleFileUpload}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4 min-h-[360px]">
              {/* File sidebar */}
              <div className="w-48 shrink-0 border rounded-md p-2 space-y-0.5 overflow-y-auto">
                {fileNames.map((fname) => (
                  <div
                    key={fname}
                    className={cn(
                      "flex items-center justify-between gap-1 rounded px-2 py-1 text-sm cursor-pointer",
                      fname === selectedFile
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-muted",
                    )}
                    onClick={() => setSelectedFile(fname)}
                  >
                    {editingFilename === fname ? (
                      <Input
                        value={editingFilenameValue}
                        onChange={(e) =>
                          setEditingFilenameValue(e.target.value)
                        }
                        onBlur={handleRenameCommit}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleRenameCommit();
                          if (e.key === "Escape") setEditingFilename(null);
                        }}
                        className="h-6 text-xs px-1"
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span
                        className="truncate flex-1"
                        onDoubleClick={() => handleRenameStart(fname)}
                        title="Double-click to rename"
                      >
                        {fname}
                        {fname === entryPoint && (
                          <span className="ml-1 text-muted-foreground text-xs">
                            (entry)
                          </span>
                        )}
                      </span>
                    )}
                    {fileNames.length > 1 && fname !== editingFilename && (
                      <button
                        type="button"
                        className="shrink-0 text-muted-foreground hover:text-destructive text-xs leading-none p-0.5"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteFile(fname);
                        }}
                        title={`Delete ${fname}`}
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* Editor area */}
              <div className="flex-1">
                <Textarea
                  value={currentContent}
                  onChange={(e) => {
                    const val = e.target.value;
                    setFiles((prev) => ({ ...prev, [selectedFile]: val }));
                  }}
                  className="font-mono text-xs min-h-[320px] resize-y"
                  placeholder="# Your code here"
                  spellCheck={false}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Requirements</CardTitle>
            <CardDescription>
              Python package requirements (one per line).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              className="font-mono text-xs min-h-[100px]"
              placeholder="requests&#10;pydantic"
            />
          </CardContent>
        </Card>

        <div className="flex gap-2">
          <Button type="submit" disabled={loading}>
            {loading ? "Saving..." : isEditing ? "Save Changes" : "Create Process"}
          </Button>
          <Button
            variant="ghost"
            type="button"
            onClick={() => navigate(isEditing && id ? `/processes/${id}` : "/processes")}
          >
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
