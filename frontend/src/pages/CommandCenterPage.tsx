/**
 * Command Center Page — Final A4-ATLAS × A2-MERIDIAN Hybrid
 *
 * Root (/) authenticated route. Renders the composed Command Center:
 *   - A4-ATLAS KPI tiles (Total Revenue, Active Channels, Model Confidence)
 *   - A2-MERIDIAN Priority Actions
 *   - A2-MERIDIAN Channel Performance Table (with SVG platform logos)
 *
 * Full state machine (loading/empty/error/ready), 30s/5min polling.
 */

import { CommandCenter } from '@/components/command-center/CommandCenter';

export default function CommandCenterPage() {
  return <CommandCenter />;
}
