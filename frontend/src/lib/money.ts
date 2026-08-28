import type { AuthorityClass } from './types';
import { AUTHORITY_CLASSES } from './types';

export type MoneyMinorInput = bigint | string;

export type MoneyParseResult =
  | { ok: true; value: bigint }
  | { ok: false; error: string };

const ISO_CURRENCY = /^[A-Z]{3}$/;

/** Reject Number, float strings, formatted strings, NaN, Infinity, unsafe integers */
export function parseMoneyMinor(input: unknown): MoneyParseResult {
  if (input === null || input === undefined) {
    return { ok: false, error: 'amountMinor is null or undefined' };
  }

  if (typeof input === 'number') {
    return { ok: false, error: 'Number input is forbidden for amountMinor' };
  }

  if (typeof input === 'bigint') {
    return { ok: true, value: input };
  }

  if (typeof input !== 'string') {
    return { ok: false, error: 'amountMinor must be bigint or integer string' };
  }

  const trimmed = input.trim();
  if (!trimmed) {
    return { ok: false, error: 'amountMinor string is empty' };
  }

  if (/[.,$€£¥\s]/.test(trimmed)) {
    return { ok: false, error: 'Formatted or decimal money strings are forbidden' };
  }

  if (!/^-?\d+$/.test(trimmed)) {
    return { ok: false, error: 'amountMinor must be an integer string' };
  }

  try {
    const value = BigInt(trimmed);
    return { ok: true, value };
  } catch {
    return { ok: false, error: 'amountMinor integer conversion failed' };
  }
}

export function isValidIsoCurrencyCode(code: unknown): code is string {
  return typeof code === 'string' && ISO_CURRENCY.test(code);
}

export function subtractMoneyMinor(claimed: bigint, verified: bigint): bigint {
  return claimed - verified;
}

export function isKnownAuthority(value: unknown): value is AuthorityClass {
  return typeof value === 'string' && (AUTHORITY_CLASSES as readonly string[]).includes(value);
}

/** Group integer digits with thousands separators — bigint-safe, display-only */
export function formatMajorUnitsGrouped(major: bigint): string {
  const negative = major < 0n;
  const abs = negative ? -major : major;
  const digits = abs.toString();
  const parts: string[] = [];
  let end = digits.length;
  while (end > 3) {
    parts.unshift(digits.slice(end - 3, end));
    end -= 3;
  }
  parts.unshift(digits.slice(0, end));
  const grouped = parts.join(',');
  return negative ? `-${grouped}` : grouped;
}

/** Display-only formatting with cents — budget simulation spend constraint */
export function formatMoneyMinorDisplayWithCents(amountMinor: bigint, _currencyCode?: string): string {
  const negative = amountMinor < 0n;
  const abs = negative ? -amountMinor : amountMinor;
  const major = abs / 100n;
  const minor = abs % 100n;
  const prefix = negative ? '-$' : '$';
  return `${prefix}${formatMajorUnitsGrouped(major)}.${minor.toString().padStart(2, '0')}`;
}

/** Display-only formatting after integer validation — not authoritative truth */
export function formatMoneyMinorDisplay(amountMinor: bigint, _currencyCode?: string): string {
  const negative = amountMinor < 0n;
  const abs = negative ? -amountMinor : amountMinor;
  const major = abs / 100n;
  const prefix = negative ? '-$' : '$';
  return `${prefix}${formatMajorUnitsGrouped(major)}`;
}

/** Display-only: format basis points as percent with one decimal (integer math, half-up). */
export function formatBpsAsPercentOneDecimal(bps: number): string {
  const sign = bps < 0 ? '-' : '';
  const abs = Math.abs(Math.trunc(bps));
  const tenthsOfPercent = Math.trunc((abs + 5) / 10);
  const whole = Math.trunc(tenthsOfPercent / 10);
  const frac = tenthsOfPercent % 10;
  if (frac === 0) return `${sign}${whole}%`;
  return `${sign}${whole}.${frac}%`;
}
