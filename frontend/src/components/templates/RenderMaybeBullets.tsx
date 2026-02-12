import React from 'react';

export function RenderMaybeBullets({
    text,
    className,
  forceBullets,
}: {
    text: any;
    className?: string;
  forceBullets?: boolean;
}) {
    const normalizedText =
        Array.isArray(text) ? text.join('\n') : (typeof text === 'string' ? text : String(text ?? ''));

    // Normalize a common inline format like: "- did X; - did Y; - did Z"
    // into separate lines so we can reliably render bullets.
    const normalizedForBullets = normalizedText
        .replaceAll('\r\n', '\n')
        .replace(/;\s*(?=(?:\u2022|•|[-–—*]|●|◦|▪|·)\s*)/g, '\n');

    const rawLines = normalizedForBullets.split('\n');

    // Recognize common bullet prefixes (dash, en/em dash, asterisk, and the usual bullet character).
    // Keep this conservative to avoid turning hyphenated sentences into bullets.
    // Includes a few additional common bullet glyphs users paste from Word/PDF.
    const bulletPrefixRe = /^(\u2022|[-–—*]|•|●|◦|▪|·)\s*/;

    const splitInlineBullets = (s: string): string[] => {
        const t = (s || '').trim();
        if (!t) return [];

        // If we see multiple bullet chars in a single line, split them.
        const bulletCharCount = (t.match(/[\u2022•]/g) || []).length;
        if (bulletCharCount >= 2) {
            return t
                .split(/[\u2022•]/g)
                .map(x => x.trim())
                .filter(Boolean);
        }

        // If we see multiple " - " separators, treat as inline dash bullets.
        // (Avoid splitting simple ranges like "2019 - 2021" which usually has only one separator.)
        const dashSepCount = (t.match(/\s-\s/g) || []).length;
        if (dashSepCount >= 2) {
            return t
                .split(/\s-\s/g)
                .map(x => x.trim())
                .filter(Boolean);
        }

        return [t];
    };

    const baseTextClass = (className || '').trim();

    const trimmedLines = rawLines.map(l => (l || '').trim()).filter(Boolean);
    if (trimmedLines.length === 0) return null;

    const hasInlineBulletDots = trimmedLines.some(l => (l.match(/\u2022|•/g) || []).length >= 2);
    const hasBulletPrefix = trimmedLines.some(l => bulletPrefixRe.test(l));
    const hasInlineDashBullets = trimmedLines.some(l => (l.match(/\s-\s/g) || []).length >= 2);
    // Important: if we detect bullet markers at all, render bullets even if there's only one item/line.
  const shouldRenderAsBullets = Boolean(forceBullets) || hasBulletPrefix || hasInlineBulletDots || hasInlineDashBullets;

    if (shouldRenderAsBullets) {
        const items: string[] = [];
        for (const line of trimmedLines) {
            // First, split inline bullets if present.
            const segments = splitInlineBullets(line);
            for (const seg of segments) {
                const cleaned = seg.replace(bulletPrefixRe, '').trim();
                if (cleaned) items.push(cleaned);
            }
        }
    // If forcing bullets and we still only got 1 item, try splitting into sentence-ish bullets.
    // Keep this conservative to avoid turning short phrases into multiple bullets.
    if (forceBullets && items.length === 1) {
      const one = items[0] || '';
      const sentenceParts = one
        .split(/(?<=[.!?])\s+/g)
        .map(s => s.trim())
        .filter(Boolean);
      if (sentenceParts.length >= 2) {
        items.length = 0;
        items.push(...sentenceParts);
            }
        }
        if (items.length === 0) return null;
        return (
            <ul className={`${baseTextClass} list-disc pl-5`.trim()}>
                {items.map((l, i) => (
                    <li key={i} className="marker:text-slate-400">
                        {l}
                    </li>
                ))}
            </ul>
        );
    }

    // No bullet markers detected: treat newlines as soft wraps so you don't get one-sentence-per-line.
    return <p className={`${baseTextClass} whitespace-pre-line`.trim()}>{trimmedLines.join(' ')}</p>;
}


