import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { Typography } from '../../layout/Typography/Typography';
import { Skeleton } from '../../layout/Skeleton/Skeleton';
import { ErrorBanner } from '../../layout/ErrorBanner/ErrorBanner';
import { GOVERNANCE_COPY } from '../../../governance/copy';
import { usePolicySettings } from '../../../governance/usePolicySettings';
import { SettingsSubnav } from '../../../app/routes/GovernanceRoutes';
import { getCurrentUserRole } from '../../../governance/governanceStore';
import { canConfigurePolicy } from '../../../governance/permissions';
import { PermissionDeniedPanel } from '../PermissionDeniedPanel/PermissionDeniedPanel';
import {
  PolicyActionCategoryList,
  PolicyStatusOverview,
} from '../PolicySettings/PolicySettingsComponents';
import { PolicyConfigureModal } from '../PolicyConfigureModal/PolicyConfigureModal';
import styles from './PolicySettingsPage.module.css';

export function PolicySettingsPage() {
  const role = getCurrentUserRole();
  const {
    policy,
    loading,
    error,
    permissionDenied,
    configureCategory,
    setConfigureCategory,
    savePending,
    saveFailed,
    saveCategory,
  } = usePolicySettings();

  if (permissionDenied) {
    return (
      <PageSurface>
        <PermissionDeniedPanel />
      </PageSurface>
    );
  }

  const activeConfig = policy?.categories.find((c) => c.category === configureCategory);

  return (
    <PageSurface data-policy-settings-page>
      <SettingsSubnav />
      <header className={styles.header}>
        <Typography variant="h2">{GOVERNANCE_COPY.policyPageTitle}</Typography>
        <p className={styles.description}>{GOVERNANCE_COPY.policyPageDescription}</p>
      </header>
      {loading ? (
        <Skeleton rows={4} variant="row" />
      ) : error ? (
        <ErrorBanner variant="error" message={error} />
      ) : policy ? (
        <>
          <PolicyStatusOverview modeLabel={policy.modeLabel} />
          <PolicyActionCategoryList
            categories={policy.categories}
            canConfigure={canConfigurePolicy(role)}
            onConfigure={setConfigureCategory}
          />
        </>
      ) : null}
      <PolicyConfigureModal
        open={Boolean(configureCategory)}
        category={configureCategory}
        initialConfig={activeConfig}
        tenantMode={policy?.mode ?? 'design_partner'}
        savePending={savePending}
        saveError={saveFailed ? GOVERNANCE_COPY.policySaveFailed : undefined}
        onClose={() => setConfigureCategory(undefined)}
        onSave={saveCategory}
      />
    </PageSurface>
  );
}
