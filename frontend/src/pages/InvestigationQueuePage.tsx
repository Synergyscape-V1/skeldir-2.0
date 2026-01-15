/**
 * InvestigationQueuePage - Investigation Queue Interface
 *
 * Route: /investigations
 */

import { useState } from 'react';
import { Calendar, ChevronDown, ChevronLeft, ChevronRight, AlertTriangle } from 'lucide-react';

// ============================================================================
// DESIGN SYSTEM CONSTANTS
// ============================================================================
const COLORS = {
  pageBackground: '#F8F9FA',
  cardBackground: '#FFFFFF',
  borderColor: '#E5E7EB',
  borderLight: '#F3F4F6',
  textPrimary: '#212529',
  textSecondary: '#6C757D',
  primaryBlue: '#3B82F6',
  completedText: '#10B981',
  completedBg: '#D1FAE5',
  pendingText: '#F59E0B',
  pendingBg: '#FEF3C7',
  failedText: '#EF4444',
  failedBg: '#FEE2E2',
  highText: '#EF4444',
  highBg: '#FEE2E2',
  mediumText: '#F59E0B',
  mediumBg: '#FEF3C7',
  lowText: '#3B82F6',
  lowBg: '#EFF6FF',
  progressTrack: '#E5E7EB',
  progressFill: '#3B82F6',
} as const;

type InvestigationStatus = 'pending' | 'completed' | 'failed';
type Priority = 'high' | 'medium' | 'low';

interface Investigation {
  id: string;
  question: string;
  status: InvestigationStatus;
  cost: string;
  createdDate: string;
  priority: Priority;
  timeRemaining?: string;
  progress?: number;
}

const investigations: Investigation[] = [
  { id: '#INV-2471', question: 'Why did Google Ads CPA increase by 15%?', status: 'pending', cost: '$0.08', createdDate: 'Oct 26, 2023, 10:30 AM', priority: 'high', timeRemaining: '60s', progress: 45 },
  { id: '#INV-2470', question: 'What is the optimal budget allocation for next month?', status: 'completed', cost: '$0.12', createdDate: 'Oct 25, 2023, 2:15 PM', priority: 'medium' },
  { id: '#INV-2469', question: 'Identify channels with declining ROAS.', status: 'failed', cost: '$0.05', createdDate: 'Oct 24, 2023, 9:00 AM', priority: 'low' },
  { id: '#INV-2468', question: 'Analyze impact of recent creative changes.', status: 'completed', cost: '$0.10', createdDate: 'Oct 23, 2023, 4:45 PM', priority: 'medium' },
  { id: '#INV-2467', question: 'Forecast revenue for Q4 with 10% spend increase.', status: 'completed', cost: '$0.15', createdDate: 'Oct 22, 2023, 11:00 AM', priority: 'high' },
];

function FilterDropdown({ label, value, icon }: { label: string; value: string; icon?: React.ReactNode }) {
  return (
    <button style={{
      display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 12px',
      fontSize: 14, fontWeight: 400, color: COLORS.textPrimary,
      backgroundColor: COLORS.cardBackground, border: `1px solid ${COLORS.borderColor}`,
      borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif', whiteSpace: 'nowrap',
    }}>
      {icon}
      <span>
        {label && <span style={{ color: COLORS.textSecondary }}>{label} </span>}
        {value}
      </span>
      <ChevronDown size={16} color={COLORS.textSecondary} />
    </button>
  );
}

function StatusBadge({ status, timeRemaining, progress }: { status: InvestigationStatus; timeRemaining?: string; progress?: number }) {
  const statusConfig = {
    pending: { text: 'Pending', bg: COLORS.pendingBg, color: COLORS.pendingText },
    completed: { text: 'Completed', bg: COLORS.completedBg, color: COLORS.completedText },
    failed: { text: 'Failed', bg: COLORS.failedBg, color: COLORS.failedText },
  };
  const config = statusConfig[status];

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{
        display: 'inline-flex', alignItems: 'center', padding: '4px 10px',
        fontSize: 12, fontWeight: 500, color: config.color, backgroundColor: config.bg,
        borderRadius: 9999, fontFamily: 'Inter, sans-serif',
      }}>
        {config.text}
      </span>
      {status === 'pending' && progress !== undefined && (
        <>
          <div style={{ width: 40, height: 4, backgroundColor: COLORS.progressTrack, borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ width: `${progress}%`, height: '100%', backgroundColor: COLORS.progressFill, borderRadius: 2 }} />
          </div>
          {timeRemaining && <span style={{ fontSize: 12, color: COLORS.textSecondary, fontFamily: 'Inter, sans-serif' }}>{timeRemaining}</span>}
        </>
      )}
    </div>
  );
}

