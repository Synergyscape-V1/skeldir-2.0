import { useSearchParams } from 'react-router-dom';
import { ClaimsLedgerPage } from '../components/claims/ClaimsLedgerPage/ClaimsLedgerPage';
import { TrustEnvelopeIndexPage } from '../components/trustIndex/TrustEnvelopeIndexPage/TrustEnvelopeIndexPage';
import { ChannelsOverviewPage } from '../components/channels/ChannelsOverviewPage/ChannelsOverviewPage';
import { BenchmarksPage } from '../components/benchmarks/BenchmarksPage/BenchmarksPage';
import { ExceptionsQueuePage } from '../components/exceptions/ExceptionsQueuePage/ExceptionsQueuePage';
import { BudgetInputPage } from '../components/budget/BudgetInputPage/BudgetInputPage';
import { Level8BlockedDetailPage } from '../components/ledger/Level8BlockedDetailPage/Level8BlockedDetailPage';
import { createMockSession, createMockTenant } from '../auth/authClient';
import { establishTenant, setBootstrapReady } from '../auth/sessionStore';
import { setCurrentUserRole } from '../governance/governanceStore';
import { useEffect } from 'react';

function SeedFixture() {
  useEffect(() => {
    establishTenant(createMockSession(), createMockTenant());
    setBootstrapReady();
    setCurrentUserRole('owner');
  }, []);
  return null;
}

export function Level7LedgerSpecimens() {
  const [params] = useSearchParams();
  const fixture = params.get('fixture') ?? 'claims-loaded';

  return (
    <div data-level7-specimens>
      <SeedFixture />
      {fixture === 'claims-loaded' || fixture === 'claims-empty' ? <ClaimsLedgerPage /> : null}
      {fixture === 'trust-loaded' ? <TrustEnvelopeIndexPage /> : null}
      {fixture === 'channels-loaded' ? <ChannelsOverviewPage /> : null}
      {fixture === 'benchmarks-unavailable' ? <BenchmarksPage /> : null}
      {fixture === 'exceptions-loaded' ? <ExceptionsQueuePage /> : null}
      {fixture === 'budget-blocked' ? <BudgetInputPage /> : null}
      {fixture === 'detail-blocked' ? <Level8BlockedDetailPage surfaceLabel="Claim detail" /> : null}
    </div>
  );
}
