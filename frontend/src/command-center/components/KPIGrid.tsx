import React from 'react';
import KPITile from './KPITile';
import type { KPITileProps } from './KPITile';

export interface CommandCenterKpiGrid {
  blendedCpl: KPITileProps;
  leadToCustomer: KPITileProps;
  blendedCac: KPITileProps;
  monthlyVerifiedRevenue: KPITileProps;
}

export default function KPIGrid({ data }: { data: CommandCenterKpiGrid }) {
  const { blendedCpl, leadToCustomer, blendedCac, monthlyVerifiedRevenue } = data;

  return (
    <section className="cc-kpi-grid" aria-label="Key performance indicators">
      <KPITile {...blendedCpl} />
      <KPITile {...leadToCustomer} />
      <KPITile {...blendedCac} />
      <KPITile {...monthlyVerifiedRevenue} />
    </section>
  );
}
