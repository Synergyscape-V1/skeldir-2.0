/**
 * BudgetScenarioDetailPage - Budget Scenario Detail Interface
 *
 * Route: /budget/scenarios/:scenarioId
 */

import { useLocation } from 'wouter';
import { ArrowLeft, ExternalLink, AlertTriangle } from 'lucide-react';

// ============================================================================
// DESIGN SYSTEM CONSTANTS
// ============================================================================
const COLORS = {
  pageBackground: '#F8F9FA',
  cardBackground: '#FFFFFF',
  borderColor: '#E5E7EB',
  textPrimary: '#212529',
  textSecondary: '#6C757D',
  textBody: '#4B5563',
  successText: '#10B981',
  successBg: '#D1FAE5',
  warningText: '#F59E0B',
  warningBg: '#FEF3C7',
  errorText: '#DC2626',
  primaryBlue: '#3B82F6',
} as const;

// Platform logos
const PlatformLogos: Record<string, { bg: string; text: string }> = {
  'Google Ads': { bg: '#4285F4', text: 'G' },
  'Meta Ads': { bg: '#1877F2', text: 'M' },
  'Pinterest Ads': { bg: '#E60023', text: 'P' },
};

function PlatformLogo({ platform }: { platform: string }) {
  const config = PlatformLogos[platform] || { bg: '#6C757D', text: '?' };
  return (
    <div
      style={{
        width: 32, height: 32, borderRadius: 6, backgroundColor: config.bg,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#FFFFFF', fontSize: 14, fontWeight: 700, marginRight: 12, flexShrink: 0,
      }}
    >
      {config.text}
    </div>
  );
}

function Badge({ variant, children }: { variant: 'success' | 'warning'; children: React.ReactNode }) {
  const styles = {
    success: { bg: COLORS.successBg, text: COLORS.successText },
    warning: { bg: COLORS.warningBg, text: COLORS.warningText },
  };
  const style = styles[variant];
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', padding: '4px 12px',
      fontSize: 12, fontWeight: 600, color: style.text, backgroundColor: style.bg,
      borderRadius: 9999, fontFamily: 'Inter, sans-serif',
    }}>
      {children}
    </span>
  );
}

function PageHeader() {
  const [, navigate] = useLocation();
  return (
    <div style={{ marginBottom: 32 }}>
      <button
        onClick={() => navigate('/budget')}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 4, padding: '6px 12px',
          fontSize: 14, fontWeight: 500, color: COLORS.textSecondary,
          backgroundColor: 'transparent', border: `1px solid ${COLORS.borderColor}`,
          borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif', marginBottom: 16,
        }}
      >
        <ArrowLeft size={16} />
        /budget
      </button>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
        <h1 style={{ fontSize: 30, fontWeight: 700, color: COLORS.textPrimary, margin: 0, fontFamily: 'Inter, sans-serif' }}>
          Budget Recommendation #2471
        </h1>
        <Badge variant="success">Completed</Badge>
      </div>
      <p style={{ fontSize: 16, color: COLORS.textSecondary, margin: 0, fontFamily: 'Inter, sans-serif' }}>
        Optimization based on last 30 days performance (Bayesian MMM).
      </p>
    </div>
  );
}

function RecommendationSummaryCard() {
  return (
    <div style={{
      width: '100%', backgroundColor: COLORS.cardBackground, border: `1px solid ${COLORS.borderColor}`,
      borderRadius: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: 32, marginBottom: 24,
    }}>
      <h2 style={{ fontSize: 24, fontWeight: 600, color: COLORS.textPrimary, margin: 0, marginBottom: 24, fontFamily: 'Inter, sans-serif' }}>
        Shift <strong>$8,500</strong> from Pinterest to Google Search.
      </h2>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 16, fontFamily: 'Inter, sans-serif' }}>
            <span style={{ color: COLORS.successText }}>↗</span>{' '}
            <span style={{ color: COLORS.textPrimary }}>Predicted Revenue: </span>
            <span style={{ color: COLORS.successText, fontWeight: 600 }}>+$24,000 (8.5%)</span>
          </span>
          <Badge variant="success">High Confidence</Badge>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 16, fontFamily: 'Inter, sans-serif' }}>
            <span style={{ color: COLORS.successText }}>↗</span>{' '}
            <span style={{ color: COLORS.textPrimary }}>Predicted ROAS: </span>
            <span style={{ color: COLORS.successText, fontWeight: 600 }}>4.12 (+0.47)</span>
          </span>
          <Badge variant="success">High Confidence</Badge>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 16, fontFamily: 'Inter, sans-serif' }}>
            <span style={{ color: COLORS.textPrimary }}>↗</span>{' '}
            <span style={{ color: COLORS.textPrimary }}>Est. Conversions: </span>
            <span style={{ color: COLORS.textPrimary, fontWeight: 600 }}>+1,200 (10%)</span>
          </span>
          <Badge variant="warning">Medium Confidence</Badge>
        </div>
      </div>
    </div>
  );
}

