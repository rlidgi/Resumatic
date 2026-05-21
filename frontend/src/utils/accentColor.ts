function clamp01(n: number): number {
    if (Number.isNaN(n)) return 0;
    if (n < 0) return 0;
    if (n > 1) return 1;
    return n;
}

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
    const normalized = normalizeHexColor(hex);
    if (!normalized) return null;
    const raw = normalized.slice(1);
    const r = parseInt(raw.slice(0, 2), 16);
    const g = parseInt(raw.slice(2, 4), 16);
    const b = parseInt(raw.slice(4, 6), 16);
    if ([r, g, b].some((v) => Number.isNaN(v))) return null;
    return { r, g, b };
}

function rgbToHex(rgb: { r: number; g: number; b: number }): string {
    const toHex = (n: number) => {
        const v = Math.max(0, Math.min(255, Math.round(n)));
        return v.toString(16).padStart(2, '0');
    };
    return `#${toHex(rgb.r)}${toHex(rgb.g)}${toHex(rgb.b)}`.toUpperCase();
}

function mix(a: { r: number; g: number; b: number }, b: { r: number; g: number; b: number }, t: number) {
    const tt = clamp01(t);
    return {
        r: a.r + (b.r - a.r) * tt,
        g: a.g + (b.g - a.g) * tt,
        b: a.b + (b.b - a.b) * tt,
    };
}

export function normalizeHexColor(input: string): string {
    const raw = String(input || '').trim();
    if (!raw) return '';

    const withHash = raw.startsWith('#') ? raw : `#${raw}`;
    const hex = withHash.toUpperCase();

    // #RGB
    const short = /^#([0-9A-F]{3})$/;
    const long = /^#([0-9A-F]{6})$/;

    const mShort = hex.match(short);
    if (mShort) {
        const s = mShort[1];
        return `#${s[0]}${s[0]}${s[1]}${s[1]}${s[2]}${s[2]}`;
    }

    const mLong = hex.match(long);
    if (mLong) return `#${mLong[1]}`;

    return '';
}

export function mixWithWhite(hex: string, amount: number): string {
    const rgb = hexToRgb(hex);
    if (!rgb) return normalizeHexColor(hex) || '';
    return rgbToHex(mix(rgb, { r: 255, g: 255, b: 255 }, amount));
}

export function mixWithBlack(hex: string, amount: number): string {
    const rgb = hexToRgb(hex);
    if (!rgb) return normalizeHexColor(hex) || '';
    return rgbToHex(mix(rgb, { r: 0, g: 0, b: 0 }, amount));
}
