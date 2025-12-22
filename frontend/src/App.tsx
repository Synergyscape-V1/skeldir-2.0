import { Switch, Route, useLocation } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@/components/ThemeProvider";
import GeometricBackground from "@/components/GeometricBackground";
import LoginInterface from "@/components/LoginInterface";
import Dashboard from "@/pages/Dashboard";
import NotFound from "@/pages/not-found";

// STEP 1: Minimal routing test - just login + dashboard (no guards/providers)
function Router() {
  return (
    <Switch>
      <Route path="/" component={LoginInterface} />
      <Route path="/dashboard" component={Dashboard} />
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
