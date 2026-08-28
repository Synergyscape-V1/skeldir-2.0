import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { Typography } from '../../layout/Typography/Typography';
import { Card } from '../../layout/Card/Card';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { Modal } from '../../layout/Modal/Modal';
import { Table } from '../../layout/Table/Table';
import { BILLING_COPY } from '../../../billing/copy';
import { useTimedCardLoading } from '../../../lib/loading';
import { useBillingSettings } from '../../../billing/useBillingSettings';
import type { BillingInvoiceRow, BillingPlanSummary, BillingStatus } from '../../../billing/types';
import { SettingsSubnav } from '../../../app/routes/GovernanceRoutes';
import { TrustChip, type TrustChipTone } from '../../trust/TrustChip/TrustChip';
import styles from './BillingPage.module.css';

function billingStatusTone(status: BillingStatus): TrustChipTone {
  switch (status) {
    case 'active':
    case 'trialing':
      return 'success';
    case 'past_due':
      return 'warning';
    case 'canceled':
    case 'paused':
      return 'error';
    default:
      return 'neutral';
  }
}

function billingStatusTableLabel(status: BillingStatus): string {
  if (status === 'past_due') return 'Past due';
  return status.replace(/^\w/, (char) => char.toUpperCase());
}

function statusLabel(status: BillingStatus): string {
  switch (status) {
    case 'active':
      return BILLING_COPY.statusActive;
    case 'trialing':
      return BILLING_COPY.statusTrialing;
    case 'past_due':
      return BILLING_COPY.statusPastDue;
    case 'canceled':
      return BILLING_COPY.statusCanceled;
    case 'paused':
      return BILLING_COPY.statusPaused;
    default:
      return status;
  }
}

