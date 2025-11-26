/**
 * DataIntegrityMonitor Component
 * 
 * FE-UX-016: Data Integrity Monitor Color-Coded Top Borders
 * 
 * Displays platform-level breakdown of revenue verification status
 * Color-coded borders match Revenue Overview (green = verified, amber = unverified)
 * 
 * Features:
 * - Platform card grid with color-coded top borders
 * - Data integrity validation (verifiedTotal + unverifiedTotal = sum of platforms)
 * - Last synced timestamp
 * - Empty state handling
 * - Click handlers for platform drill-down
 */

import { useMemo } from 'react';
import { Clock, Wrench, Link, ChevronRight } from 'lucide-react';
import { ReconciliationStatusIcon, DataIntegritySeal, TrendIndicator } from '@/components/icons';
import { useLocation } from 'wouter';
import { buildImplementationPortalUrl } from '@/types/navigation';
import PlatformCard from './PlatformCard';
import type { PlatformStatus } from '@shared/schema';

export interface PlatformData {
  id: string;
  platform: string;
  platformDisplayName: string;
  status: PlatformStatus;
  matchPercentage?: number;
  revenue: number;
  percentageOfTotal: number;
  isVerified: boolean;
}

export interface DataIntegrityMonitorProps {
  platformData: PlatformData[];
  verifiedTotal: number;
  unverifiedTotal: number;
  lastSynced?: string; // ISO 8601 timestamp
  onCardClick?: (platform: PlatformData) => void;
}

