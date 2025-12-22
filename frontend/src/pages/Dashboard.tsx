/**
 * Dashboard page for authenticated users
 * Updated to use Prism mock APIs (B0.2)
 * Gracefully handles missing backend APIs
 */

import { useState, useCallback, Component, ReactNode } from 'react';
import { useCurrentUser, useAuth } from '@/hooks/useAuth';
import { useLocation } from 'wouter';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { CheckCircle, AlertCircle, Clock, LogOut } from 'lucide-react';

// Import components - these should all exist
import DashboardShell from '@/components/DashboardShell';
import { SidebarBranding } from '@/components/SidebarBranding';
import { SidebarPrimaryContent } from '@/components/dashboard/SidebarPrimaryContent';
import { SidebarUtilitiesContent } from '@/components/dashboard/SidebarUtilitiesContent';
import { ExportButton } from '@/components/ExportButton';
import UserAvatar from '@/components/ui/user-avatar';
import { RevenueOverview } from '@/components/dashboard/RevenueOverview';
import { DashboardHighlightProvider } from '@/contexts/DashboardHighlightContext';
import { VerificationSyncProvider } from '@/contexts/VerificationSyncContext';
import { VerificationToast } from '@/components/dashboard/VerificationToast';
import { useRealtimeRevenue } from '@/hooks/use-realtime-revenue-mockoon';
import { useReconciliationStatus } from '@/hooks/use-reconciliation-status';
import { useSystemHealth } from '@/hooks/use-system-health';

