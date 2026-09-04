import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";
import type { ReactNode } from "react";
import { Layout } from "@/components/Layout";
import { ProcessList } from "@/pages/ProcessList";
import { ProcessEditor } from "@/pages/ProcessEditor";
import { ProcessDetail } from "@/pages/ProcessDetail";
import { AgentList } from "@/pages/AgentList";
import { QueuesPage } from "@/pages/QueuesPage";
import { LogsPage } from "@/pages/LogsPage";
import { Login } from "@/pages/Login";
import { AuthProvider, useAuth, useMinRole } from "@/lib/auth";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, authEnabled, ready } = useAuth();
  if (!ready) {
    return <div className="text-sm text-muted-foreground">Loading...</div>;
  }
  if (authEnabled && !user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function RequireRole({ level, children }: { level: string; children: ReactNode }) {
  const allowed = useMinRole(level);
  const { ready } = useAuth();
  if (!ready) {
    return <div className="text-sm text-muted-foreground">Loading...</div>;
  }
  if (!allowed) {
    return <Navigate to="/processes" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/processes" replace />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/processes"
              element={
                <RequireAuth>
                  <ProcessList />
                </RequireAuth>
              }
            />
            <Route
              path="/processes/new"
              element={
                <RequireAuth>
                  <RequireRole level="operator">
                    <ProcessEditor />
                  </RequireRole>
                </RequireAuth>
              }
            />
            <Route
              path="/processes/:id"
              element={
                <RequireAuth>
                  <ProcessDetail />
                </RequireAuth>
              }
            />
            <Route
              path="/processes/:id/edit"
              element={
                <RequireAuth>
                  <RequireRole level="operator">
                    <ProcessEditor />
                  </RequireRole>
                </RequireAuth>
              }
            />
            <Route
              path="/agents"
              element={
                <RequireAuth>
                  <AgentList />
                </RequireAuth>
              }
            />
            <Route
              path="/queues"
              element={
                <RequireAuth>
                  <QueuesPage />
                </RequireAuth>
              }
            />
            <Route
              path="/logs"
              element={
                <RequireAuth>
                  <LogsPage />
                </RequireAuth>
              }
            />
          </Routes>
        </Layout>
      </AuthProvider>
    </BrowserRouter>
  );
}
