import React from 'react';

function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

interface ScenarioFilterBarProps {
  onSearch: (query: string) => void;
  onFilterChange: (key: string, value: string) => void;
  filters: {
    status: string;
    dateRange: string;
    goal: string;
    sort: string;
  };
}

export function ScenarioFilterBar({ onSearch, onFilterChange, filters }: ScenarioFilterBarProps) {
  return (
    <div className="sfb-bar">
      {/* Filter selects */}
      <div className="sfb-filters">
        <select
          value={filters.status}
          onChange={(e) => onFilterChange('status', e.target.value)}
          className="sfb-select"
        >
          <option value="all">Status: All</option>
          <option value="processing">Processing</option>
          <option value="completed">Completed</option>
          <option value="applied">Applied</option>
          <option value="rejected">Rejected</option>
        </select>

        <select
          value={filters.dateRange}
          onChange={(e) => onFilterChange('dateRange', e.target.value)}
          className="sfb-select"
        >
          <option value="all">Created: All Time</option>
          <option value="last_7_days">Last 7 Days</option>
          <option value="last_30_days">Last 30 Days</option>
        </select>

        <select
          value={filters.goal}
          onChange={(e) => onFilterChange('goal', e.target.value)}
          className="sfb-select"
        >
          <option value="all">Goal: All</option>
          <option value="maximize_revenue">Maximize Revenue</option>
          <option value="maximize_roas">Maximize ROAS</option>
          <option value="minimize_cac">Minimize CAC</option>
        </select>
      </div>

      {/* Search + sort */}
      <div className="sfb-right">
        <div className="sfb-search-wrap">
          <span className="sfb-search-icon"><SearchIcon /></span>
          <input
            type="text"
            className="sfb-search"
            placeholder="Search scenarios…"
            onChange={(e) => onSearch(e.target.value)}
          />
        </div>

        <select
          value={filters.sort}
          onChange={(e) => onFilterChange('sort', e.target.value)}
          className="sfb-select"
        >
          <option value="newest">Sort: Newest</option>
          <option value="oldest">Sort: Oldest</option>
          <option value="impact">Sort: Impact</option>
        </select>
      </div>
    </div>
  );
}
