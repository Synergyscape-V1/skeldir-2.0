/**
 * D3.1 App — Migrated to React Router for NavLink contract compliance
 * 
 * Route structure:
 * - /login → LoginInterface (unauthenticated)
 * - / → ProtectedLayout → AppShell with nested routes:
 *   - / (index) → CommandCenterPage
 *   - /channels → ChannelDetailRoute (Single Channel Detail — Meta Ads)
 *   - /data → DataStub
 *   - /budget → BudgetOptimizerPage
 *   - /investigations → InvestigationQueuePage
 *   - /settings → SettingsPage
 *   - Harness routes preserved for D1/D2 validation
 */
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ErrorBannerProvider } from "@/components/error-banner/ErrorBannerProvider";
import { ErrorBannerContainer } from "@/components/error-banner/ErrorBannerContainer";
import GeometricBackground from "@/components/GeometricBackground";
import LoginInterface from "@/components/LoginInterface";
import ProtectedLayout from "@/components/ProtectedLayout";
import CommandCenterPage from "@/pages/CommandCenterPage";
import ChannelDetailRoute from "@/pages/ChannelDetailRoute";
import { A6VictorComparison } from "@/pages/channel-comparison/a6-victor";
import { VICTOR_FIXTURES } from "@/pages/channel-comparison/a6-victor/victor-fixtures";
import DataStub from "@/pages/DataStub";
import BudgetOptimizerPage from "@/pages/BudgetOptimizerPage";
import BudgetScenarioDetailPage from "@/pages/BudgetScenarioDetailPage";
import InvestigationQueuePage from "@/pages/InvestigationQueuePage";
import SettingsPage from "@/pages/SettingsPage";
import D2CompositesHarness from "@/pages/D2CompositesHarness";
import D1AtomicsHarness from "@/pages/D1AtomicsHarness";
import NotFound from "@/pages/not-found";

function Router() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Unauthenticated route */}
        <Route path="/login" element={<LoginInterface />} />
        
        {/* Legacy dashboard route - redirect to root */}
        <Route path="/dashboard" element={<Navigate to="/" replace />} />
        
        {/* Protected routes with AppShell */}
        <Route path="/" element={<ProtectedLayout />}>
          <Route index element={<CommandCenterPage />} />
          <Route path="channels/compare" element={<A6VictorComparison initialState={VICTOR_FIXTURES.ready} />} />
          <Route path="channels/:channelId" element={<ChannelDetailRoute />} />
          <Route path="data" element={<DataStub />} />
          <Route path="budget" element={<BudgetOptimizerPage />} />
          <Route path="budget/scenarios/:scenarioId" element={<BudgetScenarioDetailPage />} />
          <Route path="investigations" element={<InvestigationQueuePage />} />
          <Route path="settings" element={<SettingsPage />} />
          
          {/* Harness routes for D1/D2 validation */}
          <Route path="d1/atomics" element={<D1AtomicsHarness />} />
          <Route path="d2/composites" element={<D2CompositesHarness />} />
          
          {/* 404 fallback */}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ErrorBannerProvider>
          <GeometricBackground />
          <div className="relative z-10">
            <Router />
          </div>
          <ErrorBannerContainer />
        </ErrorBannerProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
