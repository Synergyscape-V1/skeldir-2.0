/**
 * Dashboard page for authenticated users
 * Updated to use Prism mock APIs (B0.2)
 */

import { useState, useCallback } from 'react';
import { useCurrentUser, useAuth } from '@/hooks/useAuth';
import DashboardShell from '@/components/DashboardShell';
import { SidebarBranding } from '@/components/SidebarBranding';
import { SidebarPrimaryContent } from '@/components/dashboard/SidebarPrimaryContent';
import { SidebarUtilitiesContent } from '@/components/dashboard/SidebarUtilitiesContent';
import { useLocation } from 'wouter';
import { ExportButton } from '@/components/ExportButton';
import UserAvatar from '@/components/ui/user-avatar';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RevenueOverview } from '@/components/dashboard/RevenueOverview';
import { DashboardHighlightProvider } from '@/contexts/DashboardHighlightContext';
import { VerificationSyncProvider } from '@/contexts/VerificationSyncContext';
import { VerificationToast } from '@/components/dashboard/VerificationToast';
import { useRealtimeRevenue } from '@/hooks/use-realtime-revenue-mockoon';
import { useReconciliationStatus } from '@/hooks/use-reconciliation-status';
import { useSystemHealth } from '@/hooks/use-system-health';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, AlertCircle, Clock, TrendingUp, TrendingDown } from 'lucide-react';

export default function Dashboard() {
  const user = useCurrentUser();
  const { logout } = useAuth();
  const [, navigate] = useLocation();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

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

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      logout();
      await new Promise(resolve => setTimeout(resolve, 100));
      navigate('/');
    } catch (error) {
      console.error('Logout error:', error);
      setIsLoggingOut(false);
    }
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4" data-testid="loading-dashboard">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  const sidebarHeader = <SidebarBranding />;

  const sidebarContent = (
    <div className="flex flex-col h-full">
      <SidebarPrimaryContent />
      <div className="flex-1" />
      <SidebarUtilitiesContent 
        onLogout={handleLogout}
        isLoggingOut={isLoggingOut}
      />
    </div>
  );

  const dashboardData = {
    user: {
      id: user.id,
      username: user.username,
      email: user.email,
      lastLogin: user.lastLogin
    },
    revenueMetrics: revenueData ? [
      { value: revenueData.total_revenue, currency: 'USD', verified: revenueData.verified }
    ] : []
  };

  const userInitials = user.username.charAt(0);

  const headerActions = (
    <div className="flex items-center gap-4">
      <ExportButton data={dashboardData} />
      <UserAvatar 
        userName={user.username}
        userEmail={user.email}
        userInitials={userInitials}
      />
    </div>
  );

  const getHealthStatusBadge = () => {
    if (isLoadingHealth) {
      return <Badge variant="outline"><Clock className="w-3 h-3 mr-1" /> Checking...</Badge>;
    }
    if (!healthData) {
      return <Badge variant="destructive"><AlertCircle className="w-3 h-3 mr-1" /> Offline</Badge>;
    }
    if (healthData.status === 'healthy') {
      return <Badge variant="default" className="bg-green-500"><CheckCircle className="w-3 h-3 mr-1" /> Healthy</Badge>;
    }
    if (healthData.status === 'degraded') {
      return <Badge variant="secondary"><AlertCircle className="w-3 h-3 mr-1" /> Degraded</Badge>;
    }
    return <Badge variant="destructive"><AlertCircle className="w-3 h-3 mr-1" /> Unhealthy</Badge>;
  };

  return (
    <DashboardShell sidebarHeader={sidebarHeader} sidebarContent={sidebarContent} headerActions={headerActions}>
      <VerificationSyncProvider>
        <DashboardHighlightProvider>
          <VerificationToast />
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-[#080808]" style={{ color: 'hsl(var(--brand-cool-black))' }} data-testid="text-dashboard-title">Control Panel</h1>
                <p style={{ color: 'hsl(var(--brand-cool-black) / 0.7)' }}>
                  Welcome back, {user.username}!
                </p>
              </div>
              <div className="flex items-center gap-2">
                {getHealthStatusBadge()}
              </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
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
                    <div className="text-destructive text-sm">
                      Failed to load revenue data
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
                      {revenueData.upgrade_notice && (
                        <div className="text-xs text-blue-600 mt-2">
                          {revenueData.upgrade_notice}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-muted-foreground">No data available</div>
                  )}
                </CardContent>
              </Card>

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
                      {reconciliationData.platforms.slice(0, 4).map((platform, index) => (
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
                      {reconciliationData.platforms.length > 4 && (
                        <div className="text-xs text-muted-foreground">
                          +{reconciliationData.platforms.length - 4} more platforms
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-muted-foreground">No platforms connected</div>
                  )}
                </CardContent>
              </Card>

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
                    <div className="text-muted-foreground">Health check unavailable</div>
                  )}
                </CardContent>
              </Card>
            </div>

            {revenueData && (
              <div className="mt-8">
                <h2 className="text-2xl font-bold mb-6" style={{ color: 'hsl(var(--brand-cool-black))' }}>
                  Revenue Overview
                </h2>
                <RevenueOverview
                  verifiedRevenue={revenueData.verified ? revenueData.total_revenue : 0}
                  unverifiedRevenue={revenueData.verified ? 0 : revenueData.total_revenue}
                  verifiedPercentage={revenueData.verified ? 100 : 0}
                  unverifiedPercentage={revenueData.verified ? 0 : 100}
                  verifiedTrend={5.2}
                  unverifiedTrend={-2.1}
                />
              </div>
            )}

          </div>
        </DashboardHighlightProvider>
      </VerificationSyncProvider>
    </DashboardShell>
  );
}
