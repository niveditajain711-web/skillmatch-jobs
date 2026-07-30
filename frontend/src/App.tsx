import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { HistoryPage } from "./pages/HistoryPage";
import { JobDetailPage } from "./pages/JobDetailPage";
import { NewSearchPage } from "./pages/NewSearchPage";
import { ResultsPage } from "./pages/ResultsPage";
import { ResumePage } from "./pages/ResumePage";
import { SettingsPage } from "./pages/SettingsPage";

const qc = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="search" element={<NewSearchPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="results/:runId" element={<ResultsPage />} />
            <Route path="results/:runId/jobs/:jobId" element={<JobDetailPage />} />
            <Route path="resume" element={<ResumePage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
