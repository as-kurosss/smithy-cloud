import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const styles: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800 border-amber-200",
  dispatched: "bg-sky-100 text-sky-800 border-sky-200",
  deploying: "bg-sky-100 text-sky-800 border-sky-200",
  running: "bg-blue-100 text-blue-800 border-blue-200",
  stopping: "bg-orange-100 text-orange-800 border-orange-200",
  completed: "bg-emerald-100 text-emerald-800 border-emerald-200",
  deployed: "bg-emerald-100 text-emerald-800 border-emerald-200",
  online: "bg-emerald-100 text-emerald-800 border-emerald-200",
  active: "bg-emerald-100 text-emerald-800 border-emerald-200",
  failed: "bg-red-100 text-red-800 border-red-200",
  stopped: "bg-orange-100 text-orange-800 border-orange-200",
  offline: "bg-zinc-200 text-zinc-600 border-zinc-300",
};

const pulseStatuses = new Set([
  "pending",
  "dispatched",
  "deploying",
  "running",
  "stopping",
  "online",
  "active",
]);

export function StatusBadge({ status }: { status: string }) {
  const key = status.toLowerCase();
  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1.5 font-medium",
        styles[key] ?? "bg-zinc-100 text-zinc-700 border-zinc-200",
      )}
    >
      {pulseStatuses.has(key) && (
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-current" />
        </span>
      )}
      {status}
    </Badge>
  );
}