function PriorityBadge({ priority }: { priority: Priority }) {
  const priorityConfig = {
    high: { text: 'High', bg: COLORS.highBg, color: COLORS.highText, showIcon: true },
    medium: { text: 'Medium', bg: COLORS.mediumBg, color: COLORS.mediumText, showIcon: false },
    low: { text: 'Low', bg: COLORS.lowBg, color: COLORS.lowText, showIcon: false },
  };
  const config = priorityConfig[priority];

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 10px',
      fontSize: 12, fontWeight: 500, color: config.color, backgroundColor: config.bg,
      borderRadius: 9999, fontFamily: 'Inter, sans-serif',
    }}>
      {config.showIcon && <AlertTriangle size={12} />}
      {config.text}
    </span>
  );
}

function PageHeader() {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 32, flexWrap: 'wrap', gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 36, fontWeight: 600, color: COLORS.textPrimary, margin: 0, fontFamily: 'Inter, sans-serif' }}>
          Investigations
        </h1>
        <p style={{ fontSize: 16, color: COLORS.textSecondary, margin: 0, marginTop: 8, fontFamily: 'Inter, sans-serif' }}>
          Manage and review your AI-driven marketing investigations.
        </p>
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <FilterDropdown label="" value="Last 30 Days" icon={<Calendar size={16} color={COLORS.textSecondary} />} />
        <FilterDropdown label="Status:" value="All" />
        <FilterDropdown label="Type:" value="All" />
        <FilterDropdown label="Sort:" value="Date (Newest)" />
      </div>
    </div>
  );
}

function AskSkeldrCard() {
  const [question, setQuestion] = useState('');

  return (
    <div style={{ width: '100%', backgroundColor: COLORS.cardBackground, border: `1px solid ${COLORS.borderColor}`, borderRadius: 12, padding: 24, marginBottom: 32 }}>
      <h2 style={{ fontSize: 18, fontWeight: 600, color: COLORS.textPrimary, margin: 0, marginBottom: 16, fontFamily: 'Inter, sans-serif' }}>
        Ask Skeldir a Question
      </h2>
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder='e.g., "Why did Facebook Ads ROAS drop last week?"'
        style={{
          width: '100%', minHeight: 80, padding: 16, fontSize: 14, fontFamily: 'Inter, sans-serif',
          color: COLORS.textPrimary, backgroundColor: COLORS.cardBackground,
          border: `1px solid ${COLORS.borderColor}`, borderRadius: 8, resize: 'vertical',
          outline: 'none', boxSizing: 'border-box',
        }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16, flexWrap: 'wrap', gap: 12 }}>
        <span style={{ fontSize: 14, color: COLORS.textSecondary, fontFamily: 'Inter, sans-serif' }}>
          Estimated cost: ~$0.05 | Queue position: 1
        </span>
        <button style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: '10px 20px',
          fontSize: 14, fontWeight: 600, color: '#FFFFFF', backgroundColor: COLORS.primaryBlue,
          border: 'none', borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif',
        }}>
          Submit Investigation
        </button>
      </div>
    </div>
  );
}

function PaginationButton({ page, isActive }: { page: number; isActive?: boolean }) {
  return (
    <button style={{
      minWidth: 32, height: 32, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 14, fontWeight: isActive ? 500 : 400, color: isActive ? COLORS.primaryBlue : COLORS.textPrimary,
      backgroundColor: isActive ? '#EFF6FF' : 'transparent', border: isActive ? `1px solid ${COLORS.primaryBlue}` : '1px solid transparent',
      borderRadius: 6, cursor: 'pointer', fontFamily: 'Inter, sans-serif',
    }}>
      {page}
    </button>
  );
}

