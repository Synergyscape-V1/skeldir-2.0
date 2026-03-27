import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import TopBar from './components/TopBar';
import TrustBand from './components/TrustBand';
import KPIGrid from './components/KPIGrid';
import ActionDirectivesPanel from './components/ActionDirectivesPanel';
import AsyncJobTray from './components/AsyncJobTray';
import ChannelAttributionTable from './components/ChannelAttributionTable';
import RevenueDiscrepancyBanner from './components/RevenueDiscrepancyBanner';
import { MOCK_DATA } from './data';
import './command-center.css';
import { bootstrapAsyncJobRuntime, ensureSeedJobs, getAsyncJobs, subscribeAsyncJobs, type AsyncJob } from '../runtime/asyncJobs';

export default function CommandCenterContent() {
  const navigate = useNavigate();
  const [dateRange, setDateRange] = useState('Last 30 days');
  const [currency, setCurrency] = useState('USD');
  const [attributionModel, setAttributionModel] = useState('bayesian');

  const data = MOCK_DATA;

  const seedJobs = useMemo<AsyncJob[]>(() => {
    // Seed "in-flight" jobs with determinate timing (used for the tray countdown).
    return (data.activeJobs as any[]).map((j) => {
      const base: AsyncJob = {
        jobId: j.jobId,
        type: j.type,
        label: j.label,
        status: j.status,
        elapsedSeconds: typeof j.elapsedSeconds === 'number' ? j.elapsedSeconds : undefined,
        statusMessage: typeof j.statusMessage === 'string' ? j.statusMessage : undefined,
        durationSeconds: typeof j.durationSeconds === 'number' ? j.durationSeconds : undefined,
        maxDurationSeconds: typeof j.durationSeconds === 'number' ? j.durationSeconds : undefined,
        correlationId: typeof j.correlationId === 'string' ? j.correlationId : undefined,
      };

      if (base.status === 'running' || base.status === 'queued') {
        const durationSeconds = base.durationSeconds ?? 60;
        const elapsed = typeof base.elapsedSeconds === 'number' ? base.elapsedSeconds : 0;
        base.durationSeconds = durationSeconds;
        base.maxDurationSeconds = durationSeconds;
        base.startedAtMs = Date.now() - elapsed * 1000;
        base.timeRemainingSeconds = Math.max(0, durationSeconds - elapsed);
      }

      if (base.status === 'complete') {
        base.completedAtMs = Date.now() - 2 * 60 * 1000;
      }

      return base;
    });
    // Intentionally only seeded once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [activeJobs, setActiveJobs] = useState<AsyncJob[]>(() => getAsyncJobs());

  /** Sync Async Job Tray height to Action Directives shell (adjacent columns, desktop only). */
  const directivesShellRef = useRef<HTMLDivElement>(null);
  const [directivesShellHeightPx, setDirectivesShellHeightPx] = useState<number | null>(null);
  const [syncTrayToDirectives, setSyncTrayToDirectives] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 1024px)').matches
  );

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    const onChange = () => setSyncTrayToDirectives(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  useLayoutEffect(() => {
    if (!syncTrayToDirectives) {
      setDirectivesShellHeightPx(null);
      return;
    }
    const el = directivesShellRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const h = entries[0]?.contentRect.height;
      if (typeof h === 'number') setDirectivesShellHeightPx(Math.round(h));
    });
    ro.observe(el);
    setDirectivesShellHeightPx(Math.round(el.getBoundingClientRect().height));
    return () => ro.disconnect();
  }, [syncTrayToDirectives]);

  useEffect(() => {
    bootstrapAsyncJobRuntime();
    ensureSeedJobs(seedJobs);
    setActiveJobs(getAsyncJobs());

    return subscribeAsyncJobs((jobs) => setActiveJobs(jobs));
  }, [seedJobs]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', backgroundColor: '#F8FAFC' }}>
      {/* Top Bar */}
      <TopBar
        dateRange={dateRange}
        currency={currency}
        attributionModel={attributionModel}
        onDateRangeChange={setDateRange}
        onCurrencyChange={setCurrency}
        onModelChange={setAttributionModel}
      />

      {/* Main Content — banner first under TopBar, then Trust Band + KPIs */}
      <div style={{ padding: '10px 12px 0', maxWidth: '100%', margin: '0 auto', width: '100%', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <RevenueDiscrepancyBanner data={data.revenueDiscrepancyAlert} verificationHref="/data" />

        {/* Trust Band */}
        <TrustBand data={data.trustBand} />

        {/* KPI Grid */}
        <KPIGrid data={data.kpiGrid} />

        {/* Action Directives + Async Job Tray — adjacent row (~70% / ~30%) */}
        <div
          className="cc-directives-tray-row"
          style={
            directivesShellHeightPx != null && directivesShellHeightPx > 0
              ? ({ ['--cc-directives-shell-px' as string]: `${directivesShellHeightPx}px` } as React.CSSProperties)
              : undefined
          }
        >
          <div className="cc-directives-panel-wrap">
            <ActionDirectivesPanel ref={directivesShellRef} directives={data.directives} />
          </div>
          <AsyncJobTray jobs={activeJobs} />
        </div>

        {/* Channel Performance Table — full width below */}
        <div className="cc-channel-table-section">
          <ChannelAttributionTable
            channels={data.channels}
            attributionMethod={attributionModel}
            onChannelClick={(channelId) => navigate(`/channels/${channelId}`)}
          />
        </div>
      </div>
    </div>
  );
}
