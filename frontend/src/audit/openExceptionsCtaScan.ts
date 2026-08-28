import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..', '..');

function read(rel: string): string {
  return readFileSync(join(ROOT, rel), 'utf8');
}

export interface OpenExceptionsCtaViolation {
  file: string;
  rule: string;
  detail: string;
}

/**
 * Static integrity scan: Open exceptions CTA must target Exceptions queue, never Overview self.
 */
export function scanOpenExceptionsCta(sourceOverride?: {
  copyTs?: string;
  summaryMetricsTs?: string;
}): OpenExceptionsCtaViolation[] {
  const violations: OpenExceptionsCtaViolation[] = [];
  const copyTs = sourceOverride?.copyTs ?? read('src/commandCenter/copy.ts');
  const summaryMetricsTs =
    sourceOverride?.summaryMetricsTs ?? read('src/commandCenter/summaryMetrics.ts');

  const openExceptionsHrefMatch = copyTs.match(
    /open_exceptions:\s*\{\s*label:\s*'[^']*',\s*href:\s*'([^']*)'/,
  );
  const href = openExceptionsHrefMatch?.[1];

  if (!href) {
    violations.push({
      file: 'src/commandCenter/copy.ts',
      rule: 'missing-open-exceptions-href',
      detail: 'summaryDrilldown.open_exceptions.href not found',
    });
  } else if (href === '/app' || href === '/app/') {
    violations.push({
      file: 'src/commandCenter/copy.ts',
      rule: 'overview-self-loop',
      detail: `open_exceptions.href is Overview self (${href}); must be Exceptions queue`,
    });
  } else if (href !== '/app/exceptions') {
    violations.push({
      file: 'src/commandCenter/copy.ts',
      rule: 'unexpected-exceptions-href',
      detail: `open_exceptions.href is "${href}"; expected "/app/exceptions"`,
    });
  }

  if (!summaryMetricsTs.includes('COMMAND_CENTER_COPY.summaryDrilldown.open_exceptions.href')) {
    violations.push({
      file: 'src/commandCenter/summaryMetrics.ts',
      rule: 'drilldown-not-sourced-from-copy',
      detail: 'buildOpenExceptionsMetric must consume summaryDrilldown.open_exceptions.href',
    });
  }

  if (
    /PRIORITY_QUEUE_ANCHOR\s*=\s*['"]\/app['"]/.test(summaryMetricsTs) &&
    summaryMetricsTs.includes('drillDownHref: PRIORITY_QUEUE_ANCHOR')
  ) {
    violations.push({
      file: 'src/commandCenter/summaryMetrics.ts',
      rule: 'legacy-priority-queue-anchor',
      detail: 'open_exceptions still anchored to PRIORITY_QUEUE_ANCHOR=/app',
    });
  }

  return violations;
}

/** Meta-negative: deliberately sabotaged sources must produce scan failures. */
export function openExceptionsCtaSabotageFixture(): {
  copyTs: string;
  summaryMetricsTs: string;
} {
  return {
    copyTs: `summaryDrilldown: {
    open_exceptions: { label: 'Review blocking issues', href: '/app' },
  },`,
    summaryMetricsTs: `const PRIORITY_QUEUE_ANCHOR = '/app';
    drillDownHref: PRIORITY_QUEUE_ANCHOR,`,
  };
}
