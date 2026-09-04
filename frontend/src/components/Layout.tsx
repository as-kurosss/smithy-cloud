import { Link, NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Bot, Cpu, Inbox, KeyRound, Layers, LogOut, Menu, Play, ScrollText, Timer, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

const navItems = [
  { to: "/processes", label: "Processes", icon: Layers },
  { to: "/runs", label: "Runs", icon: Play },
  { to: "/agents", label: "Agents", icon: Cpu },
  { to: "/queues", label: "Queues", icon: Inbox },
  { to: "/triggers", label: "Triggers", icon: Timer },
  { to: "/assets", label: "Assets", icon: KeyRound },
  { to: "/logs", label: "Logs", icon: ScrollText },
];

function linkClass({ isActive }: { isActive: boolean }) {
  return cn(
    "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-all",
    isActive
      ? "bg-emerald-600 text-white shadow-sm shadow-emerald-600/40"
      : "text-muted-foreground hover:bg-emerald-600/10 hover:text-emerald-900",
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, authEnabled, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const initials = user?.email?.slice(0, 2).toUpperCase() ?? "··";

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-100/70 via-background to-background text-foreground">
      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-emerald-900/10 bg-background/80 px-4 backdrop-blur-md md:hidden">
        <button
          type="button"
          aria-label="Open menu"
          onClick={() => setOpen(true)}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground transition-all hover:bg-emerald-600/10 hover:text-emerald-900"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Link to="/processes" className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-400 to-emerald-700 text-white shadow-md shadow-emerald-600/30">
            <Bot className="h-4 w-4" />
          </span>
          <span className="text-[15px] font-bold tracking-tight">
            Smithy <span className="text-emerald-600">Cloud</span>
          </span>
        </Link>
      </header>

      {/* Overlay for mobile drawer */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/30 backdrop-blur-sm md:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-emerald-900/10 bg-background/90 backdrop-blur-md transition-transform duration-200",
          open ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
        )}
      >
        <div className="flex items-center gap-2.5 px-4 pt-5">
          <Link
            to="/processes"
            className="flex flex-1 items-center gap-2.5"
            onClick={() => setOpen(false)}
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-700 text-white shadow-md shadow-emerald-600/30">
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
          <button
            type="button"
            aria-label="Close menu"
            onClick={() => setOpen(false)}
            className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-all hover:bg-emerald-600/10 hover:text-emerald-900 md:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {authEnabled && user && (
          <div className="mx-4 mt-4 flex items-center gap-2.5 rounded-xl border border-emerald-900/10 bg-emerald-600/5 p-2.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400 to-emerald-700 text-xs font-bold text-white">
              {initials}
            </span>
            <span className="min-w-0 leading-tight">
              <span className="block truncate text-[13px] font-semibold">
                {user.email}
              </span>
              <span className="block text-[11px] font-semibold capitalize text-emerald-700">
                {user.role}
              </span>
            </span>
          </div>
        )}

        {(!authEnabled || user) && (
          <nav className="flex flex-col gap-1 px-4 pt-4">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={linkClass}
                onClick={() => setOpen(false)}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {item.label}
              </NavLink>
            ))}
          </nav>
        )}

        <div className="mt-auto px-4 pb-5">
          {authEnabled && user && (
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-muted-foreground transition-all hover:bg-emerald-600/10 hover:text-emerald-900"
            >
              <LogOut className="h-4 w-4 shrink-0" />
              Sign out
            </button>
          )}
          <p className="mt-3 px-3 text-[11px] text-muted-foreground">
            Smithy Cloud · live orchestration
          </p>
        </div>
      </aside>

      <main className="mx-auto max-w-6xl px-6 py-8 md:ml-64">
        {children}
      </main>
    </div>
  );
}