function InvestigationQueueTable() {
  return (
    <div style={{ width: '100%', backgroundColor: COLORS.cardBackground, border: `1px solid ${COLORS.borderColor}`, borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ padding: 24, borderBottom: `1px solid ${COLORS.borderColor}` }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: COLORS.textPrimary, margin: 0, fontFamily: 'Inter, sans-serif' }}>
          Investigation Queue
        </h3>
      </div>
      <div style={{ padding: '0 24px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'Inter, sans-serif' }}>
          <thead>
            <tr>
              {['Investigation ID', 'Question/Hypothesis', 'Status', 'Cost', 'Created Date', 'Priority'].map((h, i) => (
                <th key={h} style={{
                  textAlign: 'left', padding: i === 0 ? '16px 0' : '16px 16px',
                  fontSize: 12, fontWeight: 600, color: COLORS.textSecondary,
                  borderBottom: `1px solid ${COLORS.borderLight}`, whiteSpace: 'nowrap',
                }}>
                  {h} <ChevronDown size={12} style={{ display: 'inline', verticalAlign: 'middle' }} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {investigations.map((inv, index) => (
              <tr key={inv.id}>
                <td style={{ padding: '20px 0', fontSize: 14, fontWeight: 500, color: COLORS.textPrimary, borderBottom: index < investigations.length - 1 ? `1px solid ${COLORS.borderLight}` : 'none', whiteSpace: 'nowrap' }}>{inv.id}</td>
                <td style={{ padding: '20px 16px', fontSize: 14, color: COLORS.textPrimary, borderBottom: index < investigations.length - 1 ? `1px solid ${COLORS.borderLight}` : 'none' }}>{inv.question}</td>
                <td style={{ padding: '20px 16px', borderBottom: index < investigations.length - 1 ? `1px solid ${COLORS.borderLight}` : 'none' }}>
                  <StatusBadge status={inv.status} timeRemaining={inv.timeRemaining} progress={inv.progress} />
                </td>
                <td style={{ padding: '20px 16px', fontSize: 14, color: COLORS.textPrimary, borderBottom: index < investigations.length - 1 ? `1px solid ${COLORS.borderLight}` : 'none', whiteSpace: 'nowrap' }}>{inv.cost}</td>
                <td style={{ padding: '20px 16px', fontSize: 14, color: COLORS.textPrimary, borderBottom: index < investigations.length - 1 ? `1px solid ${COLORS.borderLight}` : 'none', whiteSpace: 'nowrap' }}>{inv.createdDate}</td>
                <td style={{ padding: '20px 0', borderBottom: index < investigations.length - 1 ? `1px solid ${COLORS.borderLight}` : 'none' }}>
                  <PriorityBadge priority={inv.priority} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ padding: '16px 24px', borderTop: `1px solid ${COLORS.borderColor}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 14, color: COLORS.textSecondary, fontFamily: 'Inter, sans-serif' }}>
          Showing 1-5 of 24 investigations
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '6px 10px', fontSize: 14, color: COLORS.textSecondary, backgroundColor: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'Inter, sans-serif' }}>
            <ChevronLeft size={16} /> Previous
          </button>
          <PaginationButton page={1} isActive />
          <PaginationButton page={2} />
          <PaginationButton page={3} />
          <span style={{ padding: '6px 8px', fontSize: 14, color: COLORS.textSecondary }}>...</span>
          <PaginationButton page={5} />
          <button style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '6px 10px', fontSize: 14, color: COLORS.textPrimary, backgroundColor: 'transparent', border: 'none', cursor: 'pointer', fontFamily: 'Inter, sans-serif' }}>
            Next <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

export default function InvestigationQueuePage() {
  return (
    <div style={{ minHeight: '100vh', backgroundColor: COLORS.pageBackground, padding: '32px 0' }}>
      <div style={{ maxWidth: 1800, margin: '0 auto', padding: '0 32px', fontFamily: 'Inter, sans-serif' }}>
        <PageHeader />
        <AskSkeldrCard />
        <InvestigationQueueTable />
      </div>
    </div>
  );
}
