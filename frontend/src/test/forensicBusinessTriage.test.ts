import { describe, expect, it } from 'vitest';
import {
  eventMatchesForensicCategories,
  forensicEventCategory,
  getDefaultForensicDateRange,
  matchesPartialRef,
} from '../operationalAudit/forensicBusinessTriage';

describe('forensic business triage filters', () => {
  it('maps forensic event types to business categories', () => {
    expect(forensicEventCategory('artifact_exported')).toBe('exported');
    expect(forensicEventCategory('policy_decision_rendered')).toBe('approved');
    expect(forensicEventCategory('exception_case_updated')).toBe('resolved');
    expect(forensicEventCategory('bayesian_fit_completed')).toBe('system_action');
  });

  it('filters by selected action categories', () => {
    expect(eventMatchesForensicCategories('artifact_exported', ['exported'])).toBe(true);
    expect(eventMatchesForensicCategories('artifact_exported', ['approved'])).toBe(false);
    expect(eventMatchesForensicCategories('artifact_exported', undefined)).toBe(true);
  });

  it('supports partial order and envelope search', () => {
    expect(matchesPartialRef('ORD-8821', '8821')).toBe(true);
    expect(matchesPartialRef('env_te_9f2a8b1c', '9f2a')).toBe(true);
    expect(matchesPartialRef('ORD-8821', '9999')).toBe(false);
  });

  it('defaults forensic date range to last 7 days', () => {
    const now = new Date('2026-07-07T12:00:00.000Z');
    const { dateFrom, dateTo } = getDefaultForensicDateRange(now);
    expect(dateFrom).toBe('2026-07-01T00:00:00.000Z');
    expect(dateTo).toBe('2026-07-07T23:59:59.999Z');
  });
});
