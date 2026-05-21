type AiField =
  | 'summary'
  | 'experience_description'
  | 'project_description'
  | 'custom_section';

export async function rewriteWithAi(field: AiField, text: string, meta: Record<string, unknown> = {}) {
  const value = String(text || '').trim();
  if (!value) {
    throw new Error('Please add text first.');
  }

  const res = await fetch('/api/ai/resume-edit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ field, text: value, meta }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !(data as { success?: boolean }).success) {
    const message = String((data as { error?: string }).error || `AI request failed (HTTP ${res.status})`);
    throw new Error(message);
  }

  const output = String((data as { text?: string }).text || '').trim();
  if (!output) {
    throw new Error('AI returned an empty response.');
  }
  return output;
}
