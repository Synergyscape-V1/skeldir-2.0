/**
 * JSON-LD serialization for `<script type="application/ld+json">`.
 * Per Next.js guidance, escape `<` (and script-breaking sequences) in serialized output.
 */
export function jsonLdScriptPayload(data: unknown): string {
  const raw = JSON.stringify(data);
  return raw.replace(/</g, "\\u003c").replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
}
