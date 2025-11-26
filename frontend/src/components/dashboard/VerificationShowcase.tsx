import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import EmptyState from '@/components/EmptyState';
import PlatformCard from './PlatformCard';
import { Clock, AlertTriangle } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { useQuery } from '@tanstack/react-query';
import { useState, useEffect, useRef } from 'react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import type { SyncStatus, RevenueBreakdown, ActiveIntegrationsResponse } from '@shared/schema';

interface StatusChange {
  platform: string;
  oldStatus: string;
  newStatus: string;
}

export function VerificationShowcase() {
  const { data: syncStatus } = useQuery<SyncStatus>({
    queryKey: ['/api/sync-status'],
    refetchInterval: 30000,
  });

  const { data: revenueData } = useQuery<RevenueBreakdown>({
    queryKey: ['/api/revenue-breakdown'],
    refetchInterval: 30000,
  });

  const { data: integrationsResponse } = useQuery<ActiveIntegrationsResponse>({
    queryKey: ['/api/integrations/active'],
    refetchInterval: 30000,
  });

  const integrations = integrationsResponse?.integrations;

  // Track previous integration status for change detection
  const prevIntegrationsRef = useRef<typeof integrations>();
  const [recentStatusChanges, setRecentStatusChanges] = useState<StatusChange[]>([]);
  const [animatingPlatforms, setAnimatingPlatforms] = useState<Set<string>>(new Set());

  // Task 1.1: Staleness detection - check if lastSynced is >5 minutes old
  const isStale = syncStatus?.lastSynced 
    ? (Date.now() - new Date(syncStatus.lastSynced).getTime()) > 5 * 60 * 1000
    : false;

  const timeAgo = syncStatus?.lastSynced 
    ? formatDistanceToNow(new Date(syncStatus.lastSynced), { addSuffix: true })
    : 'Never';

  // Task 1.2: Status change detection
  useEffect(() => {
    if (!integrations || !prevIntegrationsRef.current) {
      prevIntegrationsRef.current = integrations;
      return;
    }

    const changes: StatusChange[] = [];
    integrations.forEach(current => {
      const previous = prevIntegrationsRef.current?.find(p => p.platform === current.platform);
      if (previous && previous.status !== current.status) {
        changes.push({
          platform: current.platform,
          oldStatus: previous.status,
          newStatus: current.status,
        });

        // Track pending→verified transitions for success animation
        if (previous.status === 'pending' && current.status === 'verified') {
          setAnimatingPlatforms(prev => new Set(prev).add(current.platform));
          // Remove from animation set after animation completes
          setTimeout(() => {
            setAnimatingPlatforms(prev => {
              const next = new Set(prev);
              next.delete(current.platform);
              return next;
            });
          }, 1200); // 400ms scale + 800ms border
        }
      }
    });

    if (changes.length > 0) {
      setRecentStatusChanges(changes);
    }

    prevIntegrationsRef.current = integrations;
  }, [integrations]);

  // Helper function to calculate percentage contribution
  const calculatePercentage = (amount: number, total: number): string => {
    if (total === 0) return '0.00';
    return ((amount / total) * 100).toFixed(2);
  };


  // Get correct total based on status for percentage calculation
  const getRelevantTotal = (status: string): number => {
    switch (status) {
      case 'verified':
        return revenueData?.verifiedTotal || 0;
      case 'partial':
      case 'unverified':
      case 'pending':
        return revenueData?.unverifiedTotal || 0;
      default:
        return (revenueData?.verifiedTotal || 0) + (revenueData?.unverifiedTotal || 0);
    }
  };

  // Build platform cards from integrations data
  const platformCards = integrations?.map(integration => {
    return {
      platform: integration.platform,
      brandColor: integration.brandColor,
      status: integration.status,
      amount: integration.amount || 0,
      matchPercentage: integration.matchPercentage || 0,
    };
  }) || [];

  // Validation: Check if integration amounts match corresponding revenue data
  // Compare integration amounts against revenue data amounts for same platforms
  const isDataValid = platformCards.every(card => {
    const platformRevenue = revenueData?.platforms?.find(p => p.platform === card.platform);
    if (!platformRevenue) return true; // Skip if no revenue data for this platform
    return Math.abs(card.amount - platformRevenue.amount) <= 0.01;
  });

  // Calculate totals from integration data and revenue data separately
  const integrationTotal = platformCards.reduce((sum, card) => sum + card.amount, 0);
  const revenueTotal = revenueData?.platforms
    ?.filter(p => platformCards.some(c => c.platform === p.platform))
    .reduce((sum, p) => sum + p.amount, 0) || 0;

  // Handle empty state
  if (!integrations || integrations.length === 0) {
    return (
      <Card 
        className="shadow-xl" 
        style={{ 
          backgroundColor: 'hsl(var(--brand-alice) / 0.6)',
          borderColor: 'hsl(var(--brand-jordy) / 0.3)'
        }}
        data-testid="card-verification-badges"
      >
        <CardHeader>
          <CardTitle style={{ color: 'hsl(var(--brand-cool-black))' }}>Data Integrity Monitor</CardTitle>
          <CardDescription className="text-sm" style={{ color: '#6B7280' }}>
            Live Payment Matching
          </CardDescription>
          <TooltipProvider>
            <div className="flex items-center gap-1.5 mt-2" data-testid="sync-status">
              <Clock className="w-3 h-3" style={{ color: isStale ? '#F59E0B' : '#6B7280' }} data-testid="icon-clock" />
              <span className="text-[11px]" style={{ color: isStale ? '#F59E0B' : '#6B7280' }} data-testid="text-last-synced">
                Last synced: {timeAgo}
              </span>
              {isStale && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <AlertTriangle 
                      className="w-4 h-4" 
                      style={{ color: '#F59E0B' }} 
                      data-testid="icon-staleness-warning"
                    />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs">Status data may be outdated. Refresh page if issues persist.</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          </TooltipProvider>
        </CardHeader>
        <CardContent className="flex justify-center">
          <EmptyState />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      {!isDataValid && revenueData && (
        <div 
          className="mb-4 p-3 rounded-lg border-l-4"
          style={{ 
            backgroundColor: '#FEF2F2', 
            borderColor: '#EF4444',
          }}
          data-testid="validation-error-banner"
        >
          <p className="text-sm font-semibold" style={{ color: '#B91C1C' }}>
            ⚠️ Data Integrity Warning
          </p>
          <p className="text-xs mt-1" style={{ color: '#991B1B' }}>
            Platform integration data (${integrationTotal.toFixed(2)}) does not match revenue data (${revenueTotal.toFixed(2)})
          </p>
        </div>
      )}
      <Card 
        className="shadow-xl" 
        style={{ 
          backgroundColor: 'hsl(var(--brand-alice) / 0.6)',
          borderColor: 'hsl(var(--brand-jordy) / 0.3)'
        }}
        data-testid="card-verification-badges"
      >
        <CardHeader>
          <CardTitle style={{ color: 'hsl(var(--brand-cool-black))' }}>Data Integrity Monitor</CardTitle>
          <CardDescription className="text-sm" style={{ color: '#6B7280' }}>
            Live Payment Matching
          </CardDescription>
          <TooltipProvider>
            <div className="flex items-center gap-1.5 mt-2" data-testid="sync-status">
              <Clock className="w-3 h-3" style={{ color: isStale ? '#F59E0B' : '#6B7280' }} data-testid="icon-clock" />
              <span className="text-[11px]" style={{ color: isStale ? '#F59E0B' : '#6B7280' }} data-testid="text-last-synced">
                Last synced: {timeAgo}
              </span>
              {isStale && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <AlertTriangle 
                      className="w-4 h-4" 
                      style={{ color: '#F59E0B' }} 
                      data-testid="icon-staleness-warning"
                    />
                  </TooltipTrigger>
                  <TooltipContent>
                    <p className="text-xs">Status data may be outdated. Refresh page if issues persist.</p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          </TooltipProvider>
        </CardHeader>
        <CardContent 
          className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 gap-4 ${
            platformCards.length > 4 ? 'max-h-[520px] overflow-y-auto' : ''
          }`}
        >
          {platformCards.map((card) => (
            <div 
              key={card.platform}
              className={animatingPlatforms.has(card.platform) ? 'success-animation' : ''}
            >
              <PlatformCard
                platform={card.platform}
                platformDisplayName={card.platform}
                status={card.status}
                matchPercentage={card.matchPercentage}
                revenue={card.amount}
                percentageOfTotal={parseFloat(calculatePercentage(card.amount, getRelevantTotal(card.status)))}
                isVerified={card.status === 'verified'}
              />
            </div>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
