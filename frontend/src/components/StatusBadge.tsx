import { Badge } from "@/components/ui/badge";
import type { Execution } from "@/lib/types";

const statusStyles: Record<Execution["status"], string> = {
  pending:
    "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400 border-yellow-500/30",
  running:
    "bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30",
  completed:
    "bg-green-500/15 text-green-600 dark:text-green-400 border-green-500/30",
  failed: "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30",
};

export function StatusBadge({ status }: { status: Execution["status"] }) {
  return (
    <Badge variant="outline" className={statusStyles[status]}>
      {status}
    </Badge>
  );
}
