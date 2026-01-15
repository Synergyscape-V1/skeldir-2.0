import { Switch, Route, useLocation } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/components/ThemeProvider";
import GeometricBackground from "@/components/GeometricBackground";
import LoginInterface from "@/components/LoginInterface";
import Dashboard from "@/pages/Dashboard";
import BudgetOptimizerPage from "@/pages/BudgetOptimizerPage";
import BudgetScenarioDetailPage from "@/pages/BudgetScenarioDetailPage";
import InvestigationQueuePage from "@/pages/InvestigationQueuePage";
import SettingsPage from "@/pages/SettingsPage";
import NotFound from "@/pages/not-found";

// Frontend routing with new pages (Budget, Investigations, Settings)
function Router() {
  return (
    <Switch>
      <Route path="/" component={LoginInterface} />
      <Route path="/dashboard" component={Dashboard} />
      <Route path="/budget" component={BudgetOptimizerPage} />
      <Route path="/budget/scenarios/:scenarioId" component={BudgetScenarioDetailPage} />
      <Route path="/investigations" component={InvestigationQueuePage} />
      <Route path="/settings" component={SettingsPage} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <GeometricBackground />
        <div className="relative z-10">
          <Router />
        </div>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
