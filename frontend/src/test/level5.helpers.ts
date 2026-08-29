import { MAX_DOM_TABLE_ROWS } from '../operationalAudit/pagination';

export function countTableBodyRows(container: HTMLElement): number {
  return container.querySelectorAll('tbody tr').length;
}

export function getTableDomRowCount(container: HTMLElement): number {
  const table = container.querySelector('[data-table-row-count]');
  if (!table) return countTableBodyRows(container);
  return Number.parseInt(table.getAttribute('data-table-row-count') ?? '0', 10);
}

export function assertDomRowCap(container: HTMLElement, totalPayload: number): void {
  const domRows = getTableDomRowCount(container);
  if (domRows > MAX_DOM_TABLE_ROWS) {
    throw new Error(`DOM row cap violated: ${domRows} rows rendered for ${totalPayload} payload`);
  }
  if (totalPayload > MAX_DOM_TABLE_ROWS && domRows > MAX_DOM_TABLE_ROWS) {
    throw new Error('High-cardinality payload rendered unbounded into DOM');
  }
}
