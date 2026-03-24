import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../budget-shared.css';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  backHref?: string;
  actions?: React.ReactNode;
}

function ChevronLeftIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

export function PageHeader({ title, subtitle, backHref, actions }: PageHeaderProps) {
  const navigate = useNavigate();

  return (
    <div className="bud-page-header">
      <div className="bud-page-header__meta">
        {backHref && (
          <button className="bud-page-header__back" onClick={() => navigate(backHref)}>
            <ChevronLeftIcon />
            Back
          </button>
        )}
        <h1 className="bud-page-header__title">{title}</h1>
        {subtitle && <p className="bud-page-header__subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="bud-page-header__actions">{actions}</div>}
    </div>
  );
}