function invoiceStatusLabel(status: BillingInvoiceRow['status']): string {
  switch (status) {
    case 'paid':
      return BILLING_COPY.invoiceStatusPaid;
    case 'open':
      return BILLING_COPY.invoiceStatusOpen;
    case 'void':
      return BILLING_COPY.invoiceStatusVoid;
    default:
      return status;
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function PlanSummaryCard({ plan }: { plan: BillingPlanSummary }) {
  return (
    <Card title={BILLING_COPY.planSectionTitle} state="populated">
      <dl className={styles.planGrid} data-billing-plan-summary>
        <div>
          <dt>Plan</dt>
          <dd>{plan.label}</dd>
        </div>
        <div>
          <dt>{BILLING_COPY.statusSectionTitle}</dt>
          <dd>
            <TrustChip
              tone={billingStatusTone(plan.status)}
              data-billing-status={plan.status}
              title={statusLabel(plan.status)}
            >
              {billingStatusTableLabel(plan.status)}
            </TrustChip>
          </dd>
        </div>
        {plan.renewalAt ? (
          <div>
            <dt>{BILLING_COPY.renewalLabel}</dt>
            <dd>{formatDate(plan.renewalAt)}</dd>
          </div>
        ) : null}
        {plan.trialEndsAt ? (
          <div>
            <dt>{BILLING_COPY.trialEndsLabel}</dt>
            <dd>{formatDate(plan.trialEndsAt)}</dd>
          </div>
        ) : null}
      </dl>
    </Card>
  );
}

export function BillingPage() {
  const {
    outcome,
    summary,
    canView,
    canManage,
    portalPending,
    portalError,
    confirmOpen,
    requestManageBilling,
    confirmManageBilling,
    cancelManageBilling,
    reload,
  } = useBillingSettings();

  const timedLoading = useTimedCardLoading(outcome.kind === 'loading', { onRetry: reload });

  if (!canView || outcome.kind === 'permission_denied') {
    return (
      <PageSurface data-billing-page data-billing-state="permission_denied">
        <SettingsSubnav />
        <ErrorBanner variant="error" message={BILLING_COPY.permissionDenied} />
      </PageSurface>
    );
  }

  if (outcome.kind === 'loading' && timedLoading) {
    return (
      <PageSurface data-billing-page data-billing-state="loading">
        <SettingsSubnav />
        <Card
          title={BILLING_COPY.pageTitle}
          state={timedLoading.state}
          progressCopy={timedLoading.progressCopy}
          onRetry={timedLoading.onRetry}
        />
      </PageSurface>
    );
  }

  if (outcome.kind === 'network_error') {
    return (
      <PageSurface data-billing-page data-billing-state="network_error">
        <SettingsSubnav />
        <ErrorBanner variant="error" message={BILLING_COPY.networkError} />
      </PageSurface>
    );
  }

  if (outcome.kind === 'portal_unavailable') {
    return (
      <PageSurface data-billing-page data-billing-state="portal_unavailable">
        <SettingsSubnav />
        <ErrorBanner variant="error" message={BILLING_COPY.portalUnavailable} />
      </PageSurface>
    );
  }

  if (outcome.kind === 'cross_tenant_denied') {
    return (
      <PageSurface data-billing-page data-billing-state="cross_tenant_denied">
        <SettingsSubnav />
        <ErrorBanner variant="error" message={BILLING_COPY.permissionDenied} />
      </PageSurface>
    );
  }

  if (outcome.kind === 'empty' || !summary) {
    return (
      <PageSurface data-billing-page data-billing-state="empty">
        <SettingsSubnav />
        <ErrorBanner variant="warning" message={BILLING_COPY.invoicesEmpty} />
      </PageSurface>
    );
  }

  return (
    <PageSurface data-billing-page data-billing-state="loaded">
      <SettingsSubnav />
      <header className={styles.header}>
        <Typography variant="h2">{BILLING_COPY.pageTitle}</Typography>
        <p className={styles.description}>{BILLING_COPY.pageDescription}</p>
      </header>

      <section className={styles.trustBoundary} data-billing-trust-boundary aria-labelledby="billing-trust-boundary-title">
        <Typography variant="h3" id="billing-trust-boundary-title">
          {BILLING_COPY.trustBoundaryTitle}
        </Typography>
        <p>{BILLING_COPY.trustBoundaryBody}</p>
      </section>

      <PlanSummaryCard plan={summary.plan} />

      <Card title={BILLING_COPY.paymentMethodTitle} state="populated">
        {summary.paymentMethod ? (
          <p data-billing-payment-method>
            {BILLING_COPY.paymentMethodSummary(summary.paymentMethod.brand, summary.paymentMethod.last4)}
          </p>
        ) : (
          <p>{BILLING_COPY.paymentMethodNone}</p>
        )}
      </Card>

      <section className={styles.invoicesSection} data-billing-invoices>
        <Typography variant="h3">{BILLING_COPY.invoicesTitle}</Typography>
        {summary.invoices.length === 0 ? (
          <p>{BILLING_COPY.invoicesEmpty}</p>
        ) : (
          <div className={styles.invoiceTableWrap} data-billing-invoice-scroll-wrap>
            <Table
              caption={BILLING_COPY.invoicesTitle}
              columns={[
                { key: 'issued', header: 'Date', render: (row: BillingInvoiceRow) => formatDate(row.issuedAt) },
                { key: 'amount', header: 'Amount', render: (row: BillingInvoiceRow) => row.amountDisplay },
                {
                  key: 'status',
                  header: 'Status',
                  render: (row: BillingInvoiceRow) => invoiceStatusLabel(row.status),
                },
              ]}
              rows={summary.invoices}
              getRowKey={(row) => row.id}
              state="populated"
              density="dense"
            />
          </div>
        )}
      </section>

      {!canManage ? (
        <p className={styles.readOnlyNotice} data-billing-read-only>
          {BILLING_COPY.viewerReadOnlyNotice}
        </p>
      ) : (
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.primaryAction}
            data-billing-manage-action
            aria-busy={portalPending}
            disabled={portalPending}
            onClick={requestManageBilling}
          >
            {portalPending ? BILLING_COPY.manageBillingPending : BILLING_COPY.manageBilling}
          </button>
          <p className={styles.externalHint}>{BILLING_COPY.manageBillingExternalHint}</p>
        </div>
      )}

      {portalError === 'network_error' ? (
        <ErrorBanner variant="error" message={BILLING_COPY.networkError} />
      ) : null}
      {portalError === 'portal_unavailable' ? (
        <ErrorBanner variant="error" message={BILLING_COPY.portalUnavailable} />
      ) : null}

      <Modal
        open={confirmOpen}
        onClose={cancelManageBilling}
        title={BILLING_COPY.manageBillingConfirmTitle}
        type="standard"
      >
        <p>{BILLING_COPY.manageBillingConfirmBody}</p>
        <p className={styles.externalHint}>{BILLING_COPY.manageBillingExternalHint}</p>
        <div className={styles.modalActions}>
          <button type="button" className={styles.secondaryAction} onClick={cancelManageBilling}>
            {BILLING_COPY.manageBillingCancel}
          </button>
          <button
            type="button"
            className={styles.primaryAction}
            data-billing-portal-confirm
            aria-busy={portalPending}
            disabled={portalPending}
            onClick={() => void confirmManageBilling()}
          >
            {BILLING_COPY.manageBillingConfirmAction}
          </button>
        </div>
      </Modal>
    </PageSurface>
  );
}
