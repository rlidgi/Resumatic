// Minimal GA4 loader + SPA pageview helper for the Vite/React app.

declare global {
    interface Window {
        dataLayer?: unknown[];
        gtag?: (...args: any[]) => void;
    }
}

export const GA4_MEASUREMENT_ID: string =
    (import.meta as any)?.env?.VITE_GA_MEASUREMENT_ID || 'G-KRPLMCR73G';

let ga4InitAttempted = false;

function injectScriptOnce(src: string): void {
    const scripts = Array.from(document.getElementsByTagName('script'));
    if (scripts.some((s) => s.src === src)) return;

    const script = document.createElement('script');
    script.async = true;
    script.src = src;
    document.head.appendChild(script);
}

export function ensureGa4Loaded(measurementId: string = GA4_MEASUREMENT_ID): void {
    if (!measurementId) return;
    if (typeof window === 'undefined' || typeof document === 'undefined') return;

    // If gtag exists, assume the host page (or earlier init) already configured it.
    if (typeof window.gtag === 'function') return;
    if (ga4InitAttempted) return;
    ga4InitAttempted = true;

    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag() {
        // eslint-disable-next-line prefer-rest-params
        window.dataLayer!.push(arguments);
    };

    injectScriptOnce(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`);

    // Initialize without an automatic page_view; we send SPA page views manually.
    window.gtag('js', new Date());
    window.gtag('config', measurementId, { send_page_view: false });
}

export function trackGa4PageView(pagePath: string, measurementId: string = GA4_MEASUREMENT_ID): void {
    if (!measurementId) return;
    if (typeof window === 'undefined') return;
    if (typeof window.gtag !== 'function') return;

    window.gtag('event', 'page_view', {
        page_path: pagePath,
        page_location: window.location.href,
        page_title: document.title,
        send_to: measurementId,
    });
}
