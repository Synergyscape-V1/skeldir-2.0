import { useEffect, useState } from 'react';
import { useLocation, useSearch } from 'wouter';
import { ArrowLeft, CheckCircle, Settings, Activity } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

/**
 * Implementation Portal - Platform Integration Management
 * 
 * Handles deep-linked navigation from dashboard CTAs with contextual query parameters:
 * - action: connect | retry-sync | configure
 * - tab: health | integrations | settings
 * - source: reconciliation | integrity-monitor | empty-state | dashboard
 * - first: true | false (first-time user flag)
 * - platform: specific platform identifier
 */
export default function ImplementationPortal() {
  const [, navigate] = useLocation();
  const searchParams = useSearch();
  
  // Parse query parameters
  const params = new URLSearchParams(searchParams);
  const action = params.get('action');
  const tab = params.get('tab') || 'integrations';
  const source = params.get('source');
  const isFirstTime = params.get('first') === 'true';
  const platform = params.get('platform');

  const [activeTab, setActiveTab] = useState(tab);

  useEffect(() => {
    setActiveTab(tab);
  }, [tab]);

  // Source context messages for analytics/UX
  const getSourceMessage = () => {
    switch (source) {
      case 'reconciliation':
        return 'You were redirected here from the Data Reconciliation Status component to improve your data confidence.';
      case 'integrity-monitor':
        return 'You were redirected here from the Data Integrity Monitor to manage platform health.';
      case 'empty-state':
        return 'Welcome! Let\'s connect your first platform to start verifying revenue.';
      case 'dashboard':
        return 'You navigated here from the dashboard.';
      default:
        return '';
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-card border-b border-border shadow-sm">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/dashboard')}
                className="gap-2"
                data-testid="button-back-dashboard"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to Dashboard
              </Button>
              <div className="h-6 w-px bg-border" />
              <h1 className="text-2xl font-bold text-foreground" data-testid="text-portal-title">
                Implementation Portal
              </h1>
            </div>
            
            {source && (
              <div className="hidden md:flex items-center space-x-2 px-3 py-1.5 bg-primary/10 rounded-full border border-primary/20">
                <span className="text-xs font-medium text-primary" data-testid="text-source-indicator">
                  From: {source.replace('-', ' ')}
                </span>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Source Context Banner */}
        {source && (
          <div className="mb-6 p-4 bg-primary/5 border-l-4 border-primary rounded-md" data-testid="banner-source-context">
            <p className="text-sm text-foreground/80">
              {getSourceMessage()}
            </p>
          </div>
        )}

        {/* First-time User Welcome */}
        {isFirstTime && (
          <div className="mb-6 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 border border-primary/20 rounded-lg" data-testid="banner-first-time">
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-10 h-10 bg-primary rounded-full flex items-center justify-center">
                <CheckCircle className="w-5 h-5 text-primary-foreground" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-foreground mb-1">Welcome to Implementation Portal!</h3>
                <p className="text-sm text-foreground/80">
                  This is your central hub for managing platform integrations. Let's get you started by connecting your first platform.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Action-specific Alert */}
        {action && (
          <div className="mb-6 p-4 bg-muted border border-border rounded-md" data-testid="alert-action">
            <p className="text-sm font-medium text-foreground">
              Action requested: <span className="text-primary capitalize">{action.replace('-', ' ')}</span>
              {platform && <span> for platform: <span className="text-primary">{platform}</span></span>}
            </p>
          </div>
        )}

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-3 max-w-2xl" data-testid="tabs-navigation">
            <TabsTrigger value="integrations" data-testid="tab-integrations">
              <Settings className="w-4 h-4 mr-2" />
              Integrations
            </TabsTrigger>
            <TabsTrigger value="health" data-testid="tab-health">
              <Activity className="w-4 h-4 mr-2" />
              Platform Health
            </TabsTrigger>
            <TabsTrigger value="settings" data-testid="tab-settings">
              <Settings className="w-4 h-4 mr-2" />
              Settings
            </TabsTrigger>
          </TabsList>

          <TabsContent value="integrations" className="space-y-4" data-testid="content-integrations">
            <div className="bg-card border border-border rounded-lg p-8">
              <h2 className="text-xl font-bold text-foreground mb-4">Platform Integrations</h2>
              <p className="text-muted-foreground mb-6">
                Connect and manage your payment processors and marketing platforms.
              </p>
              
              <div className="space-y-4">
                <div className="p-4 border-2 border-dashed border-border rounded-lg text-center">
                  <p className="text-sm text-muted-foreground">
                    Platform integration functionality will be implemented here.
                  </p>
                  {action === 'connect' && (
                    <p className="text-sm text-primary mt-2">
                      Ready to connect a new platform
                    </p>
                  )}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="health" className="space-y-4" data-testid="content-health">
            <div className="bg-card border border-border rounded-lg p-8">
              <h2 className="text-xl font-bold text-foreground mb-4">Platform Health Dashboard</h2>
              <p className="text-muted-foreground mb-6">
                Monitor the health and status of all connected platforms.
              </p>
              
              <div className="p-4 border-2 border-dashed border-border rounded-lg text-center">
                <p className="text-sm text-muted-foreground">
                  Platform health monitoring will be implemented here.
                </p>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="settings" className="space-y-4" data-testid="content-settings">
            <div className="bg-card border border-border rounded-lg p-8">
              <h2 className="text-xl font-bold text-foreground mb-4">Portal Settings</h2>
              <p className="text-muted-foreground mb-6">
                Configure your implementation preferences and notifications.
              </p>
              
              <div className="p-4 border-2 border-dashed border-border rounded-lg text-center">
                <p className="text-sm text-muted-foreground">
                  Settings panel will be implemented here.
                </p>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