interface TableRow {
  channel: string;
  currentSpend: string;
  proposedSpend: string;
  change: string;
  changeType: 'positive' | 'negative' | 'neutral';
  expectedRoas: string;
  isTotal?: boolean;
}

const tableData: TableRow[] = [
  { channel: 'Google Ads', currentSpend: '$45,200', proposedSpend: '$53,700', change: '↑ +$8,500', changeType: 'positive', expectedRoas: '4.50 (High)' },
  { channel: 'Meta Ads', currentSpend: '$38,100', proposedSpend: '$38,100', change: '$0', changeType: 'neutral', expectedRoas: '3.80 (High)' },
  { channel: 'Pinterest Ads', currentSpend: '$12,500', proposedSpend: '$4,000', change: '↓ -$8,500', changeType: 'negative', expectedRoas: '2.15 (Medium)' },
  { channel: 'Total', currentSpend: '$95,800', proposedSpend: '$95,800', change: '$0', changeType: 'neutral', expectedRoas: '4.12 (High)', isTotal: true },
];

function ProposedChangesTable() {
  const getChangeColor = (type: TableRow['changeType']) => {
    switch (type) {
      case 'positive': return COLORS.successText;
      case 'negative': return COLORS.errorText;
      default: return COLORS.textSecondary;
    }
  };

  return (
    <div style={{ width: '100%', backgroundColor: COLORS.cardBackground, border: `1px solid ${COLORS.borderColor}`, borderRadius: 12, overflow: 'hidden', marginBottom: 24 }}>
      <div style={{ padding: 24, borderBottom: `1px solid ${COLORS.borderColor}` }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: COLORS.textPrimary, margin: 0, fontFamily: 'Inter, sans-serif' }}>
          Proposed Budget Changes by Channel
        </h3>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'Inter, sans-serif' }}>
        <thead>
          <tr style={{ backgroundColor: COLORS.pageBackground }}>
            {['Channel', 'Current Spend', 'Proposed Spend', 'Change', 'Expected ROAS'].map((h, i) => (
              <th key={h} style={{
                textAlign: i === 0 ? 'left' : 'right', padding: '16px 24px', fontSize: 14,
                fontWeight: 600, color: COLORS.textSecondary, borderBottom: `1px solid ${COLORS.borderColor}`,
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tableData.map((row, index) => (
            <tr key={row.channel} style={{ backgroundColor: row.isTotal ? COLORS.pageBackground : 'transparent' }}>
              <td style={{ padding: '20px 24px', fontSize: 14, color: COLORS.textPrimary, fontWeight: row.isTotal ? 600 : 400, borderBottom: index < tableData.length - 1 ? `1px solid ${COLORS.borderColor}` : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  {!row.isTotal && <PlatformLogo platform={row.channel} />}
                  {row.channel}
                </div>
              </td>
              <td style={{ textAlign: 'right', padding: '20px 24px', fontSize: 14, color: COLORS.textPrimary, fontWeight: row.isTotal ? 600 : 400, borderBottom: index < tableData.length - 1 ? `1px solid ${COLORS.borderColor}` : 'none' }}>{row.currentSpend}</td>
              <td style={{ textAlign: 'right', padding: '20px 24px', fontSize: 14, color: COLORS.textPrimary, fontWeight: row.isTotal ? 600 : 400, borderBottom: index < tableData.length - 1 ? `1px solid ${COLORS.borderColor}` : 'none' }}>{row.proposedSpend}</td>
              <td style={{ textAlign: 'right', padding: '20px 24px', fontSize: 14, color: getChangeColor(row.changeType), fontWeight: row.changeType !== 'neutral' || row.isTotal ? 600 : 400, borderBottom: index < tableData.length - 1 ? `1px solid ${COLORS.borderColor}` : 'none' }}>{row.change}</td>
              <td style={{ textAlign: 'right', padding: '20px 24px', fontSize: 14, color: COLORS.textPrimary, fontWeight: row.isTotal ? 600 : 400, borderBottom: index < tableData.length - 1 ? `1px solid ${COLORS.borderColor}` : 'none' }}>{row.expectedRoas}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StrategicContextCard() {
  return (
    <div style={{ width: '100%', backgroundColor: COLORS.cardBackground, border: `1px solid ${COLORS.borderColor}`, borderRadius: 12, padding: 32, marginBottom: 32 }}>
      <h3 style={{ fontSize: 18, fontWeight: 600, color: COLORS.textPrimary, margin: 0, marginBottom: 16, fontFamily: 'Inter, sans-serif' }}>
        Strategic Context & Rationale
      </h3>
      <p style={{ fontSize: 16, lineHeight: 1.6, color: COLORS.textBody, margin: 0, marginBottom: 20, fontFamily: 'Inter, sans-serif' }}>
        This recommendation shifts budget from Pinterest to Google Search based on the following analysis: Google Search has historically delivered strong and consistent ROAS performance (3.87 average over the past 90 days) with narrow confidence ranges, indicating reliable and predictable returns. Pinterest, while showing potential, has wider confidence intervals and lower average ROAS (2.15), suggesting higher variability in performance outcomes.
      </p>
      <a href="#" onClick={(e) => e.preventDefault()} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 14, color: COLORS.primaryBlue, textDecoration: 'none', fontFamily: 'Inter, sans-serif', fontWeight: 500 }}>
        <ExternalLink size={14} />
        Why these numbers? (View data sources & SQL)
      </a>
    </div>
  );
}

function ActionsSection() {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, maxWidth: 600 }}>
        <AlertTriangle size={18} color={COLORS.warningText} style={{ flexShrink: 0, marginTop: 2 }} />
        <span style={{ fontSize: 14, color: COLORS.textBody, fontFamily: 'Inter, sans-serif', lineHeight: 1.5 }}>
          Applying this changes your live ad platform budgets. Make sure to review platform-specific settings first.
        </span>
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <button style={{ padding: '10px 20px', fontSize: 14, fontWeight: 600, color: '#FFFFFF', backgroundColor: COLORS.successText, border: 'none', borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif' }}>
          Approve & Apply
        </button>
        <button style={{ padding: '10px 20px', fontSize: 14, fontWeight: 600, color: '#FFFFFF', backgroundColor: COLORS.errorText, border: 'none', borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif' }}>
          Reject
        </button>
        <button style={{ padding: '10px 20px', fontSize: 14, fontWeight: 600, color: COLORS.textPrimary, backgroundColor: 'transparent', border: `1px solid ${COLORS.borderColor}`, borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif' }}>
          Save as Scenario
        </button>
        <button style={{ padding: '10px 20px', fontSize: 14, fontWeight: 600, color: COLORS.textPrimary, backgroundColor: 'transparent', border: `1px solid ${COLORS.borderColor}`, borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif' }}>
          Export PDF
        </button>
      </div>
    </div>
  );
}

export default function BudgetScenarioDetailPage() {
  return (
    <div style={{ minHeight: '100vh', backgroundColor: COLORS.pageBackground, padding: '32px 0' }}>
      <div style={{ maxWidth: 1800, margin: '0 auto', padding: '0 32px', fontFamily: 'Inter, sans-serif' }}>
        <PageHeader />
        <RecommendationSummaryCard />
        <ProposedChangesTable />
        <StrategicContextCard />
        <ActionsSection />
      </div>
    </div>
  );
}
