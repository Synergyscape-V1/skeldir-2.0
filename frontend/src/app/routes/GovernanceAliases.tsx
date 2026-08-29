import { Navigate } from 'react-router-dom';

export function TeamSettingsAliasRedirect() {
  return <Navigate to="/app/settings/team" replace />;
}

export function PolicySettingsAliasRedirect() {
  return <Navigate to="/app/settings/policy" replace />;
}

export function BillingSettingsAliasRedirect() {
  return <Navigate to="/app/settings/billing" replace />;
}
