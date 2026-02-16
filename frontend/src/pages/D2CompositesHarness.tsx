import { useState } from 'react';
import {
  ActivitySection,
  UserInfoCard,
  DataConfidenceBar,
  ConfidenceScoreBadge,
  BulkActionModal,
  BulkActionToolbar,
  ErrorBanner,
  stateKeys,
  activitySectionFixtures,
  dataConfidenceBarFixtures,
  userInfoCardFixtures,
} from '@/components/composites';
import type { DataCompositeStatus } from '@/components/composites';
import { useErrorBanner } from '@/hooks/use-error-banner';
import { VerificationSyncProvider } from '@/contexts/VerificationSyncContext';
import { Badge } from '@/components/ui/badge';
import type { UnmatchedTransaction } from '@shared/schema';
import type { BannerConfig } from '@/types/error-banner';

const stateLabels: Record<(typeof stateKeys)[number], string> = {
  loading: 'Loading',
  empty: 'Empty',
  error: 'Error',
  populated: 'Populated',
};

const statusFromKey = (key: (typeof stateKeys)[number]): DataCompositeStatus =>
  key === 'populated' ? 'success' : key;

// Mock transactions for BulkActionModal/Toolbar (schema-compliant)
const mockTransactions: UnmatchedTransaction[] = [
  {
    id: 'tx-001',
    platform_id: 'stripe',
    platform_name: 'Stripe',
    transaction_id: 'ch_001',
    amount_cents: 125000,
    timestamp: '2026-02-08T10:00:00Z',
    status: 'unmatched',
  },
  {
    id: 'tx-002',
    platform_id: 'paypal',
    platform_name: 'PayPal',
    transaction_id: 'pp_002',
    amount_cents: 89050,
    timestamp: '2026-02-09T14:30:00Z',
    status: 'unmatched',
  },
  {
    id: 'tx-003',
    platform_id: 'shopify',
    platform_name: 'Shopify',
    transaction_id: 'shp_003',
    amount_cents: 342000,
    timestamp: '2026-02-10T09:15:00Z',
    status: 'unmatched',
  },
];

// Static ErrorBanner fixture
const mockBannerConfig: BannerConfig = {
  id: 'harness-banner-001',
  severity: 'warning',
  message: 'D2 Harness: This is a static ErrorBanner rendered with fixture data.',
  duration: 0,
  correlationId: 'harness-corr-001',
  createdAt: Date.now(),
};

