import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from './PageHeader';
import { Button } from './ui/Button';
import { ScenarioFilterBar } from './BudgetScenarioList/ScenarioFilterBar';
import { ScenarioCard } from './BudgetScenarioList/ScenarioCard';
import { mockApi } from '../services/mockApi';
import { BudgetScenario, ScenarioStats } from '../types/budgetScenarios';
import './budget-scenario-list.css';

function PlusIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

export function BudgetScenarioList() {
  const navigate = useNavigate();
  const [scenarios, setScenarios] = useState<BudgetScenario[]>([]);
  const [stats, setStats] = useState<ScenarioStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filters, setFilters] = useState({
    status: 'all',
    dateRange: 'all',
    goal: 'all',
    sort: 'newest',
  });

  const loadData = async () => {
    try {
      const data = await mockApi.getScenarios();
      setScenarios(data.scenarios);
      setStats(data.stats);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const filteredScenarios = scenarios
    .filter((s) => {
      if (filters.status !== 'all' && s.status !== filters.status) return false;
      if (filters.goal !== 'all' && s.goal !== filters.goal) return false;
      if (searchQuery && !s.name?.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      if (filters.sort === 'newest') return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      if (filters.sort === 'oldest') return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
      return 0;
    });

  return (
    <div className="bsl-page">
      <PageHeader
        title="Budget Scenarios"
        subtitle="Create, compare, and manage budget optimization scenarios"
        actions={
          <>
            <Button variant="secondary" icon={<DownloadIcon />}>
              Export All
            </Button>
            <Button variant="primary" icon={<PlusIcon />} onClick={() => navigate('/budget')}>
              New Scenario
            </Button>
          </>
        }
      />

      {/* Stats */}
      {stats && (
        <div className="bsl-stats">
          <div className="bsl-stat">
            <p className="bsl-stat__label">Active Scenarios</p>
            <p className="bsl-stat__value">{stats.activeCount}</p>
            <span className="bsl-stat__foot" aria-hidden="true" />
          </div>
          <div className="bsl-stat">
            <p className="bsl-stat__label">Applied This Month</p>
            <p className="bsl-stat__value">{stats.appliedThisMonth}</p>
            <span className="bsl-stat__foot" aria-hidden="true" />
          </div>
          <div className="bsl-stat">
            <p className="bsl-stat__label">Avg. Revenue Lift</p>
            <p className="bsl-stat__value bsl-stat__value--green">+{stats.avgRevenueLift}%</p>
            <span className="bsl-stat__foot" aria-hidden="true" />
          </div>
          <div className="bsl-stat">
            <p className="bsl-stat__label">Budget Optimized</p>
            <p className="bsl-stat__value">
              ${(stats.totalBudgetOptimized / 100).toLocaleString()}
            </p>
            <span className="bsl-stat__foot" aria-hidden="true" />
          </div>
        </div>
      )}

      <ScenarioFilterBar
        onSearch={setSearchQuery}
        onFilterChange={handleFilterChange}
        filters={filters}
      />

      <div className="bsl-grid">
        {loading ? (
          <p className="bsl-empty">Loading scenarios…</p>
        ) : filteredScenarios.length === 0 ? (
          <p className="bsl-empty">No scenarios found.</p>
        ) : (
          filteredScenarios.map((scenario) => (
            <ScenarioCard key={scenario.id} scenario={scenario} />
          ))
        )}
      </div>
    </div>
  );
}
