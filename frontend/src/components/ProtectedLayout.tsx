/**
 * D3.1 ProtectedLayout — Wraps AppShell with nested route rendering
 * 
 * For D3.1 baseline: renders AppShell without auth guard.
 * Future: Add authentication check and redirect to login if unauthenticated.
 */

import AppShell from '@/components/AppShell'

export default function ProtectedLayout() {
  // D3.1: No auth guard for baseline validation
  // Future: Add useAuth check and redirect
  
  return <AppShell />
}
