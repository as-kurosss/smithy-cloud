import { Link, NavLink } from "react-router-dom";
import { Bot } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/processes", label: "Processes" },
  { to: "/agents", label: "Agents" },
];

function linkClass({ isActive }: { isActive: boolean }) {
  return cn(
    "rounded-full px-4 py-1.5 text-sm font-medium transition-all",
    isActive
      ? "bg-emerald-600 text-white shadow-sm shadow-emerald-600/40"
      : "text-muted-foreground hover:bg-emerald-600/10 hover:text-emerald-900",
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-100/70 via-background to-background text-foreground">
      <header className="sticky top-0 z-10 border-b border-emerald-900/10 bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-6">
          <Link to="/processes" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-700 text-white shadow-md shadow-emerald-600/30">
              <Bot className="h-5 w-5" />
            </span>
            <span className="leading-tight">
              <span className="block text-[15px] font-bold tracking-tight">
                Smithy <span className="text-emerald-600">Cloud</span>
              </span>
              <span className="block text-[11px] font-medium text-muted-foreground">
                process orchestrator
              </span>
            </span>
          </Link>
          <nav className="ml-6 flex items-center gap-1">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={linkClass}>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      <footer className="mx-auto max-w-6xl px-6 pb-6 text-center text-xs text-muted-foreground">
        Smithy Cloud · live process orchestration
      </footer>
    </div>
  );
}