export function DataIntegrityMonitor({
  platformData,
  verifiedTotal,
  unverifiedTotal,
  lastSynced,
  onCardClick,
}: DataIntegrityMonitorProps) {
  const [, navigate] = useLocation();
  
  // Calculate last sync time display
  const lastSyncedDisplay = useMemo(() => {
    if (!lastSynced) return 'Never';
    
    const syncDate = new Date(lastSynced);
    const now = new Date();
    const diffMs = now.getTime() - syncDate.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);
    
    if (diffMinutes < 1) return 'less than a minute ago';
    if (diffMinutes === 1) return '1 minute ago';
    if (diffMinutes < 60) return `${diffMinutes} minutes ago`;
    
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours === 1) return '1 hour ago';
    if (diffHours < 24) return `${diffHours} hours ago`;
    
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return '1 day ago';
    return `${diffDays} days ago`;
  }, [lastSynced]);

  // Data integrity validation
  const { isValid, calculatedVerified, calculatedUnverified, mismatch } = useMemo(() => {
    const calcVerified = platformData
      .filter(p => p.status === 'verified')
      .reduce((sum, p) => sum + p.revenue, 0);
    
    const calcUnverified = platformData
      .filter(p => p.status !== 'verified')
      .reduce((sum, p) => sum + p.revenue, 0);

    const verifiedDiff = Math.abs(calcVerified - verifiedTotal);
    const unverifiedDiff = Math.abs(calcUnverified - unverifiedTotal);
    const tolerance = 0.01;

    const valid = verifiedDiff <= tolerance && unverifiedDiff <= tolerance;
    
    return {
      isValid: valid,
      calculatedVerified: calcVerified,
      calculatedUnverified: calcUnverified,
      mismatch: !valid ? {
        verifiedDiff,
        unverifiedDiff,
      } : null,
    };
  }, [platformData, verifiedTotal, unverifiedTotal]);

  // Log validation warnings in development
  if (!isValid && import.meta.env.DEV) {
    console.warn(
      '[DataIntegrityMonitor] Revenue mismatch detected:',
      `\n  Verified: Expected ${verifiedTotal}, Calculated ${calculatedVerified} (diff: ${mismatch?.verifiedDiff.toFixed(2)})`,
      `\n  Unverified: Expected ${unverifiedTotal}, Calculated ${calculatedUnverified} (diff: ${mismatch?.unverifiedDiff.toFixed(2)})`
    );
  }

  // Handle empty state
  if (platformData.length === 0) {
    return (
      <section 
        className="data-integrity-monitor mt-6 bg-card border border-border rounded-md shadow-sm overflow-hidden"
        aria-labelledby="data-integrity-heading"
        data-testid="data-integrity-monitor"
      >
        {/* Component Header (always visible) */}
        <div className="component-header p-6 border-b border-border">
          <h2 
            id="data-integrity-heading"
            className="text-2xl font-bold text-foreground"
            data-testid="text-integrity-title"
          >
            Data Integrity Monitor
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Live Payment Matching — Breaking down your verified and unverified revenue by platform
          </p>
        </div>

        {/* EMPTY STATE CTA */}
        <div className="p-12" data-testid="empty-state">
          <div className="max-w-xl mx-auto text-center">
            {/* Gradient Background Card */}
            <div className="bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-blue-950/30 dark:via-indigo-950/30 dark:to-purple-950/30
                            border-2 border-dashed border-primary/30 rounded-2xl p-10">
              
              {/* Icon */}
              <div className="w-20 h-20 bg-gradient-to-br from-primary to-indigo-600 dark:from-primary/80 dark:to-indigo-600/80
                              rounded-2xl flex items-center justify-center mx-auto shadow-lg 
                              transform rotate-3 hover:rotate-0 transition-transform duration-300">
                <Link className="w-10 h-10 text-primary-foreground" strokeWidth={2} />
              </div>

              {/* Heading */}
              <h3 className="text-2xl font-bold text-foreground mt-8" data-testid="text-empty-state-title">
                Connect Your First Platform
              </h3>

              {/* Description */}
              <p className="text-sm text-foreground/80 mt-4 leading-relaxed max-w-md mx-auto">
                Link your payment processors and marketing platforms to automatically verify revenue, 
                track attribution, and generate reconciliation reports—all in one unified dashboard.
              </p>

              {/* Benefit List */}
              <div className="mt-6 space-y-2 text-left max-w-sm mx-auto">
                <div className="flex items-start space-x-3">
                  <ReconciliationStatusIcon size={20} status="complete" aria-label="Complete" className="flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-foreground/80">
                    <span className="font-semibold">Automated reconciliation</span> — No more manual CSV matching
                  </p>
                </div>
                
                <div className="flex items-start space-x-3">
                  <TrendIndicator size={20} direction="up" aria-label="Trending up" className="flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-foreground/80">
                    <span className="font-semibold">Real-time attribution</span> — Track which channels drive revenue
                  </p>
                </div>
                
                <div className="flex items-start space-x-3">
                  <DataIntegritySeal size={20} confidence="high" aria-label="High security" className="flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-foreground/80">
                    <span className="font-semibold">Bank-level security</span> — SOC 2 Type II certified infrastructure
                  </p>
                </div>
              </div>

              {/* Supported Platforms Preview */}
              <div className="mt-8 pt-6 border-t border-primary/20">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-4">
                  Supported Platforms
                </p>
                
                <div className="flex items-center justify-center space-x-6 opacity-70 hover:opacity-100 
                                transition-opacity">
                  <div className="text-xs font-medium text-muted-foreground">Stripe</div>
                  <div className="text-xs font-medium text-muted-foreground">Shopify</div>
                  <div className="text-xs font-medium text-muted-foreground">Google Ads</div>
                  <div className="text-xs font-medium text-muted-foreground">Square</div>
                  <span className="text-sm font-medium text-muted-foreground">+8 more</span>
                </div>
              </div>

              {/* Primary CTA Button */}
              <button
                onClick={() => navigate(buildImplementationPortalUrl({ action: 'connect', first: 'true', source: 'empty-state' }))}
                className="mt-8 px-8 py-4 bg-gradient-to-r from-primary to-indigo-600 dark:from-primary/90 dark:to-indigo-600/90
                           hover:from-primary/90 hover:to-indigo-600/90 active:from-primary/80 active:to-indigo-600/80 
                           text-primary-foreground text-base font-bold rounded-xl shadow-lg hover:shadow-xl 
                           transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary 
                           focus:ring-offset-2 inline-flex items-center group"
                aria-label="Open Implementation Portal to connect your first platform"
                data-testid="button-get-started"
              >
                <span>Get Started — Connect Platform</span>
                <ChevronRight className="w-5 h-5 ml-2 group-hover:translate-x-1 transition-transform" />
              </button>

              {/* Setup Time Indicator */}
              <p className="text-xs text-muted-foreground mt-4 flex items-center justify-center space-x-2">
                <Clock className="w-3.5 h-3.5" />
                <span>Most integrations complete in under 5 minutes</span>
              </p>

              {/* Secondary Action */}
              <button
                onClick={() => navigate('/help/integration-guide')}
                className="mt-4 text-xs text-primary hover:text-primary/80 font-medium underline 
                           underline-offset-2 focus:outline-none focus:ring-2 focus:ring-primary 
                           focus:ring-offset-2 rounded px-2 py-1"
                data-testid="link-integration-guide"
              >
                View integration guide
              </button>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Calculate platforms needing attention
  const unmatchedPlatforms = useMemo(() => {
    return platformData.filter(p => p.status !== 'verified' || (p.matchPercentage !== undefined && p.matchPercentage < 100));
  }, [platformData]);

  const unmatchedPlatformCount = unmatchedPlatforms.length;

  return (
    <section 
      className="data-integrity-monitor mt-6 bg-card border border-border rounded-md shadow-sm overflow-hidden"
      aria-labelledby="data-integrity-heading"
      data-testid="data-integrity-monitor"
    >
      {/* Component Header */}
      <div className="component-header p-6 border-b border-border">
        <h2 
          id="data-integrity-heading"
          className="text-2xl font-bold text-foreground"
          data-testid="text-integrity-title"
        >
          Data Integrity Monitor
        </h2>
        
        <p className="text-sm text-muted-foreground mt-1">
          Live Payment Matching — Breaking down your verified and unverified revenue by platform
        </p>
        
        {/* Last Synced Timestamp */}
        <div className="flex items-center text-xs text-muted-foreground mt-2" data-testid="text-last-synced">
          <Clock className="w-3 h-3 mr-1" aria-hidden="true" />
          <span>Last synced: {lastSyncedDisplay}</span>
        </div>

        {/* Data Integrity Warning (Development Only) */}
        {!isValid && import.meta.env.DEV && (
          <div className="mt-2 p-2 bg-destructive/10 border border-destructive/20 rounded text-xs text-destructive flex items-center gap-1" data-testid="warning-mismatch">
            <DataIntegritySeal size={12} confidence="low" aria-label="Warning" />
            <span>Data mismatch detected. Check console for details.</span>
          </div>
        )}
      </div>

      {/* Platform Cards Grid */}
      <div className="p-6">
        <div 
          className="integrity-cards grid grid-cols-1 md:grid-cols-2 gap-4"
          role="list"
          data-testid="grid-platforms"
        >
          {platformData.map((platform) => (
            <div 
              key={platform.id} 
              role="listitem"
              onClick={() => onCardClick?.(platform)}
              className={onCardClick ? 'cursor-pointer' : ''}
            >
              <PlatformCard 
                platform={platform.platform}
                platformDisplayName={platform.platformDisplayName}
                status={platform.status}
                matchPercentage={platform.matchPercentage}
                revenue={platform.revenue}
                percentageOfTotal={platform.percentageOfTotal}
                isVerified={platform.isVerified}
              />
            </div>
          ))}
        </div>
      </div>

      {/* SECONDARY CTA FOOTER - Conditional Rendering */}
      {unmatchedPlatformCount > 0 && (
        <div className="border-t border-border bg-muted/50 px-6 py-4" data-testid="section-secondary-cta">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            {/* Left: Status Summary */}
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-10 h-10 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center">
                <ReconciliationStatusIcon size={20} status="pending" aria-label="Needs attention" />
              </div>
              
              <div>
                <p className="text-sm font-semibold text-foreground" data-testid="text-platforms-attention">
                  {unmatchedPlatformCount} {unmatchedPlatformCount === 1 ? 'platform requires' : 'platforms require'} attention
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  These platforms have incomplete verification or pending transactions
                </p>
              </div>
            </div>

            {/* Right: CTA Button */}
            <button
              onClick={() => navigate(buildImplementationPortalUrl({ tab: 'health', source: 'integrity-monitor' }))}
              className="flex-shrink-0 w-full sm:w-auto inline-flex items-center justify-center 
                         px-4 py-2.5 border-2 border-border bg-card hover-elevate active-elevate-2
                         text-sm font-medium text-foreground rounded-md shadow-sm transition-all 
                         focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 group"
              aria-label="Open Implementation Portal to view platform health"
              data-testid="button-open-implementation-portal"
            >
              <Wrench className="w-4 h-4 mr-2 text-muted-foreground group-hover:text-foreground transition-colors" />
              <span>Open Implementation Portal</span>
            </button>
          </div>

          {/* Quick Actions */}
          <div className="mt-4 pt-4 border-t border-border flex flex-wrap items-center gap-3">
            <span className="text-xs font-medium text-foreground/70">Quick actions:</span>
            
            <button
              onClick={() => navigate(buildImplementationPortalUrl({ action: 'connect', source: 'integrity-monitor' }))}
              className="text-xs text-primary hover:text-primary/80 font-medium underline 
                         underline-offset-2 focus:outline-none focus:ring-2 focus:ring-primary 
                         focus:ring-offset-2 rounded px-1"
              data-testid="link-connect-platform"
            >
              Connect new platform
            </button>
            
            <span className="text-muted-foreground">•</span>
            
            <button
              onClick={() => navigate(buildImplementationPortalUrl({ action: 'retry-sync', source: 'integrity-monitor' }))}
              className="text-xs text-primary hover:text-primary/80 font-medium underline 
                         underline-offset-2 focus:outline-none focus:ring-2 focus:ring-primary 
                         focus:ring-offset-2 rounded px-1"
              data-testid="link-retry-syncs"
            >
              Retry failed syncs
            </button>
          </div>
        </div>
      )}

      {/* SUCCESS STATE FOOTER - When all platforms verified */}
      {unmatchedPlatformCount === 0 && platformData.length > 0 && (
        <div className="border-t border-border bg-green-50 dark:bg-green-950/30 px-6 py-4" data-testid="section-success-footer">
          <div className="flex items-center space-x-3">
            <div className="flex-shrink-0 w-10 h-10 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center">
              <ReconciliationStatusIcon size={20} status="complete" aria-label="All verified" />
            </div>
            
            <div className="flex-1">
              <p className="text-sm font-semibold text-green-900 dark:text-green-100" data-testid="text-all-verified">
                All platforms operating normally
              </p>
              <p className="text-xs text-green-700 dark:text-green-300 mt-0.5">
                100% of connected platforms have complete verification
              </p>
            </div>

            <button
              onClick={() => navigate(buildImplementationPortalUrl({ tab: 'health' }))}
              className="flex-shrink-0 text-xs text-green-700 dark:text-green-300 hover:text-green-900 dark:hover:text-green-100 font-medium 
                         underline underline-offset-2 focus:outline-none focus:ring-2 
                         focus:ring-green-500 focus:ring-offset-2 rounded px-1"
              data-testid="link-health-dashboard"
            >
              View health dashboard →
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
