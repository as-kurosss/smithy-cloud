import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { ProcessList } from "@/pages/ProcessList";
import { ProcessEditor } from "@/pages/ProcessEditor";
import { ProcessDetail } from "@/pages/ProcessDetail";
import { AgentList } from "@/pages/AgentList";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/processes" replace />} />
          <Route path="/processes" element={<ProcessList />} />
          <Route path="/processes/new" element={<ProcessEditor />} />
          <Route path="/processes/:id" element={<ProcessDetail />} />
          <Route path="/processes/:id/edit" element={<ProcessEditor />} />
          <Route path="/agents" element={<AgentList />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