// Error boundary to catch component errors
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class DashboardErrorBoundary extends Component<{ children: ReactNode; fallback?: ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: ReactNode; fallback?: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Dashboard error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800 text-sm">
            <strong>Component Error:</strong> {this.state.error?.message || 'Unknown error'}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function Dashboard() {
  const user = useCurrentUser();
  const { logout } = useAuth();
  const [, navigate] = useLocation();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  // Use hooks - they handle their own errors via react-query
  const { data: revenueData, isLoading: isLoadingRevenue, error: revenueError } = useRealtimeRevenue({
    refetchInterval: 30000,
    enabled: true,
  });

  const { data: reconciliationData, isLoading: isLoadingReconciliation } = useReconciliationStatus({
    refetchInterval: 60000,
    enabled: true,
  });

  const { data: healthData, isLoading: isLoadingHealth } = useSystemHealth({
    refetchInterval: 30000,
    enabled: true,
  });

  const handleLogout = useCallback(async () => {
    setIsLoggingOut(true);
    try {
      logout();
      await new Promise(resolve => setTimeout(resolve, 100));
      navigate('/');
    } catch (error) {
      console.error('Logout error:', error);
      setIsLoggingOut(false);
    }
  }, [logout, navigate]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100" data-testid="loading-dashboard">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const getHealthStatusBadge = () => {
    if (isLoadingHealth) {
      return <Badge variant="outline"><Clock className="w-3 h-3 mr-1" /> Checking...</Badge>;
    }
    if (!healthData) {
      return <Badge variant="secondary"><AlertCircle className="w-3 h-3 mr-1" /> Offline</Badge>;
    }
    if (healthData.status === 'healthy') {
      return <Badge variant="default" className="bg-green-500"><CheckCircle className="w-3 h-3 mr-1" /> Healthy</Badge>;
    }
    if (healthData.status === 'degraded') {
      return <Badge variant="secondary"><AlertCircle className="w-3 h-3 mr-1" /> Degraded</Badge>;
    }
    return <Badge variant="destructive"><AlertCircle className="w-3 h-3 mr-1" /> Unhealthy</Badge>;
  };

  const sidebarHeader = (
    <DashboardErrorBoundary fallback={<div className="p-2 text-sm">Skeldir</div>}>
      <SidebarBranding />
    </DashboardErrorBoundary>
  );

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <DashboardErrorBoundary fallback={<div className="p-2 text-sm text-muted-foreground">Menu unavailable</div>}>
        <SidebarPrimaryContent />
      </DashboardErrorBoundary>
      <div className="flex-1" />
      <DashboardErrorBoundary fallback={
        <Button variant="ghost" onClick={handleLogout} className="w-full">
          <LogOut className="w-4 h-4 mr-2" /> Logout
        </Button>
      }>
        <SidebarUtilitiesContent 
          onLogout={handleLogout}
          isLoggingOut={isLoggingOut}
        />
      </DashboardErrorBoundary>
    </div>
  );

  const headerActions = (
    <div className="flex items-center gap-4">
      <DashboardErrorBoundary fallback={null}>
        <ExportButton data={{ user: { id: user.id, username: user.username, email: user.email } }} />
      </DashboardErrorBoundary>
      <DashboardErrorBoundary fallback={
        <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center text-sm font-medium">
          {user.username.charAt(0).toUpperCase()}
        </div>
      }>
        <UserAvatar 
          userName={user.username}
          userEmail={user.email}
          userInitials={user.username.charAt(0)}
        />
      </DashboardErrorBoundary>
    </div>
  );

  const dashboardContent = (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-800" data-testid="text-dashboard-title">Control Panel</h1>
          <p className="text-gray-600">
            Welcome back, {user.username}!
          </p>
        </div>
        <div className="flex items-center gap-2">
          {getHealthStatusBadge()}
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Realtime Revenue Card */}
        <Card data-testid="card-realtime-revenue">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Realtime Revenue
              {revenueData?.verified && (
                <CheckCircle className="w-4 h-4 text-green-500" />
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingRevenue ? (
              <div className="flex items-center justify-center h-20">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
              </div>
            ) : revenueError ? (
              <div className="text-muted-foreground text-sm">
                <p>API not connected</p>
                <p className="text-xs mt-1">Revenue data will appear when backend is running</p>
              </div>
            ) : revenueData ? (
              <div className="space-y-2">
                <div className="text-3xl font-bold" data-testid="text-total-revenue">
                  ${revenueData.total_revenue?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </div>
                <div className="text-sm text-muted-foreground">
                  {revenueData.event_count?.toLocaleString()} events tracked
                </div>
                <div className="text-xs text-muted-foreground">
                  Last updated: {revenueData.last_updated ? new Date(revenueData.last_updated).toLocaleTimeString() : 'N/A'}
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground text-sm">
                <p>No data available</p>
                <p className="text-xs mt-1">Connect backend to see revenue</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Platform Status Card */}
        <Card data-testid="card-reconciliation-status">
          <CardHeader>
            <CardTitle>Platform Status</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingReconciliation ? (
              <div className="flex items-center justify-center h-20">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
              </div>
            ) : reconciliationData?.platforms ? (
              <div className="space-y-2">
                {reconciliationData.platforms.slice(0, 4).map((platform: any, index: number) => (
                  <div key={index} className="flex items-center justify-between text-sm">
                    <span>{platform.platform_name}</span>
                    <Badge 
                      variant={platform.connection_status === 'verified' ? 'default' : 
                              platform.connection_status === 'partial' ? 'secondary' : 
                              platform.connection_status === 'pending' ? 'outline' : 'destructive'}
                      className={platform.connection_status === 'verified' ? 'bg-green-500' : ''}
                    >
                      {platform.connection_status}
                    </Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-muted-foreground text-sm">
                <p>No platforms connected</p>
                <p className="text-xs mt-1">Platform data will appear when backend is running</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* System Health Card */}
        <Card data-testid="card-system-health">
          <CardHeader>
            <CardTitle>System Health</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingHealth ? (
              <div className="flex items-center justify-center h-20">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
              </div>
            ) : healthData ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm">Status:</span>
                  <span className={`font-medium ${
                    healthData.status === 'healthy' ? 'text-green-600' :
                    healthData.status === 'degraded' ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {healthData.status?.charAt(0).toUpperCase() + healthData.status?.slice(1)}
                  </span>
                </div>
                <div className="text-sm text-muted-foreground">
                  Version: {healthData.version}
                </div>
                <div className="text-xs text-muted-foreground">
                  Uptime: {Math.floor((healthData.uptime_seconds || 0) / 3600)}h {Math.floor(((healthData.uptime_seconds || 0) % 3600) / 60)}m
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground text-sm">
                <p>Health check unavailable</p>
                <p className="text-xs mt-1">Status will appear when backend is running</p>
              </div>
            )}
          </CardContent>
        </Card>

      </div>

      {/* Revenue Overview Section - Always show with mock data fallback */}
      <div className="mt-8">
        <h2 className="text-2xl font-bold mb-6 text-gray-800">
          Revenue Overview
        </h2>
        <DashboardErrorBoundary fallback={
          <div className="p-4 bg-gray-50 border rounded-lg text-muted-foreground">
            Revenue overview unavailable
          </div>
        }>
          <RevenueOverview
            verifiedRevenue={revenueData?.verified ? revenueData.total_revenue : (revenueData?.total_revenue || 125430.50)}
            unverifiedRevenue={revenueData?.verified ? 0 : (revenueData ? revenueData.total_revenue : 0)}
            verifiedPercentage={revenueData?.verified ? 100 : (revenueData ? 0 : 100)}
            unverifiedPercentage={revenueData?.verified ? 0 : (revenueData ? 100 : 0)}
            verifiedTrend={5.2}
            unverifiedTrend={-2.1}
          />
        </DashboardErrorBoundary>
      </div>

      {/* API Status Notice - Only show when APIs are not connected */}
      {!revenueData && !reconciliationData && !healthData && (
        <div className="mt-8 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-blue-800 text-sm">
            <strong>Development Mode:</strong> Backend APIs are not connected. 
            Showing mock data. Revenue, platform status, and health data will update when the backend services are running.
          </p>
        </div>
      )}
    </div>
  );

  return (
    <DashboardErrorBoundary fallback={
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 p-6">
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg mb-6">
          <p className="text-red-800">Dashboard shell failed to load. Showing simplified view.</p>
        </div>
        {dashboardContent}
      </div>
    }>
      <DashboardShell sidebarHeader={sidebarHeader} sidebarContent={sidebarContent} headerActions={headerActions}>
        <DashboardErrorBoundary fallback={
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-yellow-800">Some dashboard features failed to load.</p>
          </div>
        }>
          <VerificationSyncProvider>
            <DashboardHighlightProvider>
              <VerificationToast />
              {dashboardContent}
            </DashboardHighlightProvider>
          </VerificationSyncProvider>
        </DashboardErrorBoundary>
      </DashboardShell>
    </DashboardErrorBoundary>
  );
}
