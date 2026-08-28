const FREE_EMAIL_DOMAINS = new Set([
  'gmail.com',
  'googlemail.com',
  'yahoo.com',
  'yahoo.co.uk',
  'hotmail.com',
  'outlook.com',
  'live.com',
  'icloud.com',
  'aol.com',
  'proton.me',
  'protonmail.com',
  'mail.com',
  'gmx.com',
  'yandex.com',
  'zoho.com',
]);

export type BusinessEmailValidation =
  | { ok: true; normalized: string }
  | { ok: false; reason: 'empty' | 'invalid_format' | 'consumer_domain' };

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normalizeEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

export function validateBusinessEmail(raw: string): BusinessEmailValidation {
  const normalized = normalizeEmail(raw);
  if (!normalized) return { ok: false, reason: 'empty' };
  if (!EMAIL_PATTERN.test(normalized)) return { ok: false, reason: 'invalid_format' };

  const domain = normalized.split('@')[1];
  if (!domain || FREE_EMAIL_DOMAINS.has(domain)) {
    return { ok: false, reason: 'consumer_domain' };
  }

  return { ok: true, normalized };
}
