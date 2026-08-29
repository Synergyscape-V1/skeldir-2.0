/** Entry-point contract for Sequential Triage Nodes (CDO Audit 2). */
export const TRIAGE_SOURCE = 'command_center_queue' as const;

export type TriageSearch =
  | { isTriage: false; malformed?: boolean }
  | {
      isTriage: true;
      issueId: string;
      issueIndex: number;
      issueTotal: number;
    };

export function buildTriageHref(
  baseHref: string,
  issueId: string,
  issueIndex: number,
  issueTotal: number,
): string {
  const url = new URL(baseHref, 'https://skeldir.local');
  url.searchParams.set('source', TRIAGE_SOURCE);
  url.searchParams.set('issueId', issueId);
  url.searchParams.set('issueIndex', String(issueIndex));
  url.searchParams.set('issueTotal', String(issueTotal));
  return `${url.pathname}${url.search}${url.hash}`;
}

export function parseTriageSearch(searchParams: URLSearchParams): TriageSearch {
  const source = searchParams.get('source');
  if (source !== TRIAGE_SOURCE) {
    return { isTriage: false };
  }
  const issueId = searchParams.get('issueId');
  const issueIndex = Number(searchParams.get('issueIndex'));
  const issueTotal = Number(searchParams.get('issueTotal'));
  if (
    !issueId ||
    !Number.isFinite(issueIndex) ||
    issueIndex < 1 ||
    !Number.isFinite(issueTotal) ||
    issueTotal < 1
  ) {
    return { isTriage: false, malformed: true };
  }
  return { isTriage: true, issueId, issueIndex, issueTotal };
}

export function stripTriageParams(href: string): string {
  const url = new URL(href, 'https://skeldir.local');
  url.searchParams.delete('source');
  url.searchParams.delete('issueId');
  url.searchParams.delete('issueIndex');
  url.searchParams.delete('issueTotal');
  const search = url.searchParams.toString();
  return `${url.pathname}${search ? `?${search}` : ''}${url.hash}`;
}
