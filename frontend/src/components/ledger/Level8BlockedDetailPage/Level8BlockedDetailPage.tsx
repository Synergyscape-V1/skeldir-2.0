import { PageSurface } from '../../layout/PageSurface/PageSurface';
import { BlockedDetailPanel } from '../../../ledger/BlockedDetailAffordance';

export function Level8BlockedDetailPage({ surfaceLabel }: { surfaceLabel: string }) {
  return (
    <PageSurface data-level8-blocked-route>
      <BlockedDetailPanel surfaceLabel={surfaceLabel} />
    </PageSurface>
  );
}
