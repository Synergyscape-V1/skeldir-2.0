import React from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { AgentShellChannelComparison } from "./comparison/AgentShellChannelComparison";
import { AgentShellCommandCenter } from "./comparison/AgentShellCommandCenter";
import { AgentShellDataHealth } from "./comparison/AgentShellDataHealth";
import { AgentShellPlatformIntegrations } from "./comparison/AgentShellPlatformIntegrations";
import { AgentShellSingleChannelDetail } from "./comparison/AgentShellSingleChannelDetail";
import { AgentShellBudgetOptimizer } from "./comparison/AgentShellBudgetOptimizer";
import { AgentShellBudgetScenarioDetail } from "./comparison/AgentShellBudgetScenarioDetail";
import { AgentShellBudgetScenarioList } from "./comparison/AgentShellBudgetScenarioList";
import { AgentShellInvestigations } from "./investigations/AgentShellInvestigations";
import { AGENTS } from "./comparison/agents";

const COMMAND_CENTER_THEME = AGENTS[1];
const SINGLE_CHANNEL_THEME = AGENTS[1];
const CHANNEL_COMPARISON_THEME = AGENTS[4];
const DATA_HEALTH_THEME = AGENTS[1];
const PLATFORM_INTEGRATIONS_THEME = AGENTS[0]; // Agent A — Minimalist Data Density
const BUDGET_OPTIMIZER_THEME = AGENTS[1]; // Agent B — Signal Console
const INVESTIGATIONS_THEME = AGENTS[1]; // Agent B — Signal Console

function mapToDetailRoute(channelId: string): string | null {
  const map: Record<string, string> = {
    ch_google_ads: "ch_google_ads",
    ch_meta_ads: "ch_meta_ads",
    ch_facebook_ads: "ch_meta_ads",
    ch_tiktok_ads: "ch_tiktok_ads",
    ch_pinterest_ads: "ch_pinterest_ads",
  };

  const resolved = map[channelId];
  if (!resolved) return null;
  return `/channels/${resolved}?date_range=last_30_days`;
}

function CommandCenterPage() {
  const navigate = useNavigate();

  return (
    <AgentShellCommandCenter
      theme={COMMAND_CENTER_THEME}
      scenario="ready"
      dataset="mixed"
      density={100}
      getChannelDetailHref={mapToDetailRoute}
      onChannelActivate={(channelId) => {
        const href = mapToDetailRoute(channelId);
        if (href) navigate(href);
      }}
    />
  );
}

function SingleChannelDetailPage() {
  return <AgentShellSingleChannelDetail theme={SINGLE_CHANNEL_THEME} scenario="steady" dataset="mixed" density={100} />;
}

function ChannelComparisonPage() {
  return (
    <AgentShellChannelComparison
      theme={CHANNEL_COMPARISON_THEME}
      territoryName={CHANNEL_COMPARISON_THEME.title}
      scenario="default"
      dateRange="last_30_days"
      density={100}
    />
  );
}

function DataHealthPage() {
  return <AgentShellDataHealth theme={DATA_HEALTH_THEME} scenario="warning" uiState="steady" density={100} stale={false} />;
}

function BudgetOptimizerPage() {
  return <AgentShellBudgetOptimizer theme={BUDGET_OPTIMIZER_THEME} density={100} />;
}

function BudgetScenarioListPage() {
  return <AgentShellBudgetScenarioList theme={BUDGET_OPTIMIZER_THEME} density={100} />;
}

function BudgetScenarioDetailPage() {
  return <AgentShellBudgetScenarioDetail theme={BUDGET_OPTIMIZER_THEME} density={100} />;
}

function InvestigationsQueuePage() {
  return <AgentShellInvestigations theme={INVESTIGATIONS_THEME} density={100} view="queue" />;
}

function InvestigationsDetailPage() {
  return <AgentShellInvestigations theme={INVESTIGATIONS_THEME} density={100} view="detail" />;
}

function DataIntegrationsPage() {
  return (
    <AgentShellPlatformIntegrations
      theme={PLATFORM_INTEGRATIONS_THEME}
      scenario="mixed"
      uiState="steady"
      density={100}
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<CommandCenterPage />} />
        <Route path="/channels/compare" element={<ChannelComparisonPage />} />
        <Route path="/channels/:channelId" element={<SingleChannelDetailPage />} />
        <Route path="/budget" element={<BudgetOptimizerPage />} />
        <Route path="/budget/scenarios" element={<BudgetScenarioListPage />} />
        <Route path="/budget/scenarios/:id" element={<BudgetScenarioDetailPage />} />
        <Route path="/data" element={<DataHealthPage />} />
        <Route path="/data/integrations" element={<DataIntegrationsPage />} />
        <Route path="/investigations" element={<InvestigationsQueuePage />} />
        <Route path="/investigations/:investigationId" element={<InvestigationsDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
