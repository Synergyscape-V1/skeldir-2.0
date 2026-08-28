import { Navigate, useLocation } from 'react-router-dom';

export function ClaimsAliasRedirect() {
  const { pathname, search } = useLocation();
  const rest = pathname.replace(/^\/claims/, '');
  return <Navigate to={`/app/claims${rest}${search}`} replace />;
}

export function TrustAliasRedirect() {
  const { pathname, search } = useLocation();
  const rest = pathname.replace(/^\/trust/, '');
  return <Navigate to={`/app/trust${rest}${search}`} replace />;
}

export function ChannelsAliasRedirect() {
  const { pathname, search } = useLocation();
  const rest = pathname.replace(/^\/channels/, '');
  return <Navigate to={`/app/channels${rest}${search}`} replace />;
}

export function BenchmarksAliasRedirect() {
  const { search } = useLocation();
  return <Navigate to={`/app/channels${search}`} replace />;
}

export function BudgetAliasRedirect() {
  const { pathname, search } = useLocation();
  const rest = pathname.replace(/^\/budget/, '');
  return <Navigate to={`/app/budget${rest}${search}`} replace />;
}

export function ExceptionsAliasRedirect() {
  const { pathname, search } = useLocation();
  const rest = pathname.replace(/^\/exceptions/, '');
  return <Navigate to={`/app/exceptions${rest}${search}`} replace />;
}
