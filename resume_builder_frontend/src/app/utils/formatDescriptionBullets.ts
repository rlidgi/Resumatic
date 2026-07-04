/**
 * Convert freeform description text into one bullet per statement.
 * Existing bullets are normalized to "- " for consistency.
 */
export function formatDescriptionBullets(raw: string): string {
  const text = String(raw || '').replace(/\r\n/g, '\n').trim();
  if (!text) return '';

  const statementChunks = text
    .split('\n')
    .flatMap((line) => line.split(/(?<=[.!?])\s+/))
    .map((part) => part.replace(/^[-*•]\s+/, '').trim())
    .filter(Boolean);

  return statementChunks.map((statement) => `- ${statement}`).join('\n');
}
