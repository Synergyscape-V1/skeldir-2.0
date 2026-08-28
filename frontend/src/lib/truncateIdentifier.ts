/** Truncate long identifiers for dense table cells while preserving head/tail recognition. */
export function truncateIdentifier(value: string, head = 7, tail = 5): string {
  if (value.length <= head + tail + 3) return value;
  return `${value.slice(0, head)}...${value.slice(-tail)}`;
}
