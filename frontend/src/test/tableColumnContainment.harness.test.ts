import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = process.cwd();

function read(rel: string): string {
  return readFileSync(join(ROOT, rel), 'utf8');
}

describe('Supervisory table column containment', () => {
  it('embedded Table cells clip overflow and constrain children', () => {
    const css = read('src/components/layout/Table/Table.module.css');
    expect(css).toMatch(/\.tableEmbedded :is\(th, td\) \{[\s\S]*?overflow:\s*hidden/);
    expect(css).toMatch(/\.tableEmbedded :is\(th, td\) > \* \{[\s\S]*?overflow:\s*hidden/);
    expect(css).toMatch(/\.tableEmbedded td\.expandedCell \{[\s\S]*?overflow:\s*visible/);
    expect(css).toMatch(
      /\[data-audit-open-affordance='navigate'\][\s\S]*?white-space:\s*nowrap/,
    );
  });

  it('dense and standard supervisory wraps share equal horizontal cell padding', () => {
    const css = read('src/styles/supervisoryTable.module.css');
    expect(css).toMatch(
      /\.tableWrapStandard :global\(table\[data-table-variant='embedded'\]\) :is\(th, td\) \{[\s\S]*?padding:\s*var\(--spacing-12\)\s+var\(--spacing-12\)/,
    );
    expect(css).toMatch(
      /\.tableWrapDense :global\(table\[data-table-variant='embedded'\]\) :is\(th, td\) \{[\s\S]*?padding:\s*var\(--spacing-12\)\s+var\(--spacing-12\)/,
    );
    expect(css).toMatch(
      /\.tableWrapDense :global\(table\[data-table-variant='embedded'\]\) :is\(th, td\) > \* \{[\s\S]*?overflow:\s*hidden/,
    );
  });

  it('ledger tables do not re-open overflow:visible on data cells', () => {
    const files = [
      'src/components/claims/ClaimsLedgerTable/ClaimsLedgerTable.module.css',
      'src/components/trustIndex/TrustEnvelopeIndexTable/TrustEnvelopeIndexTable.module.css',
      'src/components/channels/ChannelsOverviewTable/ChannelsOverviewTable.module.css',
      'src/components/benchmarks/BenchmarksTable/BenchmarksTable.module.css',
      'src/components/exceptions/ExceptionsTable/ExceptionsTable.module.css',
      'src/components/audit/AuditLedgerTable/AuditLedgerTable.module.css',
    ];
    for (const file of files) {
      const css = read(file);
      expect(css, file).not.toMatch(
        /table\[data-table-variant='embedded'\][\s\S]{0,120}overflow:\s*visible/,
      );
    }
  });

  it('command-center snapshot tables keep cell overflow clipped', () => {
    const css = read(
      'src/components/commandCenter/CommandCenterPage/CommandCenterSubcomponents.module.css',
    );
    expect(css).toMatch(/\.channelTable :is\(th, td\) \{[\s\S]*?overflow:\s*hidden/);
    expect(css).toMatch(/\.envelopeTable :is\(th, td\) \{[\s\S]*?overflow:\s*hidden/);
    expect(css).not.toMatch(
      /\.channelTable td:has\(\[data-trust-chip\]\)[\s\S]{0,80}overflow:\s*visible/,
    );
    expect(css).not.toMatch(
      /\[data-channel-trust-table\] td:has\(\.channelTrustWrapCell\) \{[\s\S]*?overflow:\s*visible/,
    );
  });
});
