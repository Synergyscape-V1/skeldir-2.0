import { Link } from 'react-router-dom';
import { Level4RouteGuard } from '../../components/governance/Level4RouteGuard/Level4RouteGuard';
import { TeamSettingsPage } from '../../components/governance/TeamSettingsPage/TeamSettingsPage';
import { PolicySettingsPage } from '../../components/governance/PolicySettingsPage/PolicySettingsPage';
import { BillingPage } from '../../components/billing/BillingPage/BillingPage';
import { GOVERNANCE_COPY } from '../../governance/copy';
import { BILLING_COPY } from '../../billing/copy';
import styles from './GovernanceRoutes.module.css';

export function TeamSettingsRoute() {
  return (
    <Level4RouteGuard>
      <TeamSettingsPage />
    </Level4RouteGuard>
  );
}

export function PolicySettingsRoute() {
  return (
    <Level4RouteGuard>
      <PolicySettingsPage />
    </Level4RouteGuard>
  );
}

export function BillingSettingsRoute() {
  return (
    <Level4RouteGuard>
      <BillingPage />
    </Level4RouteGuard>
  );
}

export function SettingsSubnav() {
  return (
    <nav className={styles.subnav} aria-label="Settings sections" data-settings-subnav>
      <Link to="/app/settings/team" className={styles.subnavLink}>
        Team
      </Link>
      <Link to="/app/settings/policy" className={styles.subnavLink}>
        {GOVERNANCE_COPY.policyPageTitle}
      </Link>
      <Link to="/app/settings/billing" className={styles.subnavLink} data-settings-billing-link>
        {BILLING_COPY.pageTitle}
      </Link>
    </nav>
  );
}
