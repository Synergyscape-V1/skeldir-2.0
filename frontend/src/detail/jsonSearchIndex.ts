export interface JsonLineMatch {
  lineIndex: number;
  lineText: string;
}

export function indexJsonLines(lines: string[]): JsonLineMatch[] {
  return lines.map((lineText, lineIndex) => ({ lineIndex, lineText }));
}

export function findJsonLineMatches(lines: string[], query: string): number[] {
  if (!query.trim()) return [];
  const normalized = query.toLowerCase();
  const matches: number[] = [];
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].toLowerCase().includes(normalized)) matches.push(i);
  }
  return matches;
}

export function computeVirtualWindowStart(
  targetLine: number,
  totalLines: number,
  windowSize: number,
): number {
  if (totalLines <= windowSize) return 0;
  const half = Math.floor(windowSize / 2);
  return Math.max(0, Math.min(targetLine - half, totalLines - windowSize));
}