export default function D2CompositesHarness() {
  const [activeState, setActiveState] = useState<(typeof stateKeys)[number]>('populated');
  const [showBulkModal, setShowBulkModal] = useState(false);
  const { showBanner } = useErrorBanner();

  const asFix = activitySectionFixtures[activeState];
  const dcbFix = dataConfidenceBarFixtures[activeState];
  const uicFix = userInfoCardFixtures[activeState];

  return (
    <VerificationSyncProvider>
      <div className="min-h-screen bg-background p-6 lg:p-10 space-y-8 max-w-4xl mx-auto">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-foreground">D2 Composites Harness</h1>
          <p className="text-sm text-muted-foreground mt-1">
            State machine proof for data-bearing D2 composites.
            Toggle the state to see loading / empty / error / populated branches.
          </p>
        </div>

        {/* State Toggle Bar */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-muted-foreground mr-2">State:</span>
          {stateKeys.map((key) => (
            <button
              key={key}
              onClick={() => setActiveState(key)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeState === key
                  ? 'bg-foreground text-background'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80'
              }`}
              data-testid={`toggle-${key}`}
            >
              {stateLabels[key]}
            </button>
          ))}
          <Badge variant="outline" className="ml-auto">
            status: {statusFromKey(activeState)}
          </Badge>
        </div>

        {/* Data-bearing composites */}
        <section className="space-y-6">
          <h2 className="text-lg font-semibold text-foreground border-b pb-2">
            Data-Bearing Composites
          </h2>

          {/* ActivitySection */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              ActivitySection
            </label>
            <ActivitySection
              status={asFix.status}
              data={[...asFix.data]}
              onRetry={asFix.onRetry}
            />
          </div>

          {/* UserInfoCard */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              UserInfoCard
            </label>
            <UserInfoCard
              status={uicFix.status}
              username={uicFix.username}
              email={uicFix.email}
              {...('lastLogin' in uicFix && uicFix.lastLogin ? { lastLogin: uicFix.lastLogin } : {})}
              onRetry={uicFix.onRetry}
            />
          </div>

          {/* DataConfidenceBar */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              DataConfidenceBar
            </label>
            <DataConfidenceBar
              status={dcbFix.status}
              overallConfidence={dcbFix.overallConfidence}
              verifiedTransactionPercentage={dcbFix.verifiedTransactionPercentage}
              lastUpdated={dcbFix.lastUpdated}
              trend={dcbFix.trend}
              onRetry={dcbFix.onRetry}
            />
          </div>
        </section>

        {/* Non-data-bearing composites (static showcase) */}
        <section className="space-y-6">
          <h2 className="text-lg font-semibold text-foreground border-b pb-2">
            Non-Data-Bearing Composites (Static)
          </h2>

          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              ConfidenceScoreBadge — high / medium / low tiers
            </label>
            <div className="flex items-center gap-4 flex-wrap">
              <ConfidenceScoreBadge score={85} />
              <ConfidenceScoreBadge score={42} />
              <ConfidenceScoreBadge score={15} />
            </div>
          </div>
        </section>

        {/* D2-P1 Remediated Composites (Bulk Actions + Error Banner) */}
        <section className="space-y-6">
          <h2 className="text-lg font-semibold text-foreground border-b pb-2">
            D2-P1 Remediated Composites
          </h2>

          {/* BulkActionToolbar */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              BulkActionToolbar — D1 Button + Separator
            </label>
            <BulkActionToolbar
              selectedCount={3}
              selectedTotalAmount={5560.50}
              onMarkReviewed={() => console.log('[harness] mark reviewed')}
              onFlagInvestigation={() => console.log('[harness] flag investigation')}
              onExcludeVariance={() => console.log('[harness] exclude variance')}
              onAssignUser={() => console.log('[harness] assign user')}
              onExport={() => console.log('[harness] export')}
              onClearSelection={() => console.log('[harness] clear selection')}
              isProcessing={false}
            />
          </div>

          {/* BulkActionModal */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              BulkActionModal — D1 Dialog + Button + Input + Textarea + Label + Alert
            </label>
            <button
              onClick={() => setShowBulkModal(true)}
              className="px-4 py-2 rounded-md text-sm font-medium bg-muted text-muted-foreground hover:bg-muted/80"
              data-testid="toggle-bulk-modal"
            >
              Open BulkActionModal
            </button>
            {showBulkModal && (
              <BulkActionModal
                action="flag_investigation"
                selectedCount={3}
                selectedTransactions={mockTransactions}
                onConfirm={(meta) => { console.log('[harness] confirm', meta); setShowBulkModal(false); }}
                onCancel={() => setShowBulkModal(false)}
              />
            )}
          </div>

          {/* ErrorBanner (static instance) */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              ErrorBanner — D1 Button (close + action)
            </label>
            <div className="relative">
              <ErrorBanner
                config={mockBannerConfig}
                index={0}
                totalBanners={1}
                onDismiss={(id) => console.log('[harness] dismiss', id)}
              />
            </div>
            <button
              onClick={() => showBanner({
                severity: 'info',
                message: 'D2 Harness: Live banner triggered via useErrorBanner hook.',
                duration: 5000,
              })}
              className="px-4 py-2 rounded-md text-sm font-medium bg-muted text-muted-foreground hover:bg-muted/80"
              data-testid="trigger-live-banner"
            >
              Trigger Live ErrorBanner (via context)
            </button>
          </div>
        </section>
      </div>
    </VerificationSyncProvider>
  );
}
