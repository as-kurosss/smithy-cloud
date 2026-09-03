import { Link, NavLink, useNavigate } from "react-router-dom";
import { Bot, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

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
  const { user, authEnabled, logout } = useAuth();
  const navigate = useNavigate();
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
          {(!authEnabled || user) && (
            <nav className="ml-6 flex items-center gap-1">
              {navItems.map((item) => (
                <NavLink key={item.to} to={item.to} className={linkClass}>
                  {item.label}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="ml-auto flex items-center gap-2">
            {authEnabled && user && (
              <>
                <span className="hidden text-sm text-muted-foreground sm:block">{user.email}</span>
                <span className="rounded-full bg-emerald-600/10 px-2.5 py-0.5 text-xs font-semibold capitalize text-emerald-700">
                  {user.role}
                </span>
                <button
                  type="button"
                  title="Sign out"
                  onClick={async () => {
                    await logout();
                    navigate("/login");
                  }}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-all hover:bg-emerald-600/10 hover:text-emerald-900"
                >
                  <LogOut className="h-4 w-4" />
                </button>
              </>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      <footer className="mx-auto max-w-6xl px-6 pb-6 text-center text-xs text-muted-foreground">
        Smithy Cloud · live process orchestration
      </footer>
    </div>
  );
}
