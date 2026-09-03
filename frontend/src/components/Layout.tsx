import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";

const navItems = [
  { to: "/processes", label: "Processes" },
  { to: "/agents", label: "Agents" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border px-6 py-3">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <Link to="/processes" className="text-lg font-semibold tracking-tight">
            Smithy Cloud
          </Link>
          <nav className="flex gap-1">
            {navItems.map((item) => (
              <Button
                key={item.to}
                variant={location.pathname === item.to ? "default" : "ghost"}
                size="sm"
                render={<Link to={item.to} />}
              >
                {item.label}
              </Button>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}
