import { lazy, Suspense, type ReactNode } from 'react';
import { Navigate, Route, useLocation, useParams } from 'react-router-dom';
import { Skeleton } from '../../components/layout/Skeleton/Skeleton';
import { buildChannelExpandHref } from '../../channels/channelExpandHref';

const ClaimsLedgerPage = lazy(() =>
  import('../../components/claims/ClaimsLedgerPage/ClaimsLedgerPage').then((module) => ({
    default: module.ClaimsLedgerPage,
  })),
);
const ClaimDetailPage = lazy(() =>
  import('../../components/claims/ClaimDetailPage/ClaimDetailPage').then((module) => ({
    default: module.ClaimDetailPage,
  })),
);
const TrustEnvelopeIndexPage = lazy(() =>
  import('../../components/trustIndex/TrustEnvelopeIndexPage/TrustEnvelopeIndexPage').then((module) => ({
    default: module.TrustEnvelopeIndexPage,
  })),
);
const ChannelsOverviewPage = lazy(() =>
  import('../../components/channels/ChannelsOverviewPage/ChannelsOverviewPage').then((module) => ({
    default: module.ChannelsOverviewPage,
  })),
);
const ExceptionsQueuePage = lazy(() =>
  import('../../components/exceptions/ExceptionsQueuePage/ExceptionsQueuePage').then((module) => ({
    default: module.ExceptionsQueuePage,
  })),
);
const BudgetInputPage = lazy(() =>
  import('../../components/budget/BudgetInputPage/BudgetInputPage').then((module) => ({
    default: module.BudgetInputPage,
  })),
);
const BudgetSimulationDetailPage = lazy(() =>
  import('../../components/budget/BudgetSimulationDetailPage/BudgetSimulationDetailPage').then((module) => ({
    default: module.BudgetSimulationDetailPage,
  })),
);

function LedgerRouteFallback() {
  return <Skeleton variant="block" aria-label="Loading page" />;
}

function withLedgerSuspense(element: ReactNode) {
  return <Suspense fallback={<LedgerRouteFallback />}>{element}</Suspense>;
}

function ChannelDetailRedirect() {
  const { channelId = '' } = useParams();
  const location = useLocation();
  return <Navigate to={buildChannelExpandHref(channelId, location.search)} replace />;
}

export function ClaimsLedgerRoute() {
  return withLedgerSuspense(<ClaimsLedgerPage />);
}

export function ClaimDetailRoute() {
  return withLedgerSuspense(<ClaimDetailPage />);
}

export function TrustIndexRoute() {
  return withLedgerSuspense(<TrustEnvelopeIndexPage />);
}

export function ChannelsRoute() {
  return withLedgerSuspense(<ChannelsOverviewPage />);
}

export function ChannelDetailRoute() {
  return <ChannelDetailRedirect />;
}

export function ExceptionsRoute() {
  return withLedgerSuspense(<ExceptionsQueuePage />);
}

export function BudgetRoute() {
  return withLedgerSuspense(<BudgetInputPage />);
}

export function BudgetSimulationDetailRoute() {
  return withLedgerSuspense(<BudgetSimulationDetailPage />);
}

export const LEVEL7_LEDGER_ROUTES = (
  <>
    <Route path="claims" element={<ClaimsLedgerRoute />} />
    <Route path="claims/:claimId" element={<ClaimDetailRoute />} />
    <Route path="trust" element={<TrustIndexRoute />} />
    <Route path="channels" element={<ChannelsRoute />} />
    <Route path="channels/:channelId" element={<ChannelDetailRoute />} />
    <Route path="exceptions" element={<ExceptionsRoute />} />
    <Route path="budget" element={<BudgetRoute />} />
    <Route path="budget/:simulationId" element={<BudgetSimulationDetailRoute />} />
  </>
);
