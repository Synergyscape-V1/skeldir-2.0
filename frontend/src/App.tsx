import { Switch, Route, useLocation } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/ThemeProvider";
import { TokenProvider } from "@/hooks/useTokenManager";
import GeometricBackground from "@/components/GeometricBackground";
import LoginInterface from "@/components/LoginInterface";
import Dashboard from "@/pages/Dashboard";
import ApiClientTest from "@/pages/ApiClientTest";
import PollingDemo from "@/pages/PollingDemo";
import DualRevenueDemo from "@/pages/DualRevenueDemo";
import ImplementationPortal from "@/pages/ImplementationPortal";
import { RouteGuard } from "@/components/RouteGuard";
import NotFound from "@/pages/not-found";
import { NavigationProvider } from "@/providers/NavigationProvider";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useEffect, useState } from "react";
import { errorRetryWorker } from "@/lib/error-retry-worker";
import { ErrorLoggingMetrics } from "@/lib/error-logging-metrics";
import { ErrorBannerProvider, ErrorBannerContainer } from "@/components/error-banner";
import { ToastNotificationProvider } from "@/components/ui/toast-notification";

function Router() {
  return (
    <Switch>
      <Route path="/" component={LoginInterface} />
      <Route path="/dashboard">
        <RouteGuard redirectTo="/">
          <Dashboard />
        </RouteGuard>
      </Route>
      <Route path="/implementation-portal">
        <RouteGuard redirectTo="/">
          <ImplementationPortal />
        </RouteGuard>
      </Route>
      <Route path="/api-test" component={ApiClientTest} />
      <Route path="/polling-demo" component={PollingDemo} />
      <Route path="/dual-revenue-demo" component={DualRevenueDemo} />
      <Route component={NotFound} />
    </Switch>
  );
}

function AppContent() {
  const [remountKey, setRemountKey] = useState(0);
  const [, navigate] = useLocation();

  // TokenProvider onTokenExpired callback
  const handleTokenExpired = () => {
    console.log('[TokenManager] Token expired, redirecting to login');
    navigate('/');
  };

  useEffect(() => {
    const handleRetry = () => setRemountKey(prev => prev + 1);
    const handleGoHome = () => {
      setRemountKey(prev => prev + 1);
      navigate('/');
    };
    
    window.addEventListener('error-boundary-retry', handleRetry);
    window.addEventListener('error-boundary-go-home', handleGoHome);
    
    return () => {
      window.removeEventListener('error-boundary-retry', handleRetry);
      window.removeEventListener('error-boundary-go-home', handleGoHome);
    };
  }, [navigate]);

  return (
    <ErrorBoundary key={remountKey}>
      <TokenProvider onTokenExpired={handleTokenExpired}>
        <ThemeProvider>
          <GeometricBackground />
          <div className="relative z-10">
            <Router />
          </div>
          <Toaster />
          <ErrorBannerContainer />
        </ThemeProvider>
      </TokenProvider>
    </ErrorBoundary>
  );
}

function App() {
  useEffect(() => {
    console.log('[App] Initializing error logging infrastructure');
    errorRetryWorker.start();
    ErrorLoggingMetrics.startPeriodicReporting();
    
    return () => {
      console.log('[App] Cleaning up error logging infrastructure');
      errorRetryWorker.stop();
      ErrorLoggingMetrics.stopPeriodicReporting();
    };
  }, []);
  
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={150} skipDelayDuration={200}>
        <ErrorBannerProvider>
          <ToastNotificationProvider>
            <NavigationProvider>
              <AppContent />
            </NavigationProvider>
          </ToastNotificationProvider>
        </ErrorBannerProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
