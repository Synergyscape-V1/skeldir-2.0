import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { PageHeader } from './PageHeader';
import { Button } from './ui/Button';
import { StatusBadge } from './ui/StatusBadge';
import { ProgressIndicator } from './BudgetScenarioDetail/ProgressIndicator';
import { RecommendationSummaryCard } from './BudgetScenarioDetail/RecommendationSummaryCard';
import { ProposedChangesTable } from './BudgetScenarioDetail/ProposedChangesTable';
import { StrategicContextSection } from './BudgetScenarioDetail/StrategicContextSection';
import { mockApi } from '../services/mockApi';
import { BudgetScenario } from '../types/budgetScenarios';
import './budget-scenario-detail.css';

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function SaveIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
      <polyline points="17 21 17 13 7 13 7 21" />
      <polyline points="7 3 7 8 15 8" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function SuccessIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function PendingIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden style={{ animation: 'bsd-spin 1s linear infinite' }}>
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}

function FailIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function getScenarioTitle(scenario: BudgetScenario): string {
  if (scenario.name) return scenario.name;
  const suffix = scenario.id.split('_').pop()?.toUpperCase() || scenario.id;
  return `Budget Recommendation #${suffix}`;
}

export function BudgetScenarioDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [scenario, setScenario] = useState<BudgetScenario | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    if (!id) return;
    let interval: ReturnType<typeof setInterval>;

    const fetchScenario = async () => {
      try {
        const data = await mockApi.getScenarioById(id);
        setScenario(data);
        if (data.status !== 'processing') clearInterval(interval);
      } catch {
        setError('Scenario not found');
      } finally {
        setLoading(false);
      }
    };

    fetchScenario();
    interval = setInterval(fetchScenario, 5000);
    return () => clearInterval(interval);
  }, [id]);

  const handleApply = async () => {
    if (!id) return;
    if (!window.confirm('Are you sure you want to apply these changes? This will update your live ad platforms.')) return;
    setApplying(true);
    try {
      const updated = await mockApi.applyScenario(id);
      setScenario(updated);
    } catch {
      alert('Failed to apply changes. Please try again.');
    } finally {
      setApplying(false);
    }
  };

  const handleReject = async () => {
    if (!id) return;
    if (!window.confirm('Reject this recommendation?')) return;
    try {
      await mockApi.rejectScenario(id);
      navigate('/budget/scenarios');
    } catch {
      alert('Failed to reject scenario.');
    }
  };

  const handleCancel = () => {
    if (window.confirm('Cancel generation?')) navigate('/budget/scenarios');
  };

  if (loading) return <div className="bsd2-loading">Loading scenario details…</div>;

  if (error || !scenario) {
    return (
      <div className="bsd2-not-found">
        <h2>Scenario Not Found</h2>
        <p>The scenario you're looking for doesn't exist or has been deleted.</p>
        <Button variant="primary" onClick={() => navigate('/budget/scenarios')}>
          Back to Scenarios
        </Button>
      </div>
    );
  }

  return (
    <div className="bsd2-page">
      <PageHeader
        title={getScenarioTitle(scenario)}
        backHref="/budget/scenarios"
        actions={<StatusBadge status={scenario.status} />}
      />

      {/* Processing state */}
      {scenario.status === 'processing' && scenario.progress && (
        <ProgressIndicator progress={scenario.progress} onCancel={handleCancel} />
      )}

      {/* Completed state */}
      {(scenario.status === 'completed' || scenario.status === 'applied') && (
        <>
          {scenario.summary && <RecommendationSummaryCard summary={scenario.summary} />}

          {scenario.proposedChanges && (
            <div>
              <h3 className="bsd2-section-title">Proposed Budget Allocation</h3>
              <ProposedChangesTable changes={scenario.proposedChanges} />
            </div>
          )}

          {scenario.strategicContext && (
            <StrategicContextSection context={scenario.strategicContext} audit={scenario.audit} />
          )}

          {/* Applied platform status */}
          {scenario.status === 'applied' && scenario.appliedStatus && (
            <div className="bsd2-applied-panel">
              <h3>Application Status</h3>
              <p>Applied on {new Date(scenario.appliedStatus.appliedAt).toLocaleString()}</p>
              <div className="bsd2-platform-list">
                {scenario.appliedStatus.platformStatus.map((p, i) => (
                  <div key={i} className={`bsd2-platform-chip bsd2-platform-chip--${p.status}`}>
                    {p.status === 'success' ? <SuccessIcon /> : p.status === 'pending' ? <PendingIcon /> : <FailIcon />}
                    <span>{p.platform}</span>
                    <span className="bsd2-platform-status">({p.status})</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions footer — only for completed (not yet applied) */}
          {scenario.status === 'completed' && (
            <div className="bsd2-footer">
              <div className="bsd2-warning">
                <WarningIcon />
                Warning: Applying this changes your live ad platform budgets.
              </div>
              <div className="bsd2-footer-actions">
                <Button variant="secondary" icon={<SaveIcon />}>Save as Scenario</Button>
                <Button variant="tertiary" icon={<DownloadIcon />}>Export PDF</Button>
                <div className="bsd2-divider" />
                <Button variant="danger" icon={<XIcon />} onClick={handleReject}>Reject</Button>
                <Button variant="success" size="lg" icon={<CheckIcon />} onClick={handleApply} isLoading={applying}>
                  Approve & Apply
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Rejected state */}
      {scenario.status === 'rejected' && (
        <div style={{ textAlign: 'center', padding: '40px 20px' }}>
          <p style={{ color: 'var(--bud-gray-500)', fontSize: 15, marginBottom: 16 }}>
            This scenario was rejected.
          </p>
          <Button variant="primary" onClick={() => navigate('/budget')}>
            Create New Scenario
          </Button>
        </div>
      )}
    </div>
  );
}
