import React, { useState } from 'react';
import TopBar from './components/TopBar';
import KPITile from './components/KPITile';
import TimeSeriesChart from './components/TimeSeriesChart';
import RevenueWaterfall from './components/RevenueWaterfall';
import SaturationPanel from './components/SaturationPanel';
import ModelComparisonTable from './components/ModelComparisonTable';
import CampaignTable from './components/CampaignTable';
import ExplanationDrawer from './components/ExplanationDrawer';
import { getChannelData } from './mockData';

export default function ChannelDetailContent({ channelId }: { channelId?: string }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerEntity, setDrawerEntity] = useState<string | null>(null);

  const { channelAttribution, modelComparison, timeSeriesData, campaigns, sparklines } = getChannelData(channelId);

  const openDrawer = (entityType: string) => {
    setDrawerEntity(entityType);
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setDrawerEntity(null);
  };

  return (
    <div style={{ minHeight: 'auto', background: 'transparent', display: 'flex', flexDirection: 'column', fontFamily: 'var(--font-sans)' }}>
      <TopBar channelName={channelAttribution.channelName} platform={channelAttribution.platform} />

      <div style={{ padding: '24px 12px 4px', display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '100%', margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>

        {/* Section A: KPI Strip */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '16px' }}>
          <KPITile
            label="Spend"
            value={channelAttribution.spendFormatted}
            sparklineData={sparklines.spend}
            trend={channelAttribution.spendTrend}
            infoTooltip="Total ad spend on this channel for the selected date range."
          />
          <KPITile
            label="Verified Revenue"
            value={channelAttribution.verifiedRevenueFormatted}
            verificationStatus={channelAttribution.verificationStatus}
            infoTooltip="Revenue confirmed by Stripe webhooks. Platform claimed $82,000 — verified revenue is $10,320 lower."
          />
          <KPITile
            label="ROAS"
            value={channelAttribution.roas.formattedEstimate}
            credibleInterval={{
              lower: channelAttribution.roas.formattedLower,
              upper: channelAttribution.roas.formattedUpper,
              bucket: channelAttribution.roas.bucket,
              rangeLabel: channelAttribution.roas.rangeLabel,
            }}
            attributionMethod={channelAttribution.attributionMethod}
            infoTooltip="Return on ad spend from webhook-verified revenue. Range shows 80% credible interval from Bayesian posterior distribution."
          />
          <KPITile
            label="Attribution Weight"
            value={`${(channelAttribution.attributionWeight * 100).toFixed(1)}%`}
            subLabel="of 100% total credit"
            attributionMethod={channelAttribution.attributionMethod}
            infoTooltip="This channel's fractional share of total attribution credit across all active channels."
          />
          <KPITile
            label="Model Agreement"
            value={modelComparison.agreementScore.toFixed(2)}
            agreementScore={modelComparison.agreementScore}
            infoTooltip="Agreement between Bayesian and deterministic attribution models. >= 0.9 = convergent. <0.7 = investigate."
          />
        </div>

        {/* Section B: Time Series */}
        <TimeSeriesChart data={timeSeriesData} />

        {/* Sections C + D: Two-column row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', alignItems: 'start' }}>
          <RevenueWaterfall channelAttribution={channelAttribution} onExplainClick={() => openDrawer('revenue_verification')} />
          <SaturationPanel channelAttribution={channelAttribution} />
        </div>

        {/* Sections E + F: analytical tables on the same plane */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
            gap: '16px',
            alignItems: 'start',
          }}
        >
          <ModelComparisonTable models={modelComparison.models} channelName={channelAttribution.channelName} />
          <CampaignTable campaigns={campaigns} channelAttribution={channelAttribution} />
        </div>
      </div>

      {/* Section G: Explanation Drawer */}
      <ExplanationDrawer isOpen={drawerOpen} entityType={drawerEntity} channelId={channelAttribution.channelId} onClose={closeDrawer} />
    </div>
  );
}
