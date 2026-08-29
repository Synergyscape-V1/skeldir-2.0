import { describe, expect, it } from 'vitest';
import { validateBusinessEmail, normalizeEmail } from '../auth/businessEmail';
import {
  resolveSafeRedirect,
  defaultPostLoginPath,
  defaultPostSignupPath,
} from '../auth/redirectGuard';

describe('BusinessEmailInput policy', () => {
  it('accepts business domain email', () => {
    expect(validateBusinessEmail('ops@acme.com')).toEqual({ ok: true, normalized: 'ops@acme.com' });
  });

  it('rejects consumer domain email', () => {
    expect(validateBusinessEmail('user@gmail.com').ok).toBe(false);
  });

  it('normalizes casing and whitespace', () => {
    expect(normalizeEmail('  Ops@Acme.COM ')).toBe('ops@acme.com');
  });

  it('rejects invalid format', () => {
    expect(validateBusinessEmail('not-an-email').ok).toBe(false);
  });
});

describe('Redirect guard', () => {
  it('allows safe fallback when redirect missing', () => {
    expect(resolveSafeRedirect(null, { hasSession: true, hasTenant: true }, defaultPostLoginPath())).toEqual({
      ok: true,
      path: '/entry/session-ready',
    });
  });

  it('rejects external redirect', () => {
    expect(resolveSafeRedirect('https://evil.test', { hasSession: true, hasTenant: true }, defaultPostLoginPath()).ok).toBe(
      false,
    );
  });

  it('rejects javascript redirect', () => {
    expect(
      resolveSafeRedirect('javascript:alert(1)', { hasSession: true, hasTenant: true }, defaultPostLoginPath()).ok,
    ).toBe(false);
  });

  it('allows /app shell route when session and tenant exist', () => {
    expect(resolveSafeRedirect('/app', { hasSession: true, hasTenant: true }, defaultPostLoginPath())).toEqual({
      ok: true,
      path: '/app',
    });
  });

  it('blocks /app without tenant', () => {
    expect(resolveSafeRedirect('/app', { hasSession: true, hasTenant: false }, defaultPostLoginPath()).ok).toBe(
      false,
    );
  });

  it('rejects unknown internal route', () => {
    expect(resolveSafeRedirect('/unknown', { hasSession: true, hasTenant: true }, defaultPostLoginPath()).ok).toBe(
      false,
    );
  });

  it('allows post-signup handoff path', () => {
    expect(
      resolveSafeRedirect('/entry/workspace-created', { hasSession: true, hasTenant: true }, defaultPostSignupPath()),
    ).toEqual({ ok: true, path: '/entry/workspace-created' });
  });

  it('allows onboarding route when session and tenant exist', () => {
    expect(
      resolveSafeRedirect('/onboarding', { hasSession: true, hasTenant: true }, defaultPostSignupPath()),
    ).toEqual({ ok: true, path: '/app/onboarding' });
  });

  it('allows integrations route when session and tenant exist', () => {
    expect(
      resolveSafeRedirect('/integrations', { hasSession: true, hasTenant: true }, defaultPostSignupPath()),
    ).toEqual({ ok: true, path: '/app/integrations' });
  });

  it('allows audit route when session and tenant exist', () => {
    expect(
      resolveSafeRedirect('/audit', { hasSession: true, hasTenant: true }, defaultPostSignupPath()),
    ).toEqual({ ok: true, path: '/app/audit' });
  });

  it('allows claims route when session and tenant exist (Level 7)', () => {
    expect(
      resolveSafeRedirect('/claims', { hasSession: true, hasTenant: true }, defaultPostSignupPath()),
    ).toEqual({ ok: true, path: '/app/claims' });
  });
});
