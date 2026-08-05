/**
 * Normalize a user-entered external URL for use in an <a href>.
 * A scheme-less value like "github.com/mj665" is treated by the browser as a
 * RELATIVE path (→ studybuddy.mj665.in/github.com/mj665), so prepend https://
 * when no http(s) scheme is present. Returns undefined for empty input.
 */
export function normalizeExternalUrl(raw?: string | null): string | undefined {
  const v = (raw || '').trim();
  if (!v) return undefined;
  if (/^https?:\/\//i.test(v)) return v;
  // Leave mailto:/tel: and protocol-relative //host as-is.
  if (/^(mailto:|tel:|\/\/)/i.test(v)) return v;
  return `https://${v.replace(/^\/+/, '')}`;
}
