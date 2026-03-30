import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import ProfessionalTemplate from '../components/templates/ProfessionalTemplate';
import ExecutiveTemplate from '../components/templates/ExecutiveTemplate';
import Creative2Template from '../components/templates/Creative2Template';
import ClassicRoseTemplate from '../components/templates/ClassicRoseTemplate';
import BoldProfessionalTemplate from '../components/templates/BoldProfessionalTemplate';
import TraditionalTemplate from '../components/templates/TraditionalTemplate';
import ModernTemplate from '../components/templates/ModernTemplate';
import CleanTemplate from '../components/templates/CleanTemplate';
import { Type, AlignLeft, Rows, RotateCcw, Lightbulb, Edit3, Grip, Wand2, AlertTriangle } from 'lucide-react';

const TEMPLATE_DISPLAY_NAMES: Record<string, string> = {
    classicrose: 'Classic',
    classic_rose: 'Classic',
    minimalsidebar: 'Clean',
    minimal_sidebar: 'Clean',
    creative2: 'Creative',
    creative_2: 'Creative',
};

function formatTemplateDisplayName(raw?: string): string {
    const key = String(raw || '').toLowerCase().replace(/[-_]/g, '');
    if (TEMPLATE_DISPLAY_NAMES[key]) return TEMPLATE_DISPLAY_NAMES[key];

    const normalized = String(raw || '')
        .replace(/[_-]+/g, ' ')
        .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
        .trim();

    if (!normalized) return '';

    return normalized
        .split(/\s+/g)
        .filter(Boolean)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

function getTemplateSkillsLimit(rawTemplateName?: string): number | null {
    const key = String(rawTemplateName || '')
        .trim()
        .toLowerCase()
        .replace(/[_-]/g, '');
    if (!key) return null;

    // Match the same aliases used by the template switch() below.
    switch (key) {
        case 'executive':
        case 'timelineblue':
            return 12;

        case 'elegant':
        case 'lavenderclassic':
        case 'classicrose':
            return 12;

        case 'creative':
        case 'creative2':
        case 'popart':
            return 8;

        case 'boldprofessional':
        case 'orangeheader':
            return 10;

        case 'traditional':
        case 'bluelineclassic':
            return 12;

        case 'modern':
        case 'cleansidebar':
            return 18;

        case 'minimalsidebar':
            return 10;

        default:
            return null;
    }
}

export default function TemplateViewer() {
    const { templateName } = useParams<{ templateName: string }>();
    const location = useLocation();
    const isDownloadOnly = location.pathname.includes('/template-download/');

    const templateDisplayName = formatTemplateDisplayName(templateName);

    const qs = new URLSearchParams(location.search || '');
    const returnTo = String(qs.get('return') || '').trim();
    const editParam = String(qs.get('edit') || '').trim().toLowerCase();
    const ridParam = String(qs.get('rid') || '').trim();
    const embedParam = String(qs.get('embed') || '').trim().toLowerCase();
    const isEmbed = embedParam === '1' || embedParam === 'true';

    // Embed mode is rendered inside an iframe (create-resume wizard preview).
    // Avoid "phantom" root scrollbars by disabling html/body scrolling and using
    // the root container as the only scroll surface.
    useEffect(() => {
        if (!isEmbed) return;

        const html = document.documentElement;
        const body = document.body;

        const prev = {
            htmlOverflow: html.style.overflow,
            htmlOverflowX: html.style.overflowX,
            htmlOverflowY: html.style.overflowY,
            bodyOverflow: body.style.overflow,
            bodyOverflowX: body.style.overflowX,
            bodyOverflowY: body.style.overflowY,
            bodyMargin: body.style.margin,
            rootOverflowY: embedRootRef.current?.style.overflowY || '',
            rootOverscroll: embedRootRef.current?.style.overscrollBehaviorY || '',
        };

        // Never allow the document root to scroll in embed mode.
        // The `.tv-embed` container will handle scrolling.
        html.style.overflow = 'hidden';
        html.style.overflowX = 'hidden';
        html.style.overflowY = 'hidden';
        body.style.overflow = 'hidden';
        body.style.overflowX = 'hidden';
        body.style.overflowY = 'hidden';
        body.style.margin = '0';

        const HIDE_CLASS = 'tv-embed-no-scrollbar';
        const updateScrollbarVisibility = () => {
            const root = embedRootRef.current;
            if (!root) return;

            const delta = root.scrollHeight - root.clientHeight;
            // Ignore tiny overflows caused by subpixel rounding / transforms.
            const scrollable = delta > 8;

            // Only allow vertical scrolling when needed.
            // This prevents "always-on" scrollbars for short content.
            root.style.overflowY = scrollable ? 'auto' : 'hidden';
            root.style.overscrollBehaviorY = 'contain';

            root.classList.toggle(HIDE_CLASS, !scrollable);

            if (!scrollable) root.scrollTop = 0;
        };

        const styleEl = document.createElement('style');
        styleEl.setAttribute('data-tv-embed-scrollbar-fix', '1');
        styleEl.textContent = `
            .tv-embed.${HIDE_CLASS},
            .tv-embed.${HIDE_CLASS} * {
                scrollbar-width: none;
                -ms-overflow-style: none;
            }
            .tv-embed.${HIDE_CLASS}::-webkit-scrollbar,
            .tv-embed.${HIDE_CLASS} *::-webkit-scrollbar {
                width: 0;
                height: 0;
            }
        `;
        document.head.appendChild(styleEl);

        // Recompute on layout changes so the scrollbar is only hidden when content fits.
        const rafUpdate = () => window.requestAnimationFrame(updateScrollbarVisibility);
        const onResize = () => rafUpdate();
        window.addEventListener('resize', onResize);

        let ro: ResizeObserver | null = null;
        if (typeof ResizeObserver !== 'undefined') {
            ro = new ResizeObserver(() => rafUpdate());
            ro.observe(embedRootRef.current || body);
        }

        rafUpdate();
        const intervalId = window.setInterval(updateScrollbarVisibility, 750);

        return () => {
            window.clearInterval(intervalId);
            window.removeEventListener('resize', onResize);
            ro?.disconnect();
            embedRootRef.current?.classList.remove(HIDE_CLASS);
            if (embedRootRef.current) {
                embedRootRef.current.style.overflowY = prev.rootOverflowY;
                embedRootRef.current.style.overscrollBehaviorY = prev.rootOverscroll;
            }
            styleEl.remove();
            html.style.overflow = prev.htmlOverflow;
            html.style.overflowX = prev.htmlOverflowX;
            html.style.overflowY = prev.htmlOverflowY;
            body.style.overflow = prev.bodyOverflow;
            body.style.overflowX = prev.bodyOverflowX;
            body.style.overflowY = prev.bodyOverflowY;
            body.style.margin = prev.bodyMargin;
        };
    }, [isEmbed]);
    // When users come from the "Create new resume" flow, they land here with ?edit=1
    // and no analysis/results context. In that case, "Back to Results" is misleading.
    const isCreateNewResumeFlow = !isEmbed && !isDownloadOnly && !returnTo && (editParam === '1' || editParam === 'true') && !ridParam;
    const backHref = returnTo || (isCreateNewResumeFlow ? '/' : '/results');
    const [resumeData, setResumeData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [downloadingPdf, setDownloadingPdf] = useState(false);
    const [sourceRevisionId, setSourceRevisionId] = useState<string>('');
    const [downloadOnlyStatus, setDownloadOnlyStatus] = useState<'idle' | 'starting' | 'done' | 'failed'>('idle');
    const [downloadOnlyError, setDownloadOnlyError] = useState<string>('');
    const [me, setMe] = useState<{
        is_authenticated: boolean;
        is_paid: boolean;
        free_revision_limit: number;
        revisions_used: number;
    } | null>(null);
    const [styleSettings, setStyleSettings] = useState({
        fontScale: 1,
        paragraphGapPx: 0,
        spacingScale: 1,
    });
    const [pdfPreviewPageScale, setPdfPreviewPageScale] = useState(1);
    const [pdfPreviewContentScale, setPdfPreviewContentScale] = useState(1);
    const [pdfPreviewPages, setPdfPreviewPages] = useState(1);
    const [pdfPreviewLastPageHeightPx, setPdfPreviewLastPageHeightPx] = useState(1056);
    const [pdfPreviewSnapshotHtml, setPdfPreviewSnapshotHtml] = useState<string>('');
    const embedRootRef = useRef<HTMLDivElement | null>(null);
    const pdfPreviewContainerRef = useRef<HTMLDivElement | null>(null);
    const pdfPreviewMeasureInnerRef = useRef<HTMLDivElement | null>(null);
    const autoDownloadTriggeredRef = useRef(false);
    const editAutoAppliedRef = useRef(false);

    const [editSaving, setEditSaving] = useState(false);
    const [editSaveError, setEditSaveError] = useState<string | null>(null);
    const [editSaveSuccess, setEditSaveSuccess] = useState(false);
    const [editSaveHubMessage, setEditSaveHubMessage] = useState<string | null>(null);
    const [editingExperienceIndex, setEditingExperienceIndex] = useState<number | null>(null);
    const [showAllWorkHistoryDescriptions, setShowAllWorkHistoryDescriptions] = useState(false);
    const [editingProjectIndex, setEditingProjectIndex] = useState<number | null>(null);
    const [showAllProjectDescriptions, setShowAllProjectDescriptions] = useState(false);

    // AI edit assistance (summary + experience + projects + custom sections)
    const [aiEditError, setAiEditError] = useState<string | null>(null);
    const [aiBusySummary, setAiBusySummary] = useState(false);
    const [aiBusyExperience, setAiBusyExperience] = useState<Record<number, boolean>>({});
    const [aiBusyProjects, setAiBusyProjects] = useState<Record<number, boolean>>({});
    const [aiBusyCustom, setAiBusyCustom] = useState<Record<string, boolean>>({});

    // Download feedback modal (shown after printing/export)
    const [downloadFeedbackOpen, setDownloadFeedbackOpen] = useState(false);
    const [downloadFeedbackRating, setDownloadFeedbackRating] = useState<number>(0);
    const [downloadFeedbackHoverRating, setDownloadFeedbackHoverRating] = useState<number>(0);
    const [downloadFeedbackComparison, setDownloadFeedbackComparison] = useState<'improved' | 'same' | 'worse' | ''>('');
    const [downloadFeedbackComment, setDownloadFeedbackComment] = useState('');
    const [downloadFeedbackSubmitting, setDownloadFeedbackSubmitting] = useState(false);

    const DOWNLOAD_FEEDBACK_DELAY_MS = 60_000;
    const downloadFeedbackTimeoutRef = useRef<number | null>(null);
    const meRef = useRef<typeof me>(null);
    const downloadFeedbackOpenRef = useRef(false);

    // Inline editing mode
    const [inlineEditMode, setInlineEditMode] = useState(false);
    const [sectionOrderByTemplate, setSectionOrderByTemplate] = useState<Record<string, string[]>>({});
    const sectionOrder = sectionOrderByTemplate[String(templateName || '')] || [];
    const setSectionOrder = React.useCallback((order: string[]) => {
        setSectionOrderByTemplate((prev) => ({
            ...(prev || {}),
            [String(templateName || '')]: Array.isArray(order) ? order : [],
        }));
    }, [templateName]);

    const [hiddenSectionKeysByTemplate, setHiddenSectionKeysByTemplate] = useState<Record<string, string[]>>({});
    const hiddenSectionKeys = hiddenSectionKeysByTemplate[String(templateName || '')] || [];
    const setHiddenSectionKeys = React.useCallback((keys: string[]) => {
        setHiddenSectionKeysByTemplate((prev) => ({
            ...(prev || {}),
            [String(templateName || '')]: Array.isArray(keys) ? keys : [],
        }));
    }, [templateName]);
    const [inlineEditChanges, setInlineEditChanges] = useState<any>({});

    // Top navigation (hamburger on mobile)
    const [mobileNavOpen, setMobileNavOpen] = useState(false);

    // Mobile-only fullscreen preview
    const [mobilePreviewOpen, setMobilePreviewOpen] = useState(false);

    useEffect(() => {
        if (!mobileNavOpen) return;
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') setMobileNavOpen(false);
        };
        document.addEventListener('keydown', onKeyDown);
        return () => document.removeEventListener('keydown', onKeyDown);
    }, [mobileNavOpen]);

    useEffect(() => {
        if (!mobilePreviewOpen) return;

        const prevOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';

        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') setMobilePreviewOpen(false);
        };
        document.addEventListener('keydown', onKeyDown);

        return () => {
            document.body.style.overflow = prevOverflow;
            document.removeEventListener('keydown', onKeyDown);
        };
    }, [mobilePreviewOpen]);

    useEffect(() => {
        meRef.current = me;
    }, [me]);

    useEffect(() => {
        downloadFeedbackOpenRef.current = downloadFeedbackOpen;
    }, [downloadFeedbackOpen]);

    useEffect(() => {
        return () => {
            if (downloadFeedbackTimeoutRef.current != null) {
                window.clearTimeout(downloadFeedbackTimeoutRef.current);
                downloadFeedbackTimeoutRef.current = null;
            }
        };
    }, []);

    // Debug logging
    useEffect(() => {
        console.log('TemplateViewer: inlineEditMode changed to:', inlineEditMode);
        console.log('TemplateViewer: sectionOrder:', sectionOrder);
    }, [inlineEditMode, sectionOrder]);

    console.log('TemplateViewer: Template name:', templateName);

    const downloadOnlyReturnToHub = React.useCallback(() => {
        const ret = new URLSearchParams(window.location.search || '').get('return') || '';
        window.location.href = ret || '/my_revisions';
    }, []);

    useEffect(() => {
        if (inlineEditMode) {
            setShowAllWorkHistoryDescriptions(false);
            setEditingExperienceIndex(null);
            setShowAllProjectDescriptions(false);
            setEditingProjectIndex(null);
        }
    }, [inlineEditMode]);

    useEffect(() => {
        let cancelled = false;
        const loadMe = () => {
            fetch('/api/me', { credentials: 'same-origin' })
                .then(r => r.json())
                .then(data => { if (!cancelled) setMe(data); })
                .catch(() => { if (!cancelled) setMe({ is_authenticated: false, is_paid: false, free_revision_limit: 2, revisions_used: 0 }); });
        };
        loadMe();

        // If the user purchases in another tab (or returns from Stripe), refresh plan gating on focus.
        const onFocus = () => loadMe();
        const onVis = () => { if (document.visibilityState === 'visible') loadMe(); };
        window.addEventListener('focus', onFocus);
        document.addEventListener('visibilitychange', onVis);
        return () => {
            cancelled = true;
            window.removeEventListener('focus', onFocus);
            document.removeEventListener('visibilitychange', onVis);
        };
    }, []);

    function openDownloadFeedbackModal() {
        if (!meRef.current?.is_authenticated) return;
        setDownloadFeedbackRating(0);
        setDownloadFeedbackComparison('');
        setDownloadFeedbackComment('');
        setDownloadFeedbackSubmitting(false);
        setDownloadFeedbackOpen(true);
    }

    function scheduleDownloadFeedbackModal() {
        if (!meRef.current?.is_authenticated) return;
        if (downloadFeedbackTimeoutRef.current != null) {
            window.clearTimeout(downloadFeedbackTimeoutRef.current);
            downloadFeedbackTimeoutRef.current = null;
        }
        downloadFeedbackTimeoutRef.current = window.setTimeout(() => {
            downloadFeedbackTimeoutRef.current = null;
            if (!meRef.current?.is_authenticated) return;
            if (downloadFeedbackOpenRef.current) return;
            openDownloadFeedbackModal();
        }, DOWNLOAD_FEEDBACK_DELAY_MS);
    }

    function closeDownloadFeedbackModal() {
        setDownloadFeedbackOpen(false);
    }

    async function submitDownloadFeedback() {
        if (!me?.is_authenticated) {
            closeDownloadFeedbackModal();
            return;
        }
        try {
            setDownloadFeedbackSubmitting(true);
            await fetch('/api/feedback/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    rating: String(downloadFeedbackRating || ''),
                    comment: String(downloadFeedbackComment || '').slice(0, 500),
                    comparison: String(downloadFeedbackComparison || ''),
                }),
            });
        } catch {
            // Ignore feedback submission errors; do not block UX
        } finally {
            setDownloadFeedbackSubmitting(false);
            closeDownloadFeedbackModal();
        }
    }

    function printElementViaHiddenIframe(el: HTMLElement, settings: { fontScale: number; paragraphGapPx: number; spacingScale: number }): Promise<void> {
        // Popup-free export: print dialog using an isolated iframe (no popup), prints only the resume DOM.
        // We render into a fixed Letter canvas with @page margin 0, but add a controlled "print padding"
        // so the PDF matches the on-page HTML spacing.
        return new Promise((resolve, reject) => {
            const stylesheetLinks = Array.from(document.querySelectorAll('link[rel="stylesheet"]'))
                .map(l => (l as HTMLLinkElement).href)
                .filter(Boolean);
            const inlineStyles = Array.from(document.querySelectorAll('style')).map(s => s.innerHTML || '');

            const clone = el.cloneNode(true) as HTMLElement;

            // CSS px are 96 per inch. Letter = 8.5in x 11in.
            const pageWidthPx = 816;
            const pageHeightPx = 1056;
            // True edge-to-edge PDF: do not add additional "page padding" in the print iframe.
            // (Templates can still have their own internal padding like p-8, which we preserve.)
            const printPadPx = 0;
            const availW = pageWidthPx - (printPadPx * 2);
            const availH = pageHeightPx - (printPadPx * 2);

            const isOnePage = false;

            // Explicitly inject style settings into print context so PDF matches on-screen adjustments
            const fs = String(settings.fontScale);
            const pg = `${settings.paragraphGapPx}px`;
            const ss = String(settings.spacingScale);

            const printCss = `
          #printTarget, #printTarget .tv-style-root {
            --tv-font-scale: ${fs};
            --tv-paragraph-gap: ${pg};
            --tv-space-scale: ${ss};
          }
                    @page { size: letter; margin: 8mm 0mm !important; }
          html, body {
            width: ${pageWidthPx}px;
            margin: 0 !important;
            padding: 0 !important;
            ${isOnePage ? `height: ${pageHeightPx}px; overflow: hidden !important;` : `height: auto; overflow: visible !important;`}
            background: #fff !important;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }
          #printPage {
            position: relative;
            width: ${pageWidthPx}px;
            ${isOnePage ? `height: ${pageHeightPx}px; overflow: hidden;` : `height: auto; overflow: visible;`}
          }
          #printTarget {
            position: ${isOnePage ? 'absolute' : 'relative'};
            top: 0; left: 0;
            width: ${pageWidthPx}px;
            ${isOnePage ? `height: ${pageHeightPx}px; overflow: hidden;` : `height: auto; overflow: visible;`}
            box-sizing: border-box !important;
            padding: ${printPadPx}px !important;
          }
                    /* Many templates have an outer wrapper with top padding/margin (e.g., Tailwind p-8 or pt-9).
                         That spacing only applies at the start of the document, making page 1 look like it
                         has a larger top margin than page 2+. Strip only the TOP spacing from the first wrapper
                         and rely on @page margin for consistent per-page top whitespace. */
                    #printTarget > *:first-child {
                        margin-top: 0 !important;
                        padding-top: 0 !important;
                    }
                    #printTarget > *:first-child > :first-of-type {
                        margin-top: 0 !important;
                        padding-top: 0 !important;
                    }
                    #printTarget > *:first-child > :first-of-type > :first-of-type {
                        margin-top: 0 !important;
                        padding-top: 0 !important;
                    }
                    #printTarget > *:first-child > :first-of-type > :first-of-type > :first-of-type {
                        margin-top: 0 !important;
                        padding-top: 0 !important;
                    }
          /* Fill the printable canvas edge-to-edge (strip outer "card" gutters like mx-auto/max-w-*) */
          #printTarget > * {
            width: ${availW}px !important;
            max-width: none !important;
            margin: 0 !important;
          }
          #printTarget .mx-auto { margin-left: 0 !important; margin-right: 0 !important; }
          #printTarget .max-w-3xl,
          #printTarget .max-w-4xl,
          #printTarget .max-w-5xl,
          #printTarget .max-w-6xl,
          #printTarget .max-w-7xl {
            max-width: none !important;
            width: 100% !important;
          }
          /* Remove template "card" shadows in the PDF output (they can appear as a gray line at the bottom) */
          #printTarget .shadow,
          #printTarget .shadow-sm,
          #printTarget .shadow-md,
          #printTarget .shadow-lg,
          #printTarget .shadow-xl,
          #printTarget .shadow-2xl {
            box-shadow: none !important;
          }
                    /*
                        Some templates rely on Tailwind's responsive md:* utilities to switch to a two-column layout.
                        If the user prints with Chrome "Margins: Default", the effective print width can drop below the md breakpoint,
                        causing the sidebar to stack above the main content in the PDF.
                        Force the md layout unconditionally in the print iframe so the PDF matches the on-screen (desktop) layout.
                    */
          #printTarget .md\\:flex-row { flex-direction: row !important; }
          #printTarget .md\\:flex-row > * { min-width: 0 !important; }
          #printTarget .md\\:w-\\[300px\\] { width: 300px !important; }
          #printTarget .md\\:flex-shrink-0 { flex-shrink: 0 !important; }

          /* Ensure TemplateViewer "Customize" styles apply inside the print iframe too */
          /* Paragraph gap: apply even when a template only renders single <p> blocks */
          #printTarget .tv-style-root p { margin: 0 0 var(--tv-paragraph-gap, 0px) 0 !important; }

          #printTarget .tv-style-root { font-size: calc(1rem * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-xs { font-size: calc(0.75rem * var(--tv-font-scale, 1)) !important; line-height: calc(1rem * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-sm { font-size: calc(0.875rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.25rem * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-base { font-size: calc(1rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.5rem * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-lg { font-size: calc(1.125rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.75rem * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-xl { font-size: calc(1.25rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.75rem * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-2xl { font-size: calc(1.5rem * var(--tv-font-scale, 1)) !important; line-height: calc(2rem * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-3xl { font-size: calc(1.875rem * var(--tv-font-scale, 1)) !important; line-height: calc(2.25rem * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-4xl { font-size: calc(2.25rem * var(--tv-font-scale, 1)) !important; line-height: calc(2.5rem * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-5xl { font-size: calc(3rem * var(--tv-font-scale, 1)) !important; line-height: 1 !important; }

          /* Also scale Tailwind "arbitrary" font sizes used by some templates (e.g. text-[11px]) */
          #printTarget .tv-style-root .text-\\[10px\\] { font-size: calc(10px * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-\\[11px\\] { font-size: calc(11px * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-\\[12px\\] { font-size: calc(12px * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-\\[13px\\] { font-size: calc(13px * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-\\[34px\\] { font-size: calc(34px * var(--tv-font-scale, 1)) !important; }
          #printTarget .tv-style-root .text-\\[38px\\] { font-size: calc(38px * var(--tv-font-scale, 1)) !important; }

          #printTarget .tv-style-root .space-y-10 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .space-y-8  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(2rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .space-y-6  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .space-y-5  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .space-y-4  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .space-y-3  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .space-y-2  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(0.5rem * var(--tv-space-scale, 1)) !important; }

          #printTarget .tv-style-root .mb-12 { margin-bottom: calc(3rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mb-10 { margin-bottom: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mb-8  { margin-bottom: calc(2rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mb-6  { margin-bottom: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mb-5  { margin-bottom: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mb-4  { margin-bottom: calc(1rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mb-3  { margin-bottom: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mb-2  { margin-bottom: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mb-1  { margin-bottom: calc(0.25rem * var(--tv-space-scale, 1)) !important; }

          #printTarget .tv-style-root .mt-12 { margin-top: calc(3rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mt-10 { margin-top: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mt-8  { margin-top: calc(2rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mt-6  { margin-top: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mt-5  { margin-top: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mt-4  { margin-top: calc(1rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mt-3  { margin-top: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mt-2  { margin-top: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .mt-1  { margin-top: calc(0.25rem * var(--tv-space-scale, 1)) !important; }

          #printTarget .tv-style-root .gap-8 { gap: calc(2rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .gap-6 { gap: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .gap-5 { gap: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .gap-4 { gap: calc(1rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .gap-3 { gap: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .gap-2 { gap: calc(0.5rem * var(--tv-space-scale, 1)) !important; }

          /* Scale common padding-bottom utilities used by templates for section/item spacing */
          #printTarget .tv-style-root .pb-4 { padding-bottom: calc(1rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .pb-3 { padding-bottom: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .pb-2 { padding-bottom: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
          #printTarget .tv-style-root .pb-0 { padding-bottom: 0 !important; }
          /* Scaling (set by JS) */
          #printTarget[data-scale] > * { transform-origin: top left !important; }

             /* Creative2 template: preserve its left accent gutter (pl-12) and right padding (pr-8)
                 while slightly compacting vertical padding for multi-page print/PDF. */
             #printTarget [data-template="creative2"] .creative2-body { padding-left: 3rem !important; padding-right: 2rem !important; padding-top: 0.4rem !important; padding-bottom: 0.4rem !important; }
          #printTarget [data-template="creative2"] .creative2-body > div:first-child { margin-bottom: 0.5rem !important; }
          #printTarget [data-template="creative2"] .creative2-summary { margin-top: 0.25rem !important; line-height: 1.35 !important; max-width: none !important; }
                    /* Printing fragmentation: keep normal flow, but render a two-column layout via floats (more paginatable than CSS grid). */
                    #printTarget [data-template="creative2"] .creative2-grid { display: block !important; }
                    #printTarget [data-template="creative2"] .creative2-grid::after { content: "" !important; display: block !important; clear: both !important; }
                    #printTarget [data-template="creative2"] .creative2-grid > aside { float: left !important; width: 32% !important; }
                    #printTarget [data-template="creative2"] .creative2-grid > main { display: block !important; margin-left: 36% !important; }
                    #printTarget [data-template="creative2"] .creative2-grid > * + * { margin-top: 0 !important; }
          #printTarget [data-template="creative2"] .creative2-template section { margin-bottom: 0.5rem !important; }
          #printTarget [data-template="creative2"] .creative2-template section h3 { margin-bottom: 0.25rem !important; }
          #printTarget [data-template="creative2"] .creative2-template .space-y-4 > * + * { margin-top: 0.5rem !important; }
          #printTarget [data-template="creative2"] .creative2-template .space-y-5 > * + * { margin-top: 0.5rem !important; }
          #printTarget [data-template="creative2"] .creative2-template .space-y-2 > * + * { margin-top: 0.25rem !important; }
          /* Allow header/summary to break normally so body can start on page 1 when space is tight */
          #printTarget [data-template="creative2"] .creative2-body > div:first-child { page-break-after: auto !important; break-after: auto !important; }
                    /* IMPORTANT: allow the main body to paginate (grid is forced to block above) */
                    #printTarget [data-template="creative2"] .creative2-grid { page-break-before: auto !important; page-break-inside: auto !important; break-inside: auto !important; }
                    /* Keep individual items together where possible (but still allow the section as a whole to span pages) */
                    /* Allow long items to split across pages; avoid flex in print which often prevents fragmentation */
                    #printTarget [data-template="creative2"] .creative2-item { display: flow-root !important; page-break-inside: auto !important; break-inside: auto !important; }
                    #printTarget [data-template="creative2"] .creative2-item > span { float: left !important; margin-right: 0.75rem !important; }
        `;

            const iframe = document.createElement('iframe');
            iframe.setAttribute('title', 'print-frame');
            iframe.style.position = 'fixed';
            iframe.style.left = '-10000px';
            iframe.style.top = '0';
            // IMPORTANT: give the iframe a real viewport so Tailwind responsive breakpoints (md:*) apply.
            iframe.style.width = `${pageWidthPx}px`;
            iframe.style.height = `${pageHeightPx}px`;
            iframe.style.border = '0';
            iframe.style.opacity = '0';
            iframe.style.pointerEvents = 'none';
            document.body.appendChild(iframe);

            const doc = iframe.contentDocument;
            const win = iframe.contentWindow;
            if (!doc || !win) {
                try { document.body.removeChild(iframe); } catch (_) { /* ignore */ }
                reject(new Error('Unable to create print frame'));
                return;
            }

            let finished = false;
            const finish = () => {
                if (finished) return;
                finished = true;
                try { win.removeEventListener('afterprint', onAfterPrint); } catch (_) { /* ignore */ }
                try { window.removeEventListener('afterprint', onAfterPrint); } catch (_) { /* ignore */ }
                try { window.clearTimeout(fallbackTimer); } catch (_) { /* ignore */ }
                try { document.body.removeChild(iframe); } catch (_) { /* ignore */ }
                resolve();
            };

            const fail = (e: unknown) => {
                if (finished) return;
                finished = true;
                try { win.removeEventListener('afterprint', onAfterPrint); } catch (_) { /* ignore */ }
                try { window.removeEventListener('afterprint', onAfterPrint); } catch (_) { /* ignore */ }
                try { window.clearTimeout(fallbackTimer); } catch (_) { /* ignore */ }
                try { document.body.removeChild(iframe); } catch (_) { /* ignore */ }
                reject(e instanceof Error ? e : new Error('Print failed'));
            };

            const onAfterPrint = () => {
                // afterprint fires when the print dialog closes (printed or cancelled)
                window.setTimeout(finish, 50);
            };

            // Some browsers may fire afterprint on the parent window even when printing from an iframe.
            try { win.addEventListener('afterprint', onAfterPrint); } catch (_) { /* ignore */ }
            try { window.addEventListener('afterprint', onAfterPrint); } catch (_) { /* ignore */ }

            // Safety fallback: if afterprint doesn't fire, resolve and cleanup eventually.
            const fallbackTimer = window.setTimeout(() => {
                finish();
            }, 60_000);

            doc.open();
            doc.write(`<!doctype html><html><head><meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Resume PDF</title>
          ${stylesheetLinks.map(href => `<link rel="stylesheet" href="${href}">`).join('\n')}
          <style>${printCss}</style>
          ${inlineStyles.map(css => `<style>${css}</style>`).join('\n')}
        </head><body>
          <div id="printPage"><div id="printTarget"></div></div>
        </body></html>`);
            doc.close();

            const mount = doc.getElementById('printTarget');
            if (mount) mount.appendChild(clone);

            setTimeout(() => {
                try {
                    // Fill width edge-to-edge. Height is allowed to paginate naturally.
                    const target = doc.getElementById('printTarget') as HTMLElement | null;
                    const child = target?.firstElementChild as HTMLElement | null;
                    if (target && child) {
                        // Ensure layout is up to date after CSS overrides.
                        const contentW = Math.max(1, child.scrollWidth || child.getBoundingClientRect().width);
                        const contentH = Math.max(1, child.scrollHeight || child.getBoundingClientRect().height);
                        const scaleW = availW / contentW;
                        const scaleH = availH / contentH;
                        // Never upscale; only shrink if needed to fit the padded page area.
                        const s = Math.min(1, scaleW);
                        child.style.transform = `scale(${s})`;
                    }
                    win.focus();
                    win.print();
                } catch (e) {
                    console.error('Print failed:', e);
                    fail(e);
                }
            }, 400);
        });
    }

    async function downloadPdf() {
        if (downloadingPdf) return;
        setDownloadingPdf(true);
        try {
            // Print the unscaled resume DOM (not the scaled mobile wrapper) so the PDF export logic stays deterministic.
            const root =
                document.getElementById('templatePrintContent') ||
                pdfPreviewMeasureInnerRef.current ||
                document.getElementById('templatePrintRoot');
            if (!root) {
                alert('Could not find the resume element to export.');
                return;
            }
            // Use isolated iframe print to preserve layout (avoids OKLCH parsing issues in html2canvas)
            await printElementViaHiddenIframe(root, styleSettings);

            // After PDF export, wait then show feedback modal.
            scheduleDownloadFeedbackModal();
        } catch (e: any) {
            console.error('PDF export failed:', e);
            alert(`PDF export failed (${e?.message || 'unknown error'}).`);
        } finally {
            setTimeout(() => setDownloadingPdf(false), 300);
        }
    }

    async function downloadPdfAsFile() {
        if (downloadingPdf) return;
        setDownloadingPdf(true);
        try {
            const filename = `resume-${String(templateName || 'resume')}.pdf`;
            const safeTemplate = String(templateName || 'professional');
            const qs = new URLSearchParams({
                fontScale: String(styleSettings.fontScale),
                paragraphGapPx: String(styleSettings.paragraphGapPx),
                spacingScale: String(styleSettings.spacingScale),
            });
            // Cache-bust: browsers/proxies sometimes cache GET PDFs even when content changes.
            qs.set('_ts', String(Date.now()));
            const pdfEndpointUrl = `/api/template-pdf/${encodeURIComponent(safeTemplate)}?${qs.toString()}`;
            const controller = new AbortController();
            const timeoutMs = 120_000;
            const t = window.setTimeout(() => controller.abort(), timeoutMs);
            const res = await fetch(pdfEndpointUrl, {
                method: 'GET',
                credentials: 'same-origin',
                cache: 'no-store',
                headers: {
                    Accept: 'application/pdf',
                    'Cache-Control': 'no-cache',
                    Pragma: 'no-cache',
                },
                signal: controller.signal,
            });
            window.clearTimeout(t);
            if (!res.ok) {
                const text = await res.text().catch(() => '');
                throw new Error(text || `HTTP ${res.status}`);
            }
            const ct = String(res.headers.get('content-type') || '');
            if (!ct.toLowerCase().includes('application/pdf')) {
                const text = await res.text().catch(() => '');
                throw new Error(text || `Unexpected response (${ct || 'no content-type'})`);
            }
            const blob = await res.blob();
            if (!blob || blob.size < 200) {
                throw new Error(`PDF generation returned an empty file. You can also try opening ${pdfEndpointUrl} directly.`);
            }
            const blobUrl = URL.createObjectURL(blob);
            try {
                const a = document.createElement('a');
                a.href = blobUrl;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                a.remove();
            } finally {
                window.setTimeout(() => URL.revokeObjectURL(blobUrl), 15000);
            }

            if (!isDownloadOnly && me?.is_authenticated) {
                scheduleDownloadFeedbackModal();
            }
            return true;
        } catch (e: any) {
            console.error('PDF download failed:', e);
            throw e;
        } finally {
            setTimeout(() => setDownloadingPdf(false), 300);
        }
    }

    const loadTemplateData = React.useCallback(async () => {
        console.log('TemplateViewer: Fetching template data...');
        try {
            const res = await fetch('/api/template-data');
            console.log('TemplateViewer: Response status:', res.status);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.error || `HTTP error! status: ${res.status}`);
            }
            const data = await res.json();
            console.log('TemplateViewer: Received data:', data);
            console.log('TemplateViewer: Resume data type:', typeof data.resume);
            console.log('TemplateViewer: Resume data:', JSON.stringify(data.resume, null, 2));
            if (data.success) {
                const urlRid = new URLSearchParams(window.location.search || '').get('rid') || '';
                const apiRid = String(data.source_revision_id || '').trim();
                const effectiveRid = (apiRid || urlRid).trim();
                if (effectiveRid) setSourceRevisionId(effectiveRid);

                if (!data.resume || Object.keys(data.resume).length === 0) {
                    setError('Resume data is empty. The resume may not have been parsed correctly.');
                } else {
                    setResumeData(data.resume);
                }
            } else {
                setError(data.error || 'Failed to load resume data');
            }
        } catch (err: any) {
            console.error('TemplateViewer: Error loading template data:', err);
            setError(`Error loading template data: ${err?.message || 'Please try again.'}`);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadTemplateData();
    }, [loadTemplateData]);

    useEffect(() => {
        if (editAutoAppliedRef.current) return;
        if (isDownloadOnly) return;
        if (!isCreateNewResumeFlow) return;

        editAutoAppliedRef.current = true;
        setInlineEditMode(true);

        // Clean up the URL so refresh/copy doesn't keep forcing edit mode.
        try {
            const params = new URLSearchParams(window.location.search);
            if (params.has('edit')) {
                params.delete('edit');
                const qs2 = params.toString();
                const newUrl = `${window.location.pathname}${qs2 ? `?${qs2}` : ''}${window.location.hash || ''}`;
                window.history.replaceState({}, '', newUrl);
            }
        } catch {
            // ignore
        }
    }, [isDownloadOnly, isCreateNewResumeFlow]);

    useEffect(() => {
        if (autoDownloadTriggeredRef.current) return;
        if (loading || error) return;
        if (!resumeData) return;

        const params = new URLSearchParams(window.location.search);
        const shouldAutoDownload = params.get('autodownload') === '1';
        if (!shouldAutoDownload) return;

        autoDownloadTriggeredRef.current = true;
        try {
            params.delete('autodownload');
            const qs = params.toString();
            const newUrl = `${window.location.pathname}${qs ? `?${qs}` : ''}${window.location.hash || ''}`;
            window.history.replaceState({}, '', newUrl);
        } catch (_) {
            // ignore
        }

        if (isDownloadOnly) {
            setDownloadOnlyStatus('starting');
            setDownloadOnlyError('');
        }

        // Kick off PDF export only after the resume DOM is mounted.
        let attempts = 0;
        const maxAttempts = 25;
        const attemptDownload = () => {
            attempts += 1;
            const root =
                document.getElementById('templatePrintContent') ||
                pdfPreviewMeasureInnerRef.current ||
                document.getElementById('templatePrintRoot');
            if (root) {
                // In download-only mode, do a real file download (no print dialog).
                if (isDownloadOnly) {
                    (async () => {
                        try {
                            await downloadPdfAsFile();
                            setDownloadOnlyStatus('done');
                        } catch (e: any) {
                            setDownloadOnlyStatus('failed');
                            setDownloadOnlyError(String(e?.message || 'Download failed.'));
                        }
                    })();
                } else {
                    downloadPdf();
                }
                return;
            }
            if (attempts < maxAttempts) {
                window.setTimeout(attemptDownload, 200);
            }
        };
        window.setTimeout(attemptDownload, 100);
    }, [resumeData, loading, error, isDownloadOnly]);

    async function saveEditedResume(resumeOverride?: any) {
        const payloadResume = resumeOverride ?? resumeData;
        if (!payloadResume) return;
        setEditSaving(true);
        setEditSaveError(null);
        setEditSaveSuccess(false);
        setEditSaveHubMessage(null);
        try {
            const res = await fetch('/api/template-data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ resume: payloadResume, source_revision_id: sourceRevisionId }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data?.success) {
                throw new Error(data?.error || `Failed to save (HTTP ${res.status})`);
            }
            setEditSaveSuccess(true);
            window.setTimeout(() => setEditSaveSuccess(false), 2000);

            if (data?.persisted_to_hub) {
                setEditSaveHubMessage('Saved to Job Search Hub.');
                window.setTimeout(() => setEditSaveHubMessage(null), 5000);
            } else if (typeof data?.persist_reason === 'string' && data.persist_reason) {
                const reason = String(data.persist_reason);
                if (reason === 'missing_source_revision_id') {
                    setEditSaveHubMessage('Saved here, but not linked to a Hub revision (open from Job Search Hub / View Analysis first).');
                } else if (reason === 'revision_not_found') {
                    setEditSaveHubMessage('Saved here, but the Hub revision could not be found (try refreshing Job Search Hub and saving again).');
                } else if (reason === 'snapshot_too_large') {
                    setEditSaveHubMessage('Saved here, but the snapshot is too large to store for Hub editing.');
                } else if (reason === 'not_authenticated') {
                    setEditSaveHubMessage('Saved here, but you must be logged in to save to Job Search Hub.');
                } else {
                    setEditSaveHubMessage('Saved here, but not persisted to Job Search Hub.');
                }
                try {
                    alert(`Saved locally, but NOT saved to Job Search Hub. Reason: ${reason}`);
                } catch (_) {
                    // ignore
                }
                window.setTimeout(() => setEditSaveHubMessage(null), 8000);
            } else {
                setEditSaveHubMessage('Saved here, but not persisted to Job Search Hub.');
                try {
                    alert('Saved locally, but NOT saved to Job Search Hub.');
                } catch (_) {
                    // ignore
                }
                window.setTimeout(() => setEditSaveHubMessage(null), 8000);
            }
        } catch (e: any) {
            setEditSaveError(e?.message || 'Failed to save changes.');
        } finally {
            setEditSaving(false);
        }
    }

    const setField = (key: string, value: any) => {
        setResumeData((prev: any) => ({ ...(prev || {}), [key]: value }));
    };

    const getSectionLabel = (key: string, fallback: string): string => {
        const h = resumeData?.section_headings?.[key];
        const s = String(h ?? '').trim();
        return s ? s : fallback;
    };

    const normalizeList = (v: any): string[] => {
        if (!v) return [];
        if (Array.isArray(v)) return v.map((x) => String(x ?? '').trim()).filter(Boolean);
        return String(v)
            .split(/\n|,|•/g)
            .map((s) => s.trim())
            .filter(Boolean);
    };

    const experienceList: any[] = Array.isArray(resumeData?.experience) ? resumeData.experience : [];
    const updateExperienceDescription = (idx: number, nextDescription: string) => {
        setResumeData((prev: any) => {
            const prevExp: any[] = Array.isArray(prev?.experience) ? prev.experience : [];
            const nextExp = prevExp.map((e, i) => (i === idx ? { ...(e || {}), description: nextDescription } : e));
            return { ...(prev || {}), experience: nextExp };
        });
    };

    const linksList: any[] = Array.isArray(resumeData?.links) ? resumeData.links : [];
    const updateLinkField = (idx: number, field: 'label' | 'url', value: string) => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.links) ? prev.links : [];
            const nextArr = prevArr.map((l, i) => {
                if (i !== idx) return l;
                const cur = (l && typeof l === 'object') ? l : {};
                if (field === 'label') return { ...(cur || {}), label: value };
                // Keep compatibility with templates that read url||href.
                return { ...(cur || {}), url: value };
            });
            return { ...(prev || {}), links: nextArr };
        });
    };

    const educationList: any[] = Array.isArray(resumeData?.education) ? resumeData.education : [];
    const addEducationItem = () => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.education) ? prev.education : [];
            const nextArr = [...prevArr, { degree: '', year: '', institution: '', gpa: '' }];
            return { ...(prev || {}), education: nextArr };
        });
    };
    const updateEducationField = (idx: number, field: string, value: string) => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.education) ? prev.education : [];
            const nextArr = prevArr.map((e, i) => (i === idx ? { ...(e || {}), [field]: value } : e));
            return { ...(prev || {}), education: nextArr };
        });
    };

    const projectsList: any[] = Array.isArray(resumeData?.projects) ? resumeData.projects : [];
    const addProjectItem = () => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.projects) ? prev.projects : [];
            const nextArr = [...prevArr, { title: '', technologies: '', link: '', description: '' }];
            return { ...(prev || {}), projects: nextArr };
        });
    };
    const updateProjectField = (idx: number, field: string, value: string) => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.projects) ? prev.projects : [];
            const nextArr = prevArr.map((e, i) => (i === idx ? { ...(e || {}), [field]: value } : e));
            return { ...(prev || {}), projects: nextArr };
        });
    };

    const certificationsList: any[] = Array.isArray(resumeData?.certifications) ? resumeData.certifications : [];
    const addCertificationItem = () => {
        // If the user previously hid (deleted) the Certifications section via the template UI,
        // adding a certification should make it visible again.
        const nextHidden = (Array.isArray(hiddenSectionKeys) ? hiddenSectionKeys : []).filter((k) => String(k) !== 'certifications');
        setHiddenSectionKeys(nextHidden);

        if (Array.isArray(sectionOrder) && sectionOrder.length > 0 && !sectionOrder.includes('certifications')) {
            setSectionOrder([...sectionOrder, 'certifications']);
        }

        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.certifications) ? prev.certifications : [];
            const nextArr = [...prevArr, { name: '', issuer: '', year: '' }];
            return { ...(prev || {}), certifications: nextArr };
        });
    };
    const updateCertification = (idx: number, patch: any) => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.certifications) ? prev.certifications : [];
            const nextArr = prevArr.map((c, i) => {
                if (i !== idx) return c;
                if (typeof c === 'string') return String(patch ?? '');
                return { ...(c || {}), ...(patch || {}) };
            });
            return { ...(prev || {}), certifications: nextArr };
        });
    };

    const customSectionsList: any[] = Array.isArray(resumeData?.custom_sections) ? resumeData.custom_sections : [];
    const addCustomSection = () => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.custom_sections) ? prev.custom_sections : [];
            const nextArr = [...prevArr, { heading: '', content: '' }];
            return { ...(prev || {}), custom_sections: nextArr };
        });
    };
    const updateCustomSectionHeading = (sectionIndex: number, heading: string) => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.custom_sections) ? prev.custom_sections : [];
            const nextArr = prevArr.map((sec, i) => (i === sectionIndex ? { ...(sec || {}), heading } : sec));
            return { ...(prev || {}), custom_sections: nextArr };
        });
    };
    const updateCustomSectionBody = (sectionIndex: number, value: string) => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.custom_sections) ? prev.custom_sections : [];
            const nextArr = prevArr.map((sec, i) => {
                if (i !== sectionIndex) return sec;
                // Prefer writing to `content` (templates read content/text/body)
                return { ...(sec || {}), content: value };
            });
            return { ...(prev || {}), custom_sections: nextArr };
        });
    };
    const updateCustomSectionItem = (sectionIndex: number, itemIndex: number, field: string, value: string) => {
        setResumeData((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.custom_sections) ? prev.custom_sections : [];
            const nextArr = prevArr.map((sec, i) => {
                if (i !== sectionIndex) return sec;
                const cur = (sec && typeof sec === 'object') ? sec : {};
                const items = Array.isArray(cur.items) ? [...cur.items] : [];
                const curItem = (items[itemIndex] && typeof items[itemIndex] === 'object') ? items[itemIndex] : {};
                items[itemIndex] = { ...(curItem || {}), [field]: value };
                return { ...(cur || {}), items };
            });
            return { ...(prev || {}), custom_sections: nextArr };
        });
    };

    async function aiRewriteResumeField(args: {
        field: 'summary' | 'experience_description' | 'project_description' | 'custom_section';
        text: string;
        meta?: any;
    }): Promise<string> {
        const { field, text, meta } = args;
        setAiEditError(null);
        if (!me?.is_authenticated) {
            throw new Error('Please sign in to use AI edit assistance.');
        }
        const res = await fetch('/api/ai/resume-edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ field, text, meta: meta || {} }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data?.success) {
            throw new Error(String(data?.error || `AI request failed (HTTP ${res.status})`));
        }
        const out = String(data?.text || '').trim();
        if (!out) throw new Error('AI returned an empty response.');
        return out;
    }

    // Always default customization settings on page load / template change.
    // (No persistence via cookies/localStorage.)
    useEffect(() => {
        setStyleSettings({ fontScale: 1, paragraphGapPx: 0, spacingScale: 1 });
    }, [templateName]);

    // PDF preview sizing:
    // - "Page scale" fits the Letter page into the preview area visually
    // - "Content scale" matches the Save-as-PDF fit logic (width-fit)
    useEffect(() => {
        const PAGE_W = 816;
        // Keep the content viewport at true Letter height (11in * 96dpi).
        // Then grow the *page frame* to include the visual top/bottom padding.
        const CONTENT_H = 1056;
        // Match server-side Playwright PDF margins: 0.32in top/bottom, 0in left/right.
        // (0.32in * 96dpi = 30.72px)
        const PAD_TOP = 31;
        const PAD_BOTTOM = 31;
        // Extra visual canvas height (frame only). Does not increase the content viewport.
        // Extra visual canvas height (frame only). Can be negative to reduce frame height
        // while keeping the fixed 1056px content viewport unchanged.
        const EXTRA_FRAME_PX = 20;
        const PAGE_H = CONTENT_H + PAD_TOP + PAD_BOTTOM + EXTRA_FRAME_PX;
        const VIEW_H = CONTENT_H;
        const container = pdfPreviewContainerRef.current;
        const inner = pdfPreviewMeasureInnerRef.current;
        if (!container || !inner) return;

        const compute = () => {
            // Account for the preview container padding (p-4 => 16px on each side)
            const containerW = Math.max(1, container.clientWidth - 32);
            // Measure unscaled template content and compute the same shrink-to-fit as the print iframe
            const contentW = Math.max(1, inner.scrollWidth || inner.getBoundingClientRect().width);
            const contentH = Math.max(1, inner.scrollHeight || inner.getBoundingClientRect().height);
            const scaleW = PAGE_W / contentW;
            const s = Math.min(1, scaleW);
            setPdfPreviewContentScale(s);

            // Build a snapshot with explicit per-section "push to next page" spacers.
            // This keeps section blocks from being split by the preview's page windowing,
            // so the on-screen preview matches the generated PDF's page breaks more closely.
            let extraSpacerPx = 0;
            if (!inlineEditMode) {
                try {
                    const innerRect = inner.getBoundingClientRect();
                    const liveSections = Array.from(inner.querySelectorAll('[data-tv-section="true"]')) as HTMLElement[];

                    // Decide which sections need a spacer before them.
                    // Use scaled coordinates because the preview windowing operates in scaled px.
                    const spacerByKey = new Map<string, number>();
                    let shift = 0;
                    for (const sec of liveSections) {
                        const key = String(sec.getAttribute('data-tv-section-key') || '').trim();
                        if (!key) continue;

                        const r = sec.getBoundingClientRect();
                        const topUnscaled = Math.max(0, r.top - innerRect.top);
                        const hUnscaled = Math.max(1, r.height);

                        const top = (topUnscaled * s) + shift;
                        const h = hUnscaled * s;
                        if (h >= (VIEW_H - 1)) {
                            // Too tall to keep together; allow it to span pages.
                            continue;
                        }
                        const pageIdx = Math.floor(top / VIEW_H);
                        const within = top - (pageIdx * VIEW_H);
                        const remaining = VIEW_H - within;
                        // If this section would be split, push it to the next page.
                        if (remaining > 0.5 && remaining < (h - 0.5)) {
                            const spacer = Math.max(1, Math.ceil(remaining));
                            spacerByKey.set(key, spacer);
                            shift += spacer;
                        }
                    }
                    extraSpacerPx = shift;

                    const rawHtml = inner.outerHTML || '';
                    if (rawHtml) {
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(rawHtml, 'text/html');
                        const root = doc.body.firstElementChild as HTMLElement | null;
                        if (root && spacerByKey.size > 0) {
                            const nodes = Array.from(root.querySelectorAll('[data-tv-section="true"]')) as HTMLElement[];
                            const denom = Math.max(0.0001, s);
                            for (const node of nodes) {
                                const key = String(node.getAttribute('data-tv-section-key') || '').trim();
                                const spacerH = spacerByKey.get(key);
                                if (!spacerH) continue;
                                const spacer = doc.createElement('div');
                                spacer.setAttribute('data-tv-preview-spacer', 'true');
                                spacer.style.display = 'block';
                                spacer.style.width = '100%';
                                // IMPORTANT:
                                // - `spacerH` is in *scaled* preview pixels (because VIEW_H is in the same units as our translateY stride).
                                // - The snapshot HTML is later scaled by `pdfPreviewContentScale`.
                                // Convert back to *unscaled* px so the visual spacer height becomes `spacerH` after scaling.
                                spacer.style.height = `${Math.max(1, Math.ceil(spacerH / denom))}px`;
                                node.parentNode?.insertBefore(spacer, node);
                            }
                        }
                        setPdfPreviewSnapshotHtml(root ? (root.outerHTML || '') : rawHtml);
                    } else {
                        setPdfPreviewSnapshotHtml('');
                    }
                } catch {
                    extraSpacerPx = 0;
                    setPdfPreviewSnapshotHtml('');
                }
            } else {
                setPdfPreviewSnapshotHtml('');
            }

            const scaledH = (contentH * s) + (inlineEditMode ? 0 : extraSpacerPx);
            // Page count:
            // - In view mode, tolerate a couple pixels of measurement jitter to avoid phantom extra pages.
            // - In inline edit mode, prefer being conservative (never undercount pages) to avoid clipping/cropping.
            const EPS_PX = inlineEditMode ? 0 : 2;
            const pages =
                scaledH <= (VIEW_H + EPS_PX)
                    ? 1
                    : Math.max(1, Math.ceil((scaledH - EPS_PX) / VIEW_H));
            setPdfPreviewPages(pages);

            // Prefer filling available width. If there are exactly 2 pages, scale so both pages can sit side-by-side.
            const twoUpGapPx = 24; // matches Tailwind gap-6 (1.5rem)
            // In edit mode we render a continuous scroll (no page split / 2-up), so always scale to a single page width.
            const pagesForLayout = inlineEditMode ? 1 : pages;
            const totalW = pagesForLayout === 2 ? ((PAGE_W * 2) + twoUpGapPx) : PAGE_W;
            // Add a tiny safety margin to avoid accidental horizontal scroll due to rounding/subpixel layout.
            const pageScale = Math.min(1, (containerW / totalW) * 0.995);
            setPdfPreviewPageScale(pageScale);

            // Shrink the last "page frame" to the actual remaining content height to avoid a trailing bottom edge/shadow line.
            // In inline edit mode, content height can change frequently (expand/collapse while typing), so keep full page
            // height to avoid clipping/cropping if measurements lag behind.
            if (inlineEditMode) {
                setPdfPreviewLastPageHeightPx(PAGE_H);
            } else {
                // Keep full-height pages for intermediate pages.
                const pagesForHeight = Math.max(1, Math.ceil(scaledH / VIEW_H));
                const remainderContent = Math.max(1, scaledH - (pagesForHeight - 1) * VIEW_H);
                const lastFrame = Math.min(PAGE_H, (PAD_TOP + PAD_BOTTOM + EXTRA_FRAME_PX + Math.ceil(remainderContent)));
                setPdfPreviewLastPageHeightPx(lastFrame);
            }
        };

        compute();
        const t1 = window.setTimeout(compute, 0);
        const t2 = window.setTimeout(compute, 250);

        let ro: ResizeObserver | null = null;
        if (typeof ResizeObserver !== 'undefined') {
            ro = new ResizeObserver(() => compute());
            ro.observe(container);
            // Also observe the measured template DOM, especially important in edit mode where content height changes.
            ro.observe(inner);
        } else {
            window.addEventListener('resize', compute);
        }

        return () => {
            window.clearTimeout(t1);
            window.clearTimeout(t2);
            if (ro) ro.disconnect();
            else window.removeEventListener('resize', compute);
        };
    }, [templateName, resumeData, styleSettings, inlineEditMode]);

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
                <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                    <p className="text-gray-600">Loading template...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
                <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full text-center">
                    <div className="text-red-500 text-5xl mb-4">⚠️</div>
                    <h2 className="text-xl font-bold text-gray-800 mb-2">Error</h2>
                    <p className="text-gray-600 mb-6">{error}</p>
                    <button
                        onClick={() => window.location.href = backHref}
                        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                        Go Back
                    </button>
                </div>
            </div>
        );
    }

    if (!resumeData) {
        return (
            <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
                <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full text-center">
                    <h2 className="text-xl font-bold text-gray-800 mb-2">No Resume Data</h2>
                    <p className="text-gray-600 mb-6">No resume data found. Please submit a resume first.</p>
                    <button
                        onClick={() => window.location.href = '/'}
                        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                        Go Home
                    </button>
                </div>
            </div>
        );
    }

    // Convert structured data to JSON string for templates
    // The templates expect a JSON string that parseResumeContent can parse
    const content = JSON.stringify(resumeData);
    console.log('TemplateViewer: Content being passed to template:', content.substring(0, 200) + '...');

    // Render appropriate template based on templateName
    let TemplateComponent;
    switch (templateName) {
        case 'professional':
            TemplateComponent = ProfessionalTemplate;
            break;
        // Legacy/experimental template ids: keep old links working by mapping to a supported template.
        case 'minimal':
        case 'darkSidebarProgress':
        case 'dark-sidebar-progress':
        case 'dark_sidebar_progress':
            TemplateComponent = ProfessionalTemplate;
            break;
        // New canonical template page names (and old aliases)
        case 'executive':
        case 'timelineblue':
        case 'timelineBlue':
        case 'timeline-blue':
        case 'timeline_blue':
            TemplateComponent = ExecutiveTemplate;
            break;
        case 'elegant':
        case 'lavenderclassic':
        case 'lavenderClassic':
        case 'lavender-classic':
        case 'lavender_classic':
            TemplateComponent = ClassicRoseTemplate;
            break;
        case 'creative':
        case 'popart':
        case 'popArt':
        case 'pop-art':
        case 'pop_art':
            TemplateComponent = Creative2Template;
            break;
        case 'creative2':
        case 'creative-2':
        case 'creative_2':
            TemplateComponent = Creative2Template;
            break;
        case 'classicRose':
        case 'classicrose':
        case 'classic-rose':
        case 'classic_rose':
            TemplateComponent = ClassicRoseTemplate;
            break;
        case 'boldProfessional':
        case 'boldprofessional':
        case 'bold-professional':
        case 'bold_professional':
        case 'orangeheader':
        case 'orangeHeader':
        case 'orange-header':
        case 'orange_header':
            TemplateComponent = BoldProfessionalTemplate;
            break;
        case 'traditional':
        case 'bluelineclassic':
        case 'blueLineClassic':
        case 'blue-line-classic':
        case 'blue_line_classic':
            TemplateComponent = TraditionalTemplate;
            break;
        case 'modern':
        case 'cleansidebar':
        case 'cleanSidebar':
        case 'clean-sidebar':
        case 'clean_sidebar':
            TemplateComponent = ModernTemplate;
            break;
        case 'minimalSidebar':
        case 'minimalsidebar':
        case 'minimal-sidebar':
        case 'minimal_sidebar':
            TemplateComponent = CleanTemplate;
            break;
        default:
            return (
                <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
                    <div className="bg-white rounded-lg shadow-lg p-8 max-w-md w-full text-center">
                        <h2 className="text-xl font-bold text-gray-800 mb-2">Template Not Found</h2>
                        <p className="text-gray-600 mb-6">The template "{templateName}" does not exist.</p>
                        <button
                            onClick={() => window.location.href = backHref}
                            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                        >
                            Go Back
                        </button>
                    </div>
                </div>
            );
    }

    const isTimelineBlue = templateName === 'executive' || templateName === 'timelineblue' || templateName === 'timelineBlue' || templateName === 'timeline-blue' || templateName === 'timeline_blue';

    return (
        <div
            ref={embedRootRef}
            className={isEmbed ? 'tv-embed bg-transparent overflow-x-hidden overflow-y-hidden h-screen' : 'min-h-screen bg-gray-100'}
        >
            {/* Offscreen export root (used by server-side Playwright PDF generation)
               NOTE: keep this out of the document's scrollable overflow area to avoid
               spurious scrollbars (especially in iframe embed mode). */}
            <div style={{ position: 'fixed', left: '-100000px', top: 0, width: '816px', opacity: 0, pointerEvents: 'none' }}>
                <div id="templatePrintRoot">
                    <div
                        id="templatePrintContent"
                        className="tv-style-root"
                        style={{
                            // @ts-ignore
                            ['--tv-paragraph-gap']: `${styleSettings.paragraphGapPx}px`,
                            // @ts-ignore
                            ['--tv-font-scale']: String(styleSettings.fontScale),
                            // @ts-ignore
                            ['--tv-space-scale']: String(styleSettings.spacingScale),
                        }}
                    >
                        <TemplateComponent
                            content={content}
                            editMode={false}
                            sectionOrder={sectionOrder}
                            onSectionOrderChange={setSectionOrder}
                            hiddenSectionKeys={hiddenSectionKeys}
                            onHiddenSectionKeysChange={setHiddenSectionKeys}
                        />
                    </div>
                </div>
            </div>

            {!isEmbed && (
                <>
                    <header className="border-b bg-white">
                        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
                            <a href="/" className="inline-flex items-center gap-3">
                                <img src="/static/images/logo23_small.webp" alt="Resumatic AI" className="h-16 w-auto object-contain" width={96} height={96} loading="lazy" />
                            </a>

                            <nav className="hidden md:flex items-center gap-6 text-gray-700" aria-label="Primary">
                                <a href="/" className="hover:text-indigo-600 font-semibold">Home</a>
                                <a href="/blog" className="hover:text-indigo-600 font-semibold">Blog</a>
                                <a href="/about" className="hover:text-indigo-600 font-semibold">About</a>
                                {me?.is_authenticated ? (
                                    <>
                                        <a href="/my_revisions" className="text-white bg-indigo-600 px-4 py-2 rounded-xl hover:bg-indigo-700">
                                            My Account
                                        </a>
                                        <a href="/logout" className="text-white bg-red-500 px-4 py-2 rounded-xl hover:bg-red-600">
                                            Sign Out
                                        </a>
                                    </>
                                ) : (
                                    <a href="/login" className="text-white bg-indigo-600 px-4 py-2 rounded-xl hover:bg-indigo-700">
                                        Login
                                    </a>
                                )}
                            </nav>

                            <button
                                type="button"
                                onClick={() => setMobileNavOpen(v => !v)}
                                className="md:hidden inline-flex items-center justify-center p-2 rounded-xl text-gray-700 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                                aria-controls="mobileMenu"
                                aria-expanded={mobileNavOpen ? 'true' : 'false'}
                            >
                                <span className="sr-only">Open menu</span>
                                <svg className="h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                                </svg>
                            </button>
                        </div>
                    </header>

                    {/* Mobile overlay */}
                    <div
                        className={`fixed inset-0 bg-black/30 z-40 transition-opacity md:hidden ${mobileNavOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
                        aria-hidden={mobileNavOpen ? 'false' : 'true'}
                        onClick={() => setMobileNavOpen(false)}
                    />

                    {/* Mobile Menu (right-side slide-in) */}
                    <div
                        id="mobileMenu"
                        className={`fixed top-0 right-0 h-full w-64 bg-white shadow-lg z-50 p-6 md:hidden transform transition-transform duration-300 ease-in-out ${mobileNavOpen ? 'translate-x-0' : 'translate-x-full'}`}
                        aria-label="Mobile"
                    >
                        <div className="flex justify-between items-center mb-8">
                            <img alt="Logo" className="h-16 w-auto object-contain" src="/static/images/logo23_small.webp" loading="lazy" width={96} height={96} />
                            <button
                                type="button"
                                className="text-gray-500 hover:text-gray-900"
                                aria-label="Close menu"
                                onClick={() => setMobileNavOpen(false)}
                            >
                                ✕
                            </button>
                        </div>
                        <nav className="space-y-4">
                            <a className="block text-gray-600 hover:text-indigo-600 underline underline-offset-2 font-semibold" href="/" onClick={() => setMobileNavOpen(false)}>Home</a>
                            <a className="block text-gray-600 hover:text-indigo-600 underline underline-offset-2 font-semibold" href="/blog" onClick={() => setMobileNavOpen(false)}>Blog</a>
                            <a className="block text-gray-600 hover:text-indigo-600 underline underline-offset-2 font-semibold" href="/about" onClick={() => setMobileNavOpen(false)}>About</a>
                            {me?.is_authenticated ? (
                                <>
                                    <a className="block px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 text-center" href="/my_revisions" onClick={() => setMobileNavOpen(false)}>My Account</a>
                                    <a className="block px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 text-center" href="/logout" onClick={() => setMobileNavOpen(false)}>Sign Out</a>
                                </>
                            ) : (
                                <a className="block px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 text-center" href="/login" onClick={() => setMobileNavOpen(false)}>Login</a>
                            )}
                        </nav>
                    </div>
                </>
            )}

            <main className={isEmbed ? '' : 'py-8 px-4'}>
                <div className={isEmbed ? '' : 'max-w-7xl mx-auto'}>
                    <style>{`
                  /* Mobile should match desktop: make key md:* utilities behave like desktop even on small viewports. */
                  #templatePrintRoot .md\\:flex-row { flex-direction: row !important; }
                  #templatePrintRoot .md\\:w-\\[300px\\] { width: 300px !important; }
                  #templatePrintRoot .md\\:flex-shrink-0 { flex-shrink: 0 !important; }
                  #templatePrintRoot .md\\:text-base { font-size: 1rem !important; line-height: 1.5rem !important; }
                  #templatePrintRoot .md\\:grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; }

                  /* Resume customization: apply only inside the resume root */
                  /* Paragraph gap: apply even when a template only renders single <p> blocks */
                  #templatePrintRoot .tv-style-root p { margin: 0 0 var(--tv-paragraph-gap, 0px) 0 !important; }

                  /* Font scaling: override Tailwind text-* utilities to scale font sizes (causes reflow, not zoom). */
                  #templatePrintRoot .tv-style-root { font-size: calc(1rem * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-xs { font-size: calc(0.75rem * var(--tv-font-scale, 1)) !important; line-height: calc(1rem * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-sm { font-size: calc(0.875rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.25rem * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-base { font-size: calc(1rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.5rem * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-lg { font-size: calc(1.125rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.75rem * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-xl { font-size: calc(1.25rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.75rem * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-2xl { font-size: calc(1.5rem * var(--tv-font-scale, 1)) !important; line-height: calc(2rem * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-3xl { font-size: calc(1.875rem * var(--tv-font-scale, 1)) !important; line-height: calc(2.25rem * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-4xl { font-size: calc(2.25rem * var(--tv-font-scale, 1)) !important; line-height: calc(2.5rem * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-5xl { font-size: calc(3rem * var(--tv-font-scale, 1)) !important; line-height: 1 !important; }

                  /* Also scale Tailwind "arbitrary" font sizes used by some templates (e.g. text-[11px]) */
                  #templatePrintRoot .tv-style-root .text-\\[10px\\] { font-size: calc(10px * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-\\[11px\\] { font-size: calc(11px * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-\\[12px\\] { font-size: calc(12px * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-\\[13px\\] { font-size: calc(13px * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-\\[34px\\] { font-size: calc(34px * var(--tv-font-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .text-\\[38px\\] { font-size: calc(38px * var(--tv-font-scale, 1)) !important; }

                  /* Scale Tailwind space-y-* gaps with a single multiplier */
                  #templatePrintRoot .tv-style-root .space-y-10 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .space-y-8  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(2rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .space-y-6  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .space-y-5  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .space-y-4  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .space-y-3  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .space-y-2  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(0.5rem * var(--tv-space-scale, 1)) !important; }

                  /* Also scale common Tailwind margin utilities used by templates for section separation */
                  #templatePrintRoot .tv-style-root .mb-12 { margin-bottom: calc(3rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mb-10 { margin-bottom: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mb-8  { margin-bottom: calc(2rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mb-6  { margin-bottom: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mb-5  { margin-bottom: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mb-4  { margin-bottom: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mb-3  { margin-bottom: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mb-2  { margin-bottom: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mb-1  { margin-bottom: calc(0.25rem * var(--tv-space-scale, 1)) !important; }

                  #templatePrintRoot .tv-style-root .mt-12 { margin-top: calc(3rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mt-10 { margin-top: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mt-8  { margin-top: calc(2rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mt-6  { margin-top: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mt-5  { margin-top: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mt-4  { margin-top: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mt-3  { margin-top: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mt-2  { margin-top: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .mt-1  { margin-top: calc(0.25rem * var(--tv-space-scale, 1)) !important; }

                  /* Scale common flex/grid gaps too */
                  #templatePrintRoot .tv-style-root .gap-8 { gap: calc(2rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .gap-6 { gap: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .gap-5 { gap: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .gap-4 { gap: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .gap-3 { gap: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .gap-2 { gap: calc(0.5rem * var(--tv-space-scale, 1)) !important; }

                  /* Scale common padding-bottom utilities used by templates for section/item spacing */
                  #templatePrintRoot .tv-style-root .pb-4 { padding-bottom: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .pb-3 { padding-bottom: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .pb-2 { padding-bottom: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                  #templatePrintRoot .tv-style-root .pb-0 { padding-bottom: 0 !important; }

                  /* PDF preview page styling (HTML-only simulation of the PDF) */
                  .pdfPreviewPage {
                    width: 816px;
                                                                                                                                                                height: var(--pdf-page-h, 1138px);
                    background: #fff;
                    position: relative;
                                        overflow: hidden;
                    box-shadow: 0 12px 30px rgba(0,0,0,0.12);
                  }
                                    /* Continuous edit-mode preview: no forced page height or clipping */
                                    .pdfPreviewPageContinuous {
                                        height: auto !important;
                                        overflow: visible !important;
                                        box-shadow: none !important;
                                    }
                                    /* Remove the bottom "end-of-document" shadow marker on the LAST page. */
                                    .pdfPreviewPageLast {
                                        box-shadow: none !important;
                                    }
                  .pdfPreviewTarget {
                    position: relative;
                    top: 0;
                    left: 0;
                    width: 816px;
                                                                                                                                                                height: var(--pdf-page-h, 1138px);
                                        overflow: hidden;
                                        contain: paint;
                                                                                --pdf-pad-top: 31px;
                                                                                --pdf-pad-bottom: 31px;
                  }
                                    /* Remove template outer "card" shadow/ring in preview (clipped shadows can look like an end marker). */
                                    .pdfPreviewTarget .tv-style-root > * {
                                        box-shadow: none !important;
                                    }
                                                                        .pdfPreviewViewport {
                                                                                position: absolute;
                                                                                left: 0;
                                                                                right: 0;
                                                                                top: var(--pdf-pad-top);
                                                                                height: 1056px;
                                                                                overflow: hidden;
                                                                        }
                                    .pdfPreviewTargetContinuous {
                                        height: auto !important;
                                        overflow: visible !important;
                                        contain: none !important;
                                    }
                  /* Match the print iframe's outer-gutter stripping */
                                    .pdfPreviewTarget > *,
                                    .pdfPreviewViewport > * {
                    width: 816px !important;
                    max-width: none !important;
                    margin: 0 !important;
                  }
                  .pdfPreviewTarget .mx-auto { margin-left: 0 !important; margin-right: 0 !important; }
                  .pdfPreviewTarget .max-w-3xl,
                  .pdfPreviewTarget .max-w-4xl,
                  .pdfPreviewTarget .max-w-5xl,
                  .pdfPreviewTarget .max-w-6xl,
                  .pdfPreviewTarget .max-w-7xl { max-width: none !important; width: 100% !important; }
                  .pdfPreviewTarget .md\\:flex-row { flex-direction: row !important; }
                  .pdfPreviewTarget .md\\:w-\\[300px\\] { width: 300px !important; }
                  .pdfPreviewTarget .md\\:flex-shrink-0 { flex-shrink: 0 !important; }

                  /* Apply Customize variables in the preview too */
                  .pdfPreviewTarget .tv-style-root p { margin: 0 0 var(--tv-paragraph-gap, 0px) 0 !important; }
                  .pdfPreviewTarget .tv-style-root { font-size: calc(1rem * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-xs { font-size: calc(0.75rem * var(--tv-font-scale, 1)) !important; line-height: calc(1rem * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-sm { font-size: calc(0.875rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.25rem * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-base { font-size: calc(1rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.5rem * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-lg { font-size: calc(1.125rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.75rem * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-xl { font-size: calc(1.25rem * var(--tv-font-scale, 1)) !important; line-height: calc(1.75rem * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-2xl { font-size: calc(1.5rem * var(--tv-font-scale, 1)) !important; line-height: calc(2rem * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-3xl { font-size: calc(1.875rem * var(--tv-font-scale, 1)) !important; line-height: calc(2.25rem * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-4xl { font-size: calc(2.25rem * var(--tv-font-scale, 1)) !important; line-height: calc(2.5rem * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-5xl { font-size: calc(3rem * var(--tv-font-scale, 1)) !important; line-height: 1 !important; }

                  /* Also scale Tailwind "arbitrary" font sizes used by some templates (e.g. text-[11px]) */
                  .pdfPreviewTarget .tv-style-root .text-\\[10px\\] { font-size: calc(10px * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-\\[11px\\] { font-size: calc(11px * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-\\[12px\\] { font-size: calc(12px * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-\\[13px\\] { font-size: calc(13px * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-\\[34px\\] { font-size: calc(34px * var(--tv-font-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .text-\\[38px\\] { font-size: calc(38px * var(--tv-font-scale, 1)) !important; }

                  .pdfPreviewTarget .tv-style-root .space-y-10 > :not([hidden]) ~ :not([hidden]) { margin-top: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .space-y-8  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(2rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .space-y-6  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .space-y-5  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .space-y-4  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .space-y-3  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .space-y-2  > :not([hidden]) ~ :not([hidden]) { margin-top: calc(0.5rem * var(--tv-space-scale, 1)) !important; }

                  .pdfPreviewTarget .tv-style-root .mb-12 { margin-bottom: calc(3rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mb-10 { margin-bottom: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mb-8  { margin-bottom: calc(2rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mb-6  { margin-bottom: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mb-5  { margin-bottom: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mb-4  { margin-bottom: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mb-3  { margin-bottom: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mb-2  { margin-bottom: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mb-1  { margin-bottom: calc(0.25rem * var(--tv-space-scale, 1)) !important; }

                  .pdfPreviewTarget .tv-style-root .mt-12 { margin-top: calc(3rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mt-10 { margin-top: calc(2.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mt-8  { margin-top: calc(2rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mt-6  { margin-top: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mt-5  { margin-top: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mt-4  { margin-top: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mt-3  { margin-top: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mt-2  { margin-top: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .mt-1  { margin-top: calc(0.25rem * var(--tv-space-scale, 1)) !important; }

                  .pdfPreviewTarget .tv-style-root .gap-8 { gap: calc(2rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .gap-6 { gap: calc(1.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .gap-5 { gap: calc(1.25rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .gap-4 { gap: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .gap-3 { gap: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .gap-2 { gap: calc(0.5rem * var(--tv-space-scale, 1)) !important; }

                  /* Scale common padding-bottom utilities used by templates for section/item spacing */
                  .pdfPreviewTarget .tv-style-root .pb-4 { padding-bottom: calc(1rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .pb-3 { padding-bottom: calc(0.75rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .pb-2 { padding-bottom: calc(0.5rem * var(--tv-space-scale, 1)) !important; }
                  .pdfPreviewTarget .tv-style-root .pb-0 { padding-bottom: 0 !important; }
                `}</style>

                    {!isEmbed && isDownloadOnly && (
                        <div className="mb-4">
                            <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-5">
                                <div className="text-base font-semibold text-gray-900">Resume PDF download</div>
                                <div className="mt-1 text-sm text-gray-700">
                                    {downloadOnlyStatus === 'idle' && 'Click “Download PDF” if your browser blocks auto-downloads.'}
                                    {downloadOnlyStatus === 'starting' && 'Preparing your PDF. Your download should start shortly…'}
                                    {downloadOnlyStatus === 'done' && 'Download started. You can return to Job Search Hub.'}
                                    {downloadOnlyStatus === 'failed' && 'Auto-download did not start.'}
                                </div>

                                <div className="mt-3 flex items-start gap-2 text-xs text-amber-800 leading-relaxed">
                                    <span className="mt-0.5 inline-flex items-center justify-center w-7 h-7 rounded-lg bg-amber-50 border border-amber-200 shrink-0 shadow-sm">
                                        <AlertTriangle className="w-4 h-4 text-amber-600" aria-hidden="true" />
                                    </span>
                                    <p>
                                        Note, pdf download may not exactly match the screen display due to different screen display settings. Download the PDF to determine optimal settings.
                                    </p>
                                </div>

                                {downloadOnlyStatus === 'failed' && downloadOnlyError && (
                                    <div className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                                        {downloadOnlyError}
                                    </div>
                                )}

                                <div className="mt-4 flex flex-col sm:flex-row gap-2">
                                    <button
                                        type="button"
                                        className={`px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors ${downloadingPdf ? 'opacity-60 cursor-not-allowed' : ''}`}
                                        disabled={downloadingPdf}
                                        onClick={() => {
                                            if (me && !me.is_paid) {
                                                const next = `${window.location.pathname}${window.location.search || ''}`;
                                                window.location.href = `/plans?next=${encodeURIComponent(next)}&reason=pdf`;
                                                return;
                                            }
                                            setDownloadOnlyStatus('starting');
                                            setDownloadOnlyError('');
                                            downloadPdfAsFile()
                                                .then(() => {
                                                    setDownloadOnlyStatus('done');
                                                })
                                                .catch((e: any) => {
                                                    setDownloadOnlyStatus('failed');
                                                    setDownloadOnlyError(String(e?.message || 'Download failed.'));
                                                });
                                        }}
                                    >
                                        {downloadingPdf ? 'Preparing…' : 'Download PDF'}
                                    </button>
                                    <button
                                        type="button"
                                        className="px-4 py-2 rounded-lg bg-white border border-gray-200 text-gray-800 hover:bg-gray-50 transition-colors"
                                        onClick={downloadOnlyReturnToHub}
                                    >
                                        Back to Job Search Hub
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {!isEmbed && !isDownloadOnly && (
                        <>
                            {/* Header with back button and template name */}
                            <div id="templateViewerHeader" className="mb-3">
                                <h1 className="text-2xl font-bold text-gray-800 break-words">{templateDisplayName || templateName} Template</h1>
                                <div className="mt-2 flex flex-col sm:flex-row sm:items-center sm:justify-end gap-2">
                                    <div className="flex items-center gap-2 flex-wrap sm:justify-end">
                                        {/* Edit Mode now available for ALL templates */}
                                        <button
                                            onClick={() => setInlineEditMode(!inlineEditMode)}
                                            className={`px-4 py-2 rounded-lg border transition-colors flex items-center gap-2 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${inlineEditMode
                                                ? 'bg-indigo-600 text-white border-indigo-600 hover:bg-indigo-700 shadow-sm'
                                                : 'bg-indigo-50 border-indigo-300 text-indigo-700 hover:bg-indigo-100 hover:border-indigo-400 shadow-sm hover:shadow'
                                                }`}
                                        >
                                            <Edit3 className="w-4 h-4" />
                                            {inlineEditMode ? 'Exit Edit Mode' : 'Switch to Edit Mode'}
                                        </button>
                                        {inlineEditMode && (
                                            <button
                                                type="button"
                                                onClick={async () => {
                                                    const merged = { ...(resumeData || {}), ...(inlineEditChanges || {}) };
                                                    setResumeData(merged);
                                                    await saveEditedResume(merged);
                                                    setInlineEditChanges({});
                                                }}
                                                className={`px-3 py-2 rounded-lg border transition-colors flex items-center gap-2 ${editSaving
                                                    ? 'bg-gray-100 text-gray-500 border-gray-200 cursor-not-allowed'
                                                    : 'bg-green-600 text-white border-green-600 hover:bg-green-700'
                                                    }`}
                                                disabled={editSaving}
                                            >
                                                {editSaving ? 'Saving…' : 'Save Changes'}
                                            </button>
                                        )}
                                        {inlineEditMode ? (
                                            <div className="px-3 py-2 rounded-lg bg-gray-50 border border-gray-200 text-gray-700 text-sm flex items-start gap-2">
                                                <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" aria-hidden="true" />
                                                <span>
                                                    Click "Exit Edit mode" for <span className="text-indigo-600 font-medium">PDF download</span>.
                                                </span>
                                            </div>
                                        ) : (
                                            <div className="flex items-center gap-2">
                                                <button
                                                    type="button"
                                                    onClick={async () => {
                                                        if (downloadingPdf) return;
                                                        if (!me) return;
                                                        if (!me?.is_paid) {
                                                            const next = `${window.location.pathname}${window.location.search || ''}`;
                                                            window.location.href = `/plans?next=${encodeURIComponent(next)}&reason=pdf`;
                                                            return;
                                                        }
                                                        try {
                                                            await downloadPdfAsFile();
                                                        } catch (e: any) {
                                                            console.error('PDF download failed:', e);
                                                            alert(`PDF download failed (${e?.message || 'unknown error'}).`);
                                                        }
                                                    }}
                                                    className={`px-3 py-2 rounded-lg bg-white border border-gray-200 text-gray-800 hover:bg-gray-50 transition-colors ${downloadingPdf ? 'opacity-60 cursor-not-allowed' : ''}`}
                                                    disabled={downloadingPdf || !me}
                                                >
                                                    {!me ? 'Loading…' : (downloadingPdf ? 'Preparing…' : 'Download PDF')}
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {(editSaving || editSaveError || editSaveHubMessage || editSaveSuccess) && (
                                <div className="mb-6">
                                    {editSaving && (
                                        <div className="text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                                            Saving…
                                        </div>
                                    )}
                                    {!editSaving && editSaveError && (
                                        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                                            {editSaveError}
                                        </div>
                                    )}
                                    {!editSaving && !editSaveError && editSaveHubMessage && (
                                        <div className="text-sm text-gray-800 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                                            {editSaveHubMessage}
                                        </div>
                                    )}
                                    {!editSaving && !editSaveError && !editSaveHubMessage && editSaveSuccess && (
                                        <div className="text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
                                            Saved.
                                        </div>
                                    )}
                                </div>
                            )}

                        </>
                    )}

                    <div className={`grid ${(isDownloadOnly || isEmbed) ? 'grid-cols-1' : 'grid-cols-[125px_minmax(0,1fr)] sm:grid-cols-[300px_minmax(0,1fr)] md:grid-cols-[360px_minmax(0,1fr)]'} gap-4 sm:gap-6`}>
                        {/* Left settings panel */}
                        {!isDownloadOnly && !isEmbed && (
                            <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden h-fit shadow-sm">
                                <div className="px-4 py-4 bg-gradient-to-r from-indigo-50 via-white to-emerald-50 border-b border-gray-100">
                                    <div className="flex items-start">
                                        <div className="flex-1">
                                            <div className="inline-flex items-center gap-2 text-base font-extrabold text-gray-900">
                                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-indigo-600 text-white shadow-sm">TIP</span>
                                                <span> Aim for one page</span>
                                            </div>
                                            <div className="mt-1 flex items-start gap-2 text-sm text-gray-700 leading-relaxed">
                                                <span className="mt-0.5 inline-flex items-center justify-center w-7 h-7 rounded-lg bg-sky-100 border border-sky-200 shrink-0 shadow-sm">
                                                    <Lightbulb className="w-4.5 h-4.5 text-sky-700" />
                                                </span>
                                                <p>
                                                    In many cases, recruiters prefer a one‑page resume. Use the sliders below to adjust font size and spacing to fit cleanly.
                                                </p>
                                            </div>

                                            <div className="mt-2 flex items-start gap-2 text-xs text-amber-800 leading-relaxed">
                                                <span className="mt-0.5 inline-flex items-center justify-center w-7 h-7 rounded-lg bg-amber-50 border border-amber-200 shrink-0 shadow-sm">
                                                    <AlertTriangle className="w-4 h-4 text-amber-600" aria-hidden="true" />
                                                </span>
                                                <p>
                                                    Note, pdf download may not exactly match the screen display. Download the PDF to determine optimal settings.
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div className="p-4">
                                    <div>
                                        <div className="flex items-center justify-between mb-3">
                                            <h2 className="text-sm font-semibold text-gray-900">Settings</h2>
                                            <button
                                                className="inline-flex items-center gap-2 text-sm text-indigo-700 hover:text-indigo-800"
                                                onClick={() => setStyleSettings({ fontScale: 1, paragraphGapPx: 0, spacingScale: 1 })}
                                            >
                                                <RotateCcw className="w-4 h-4" />
                                                Reset
                                            </button>
                                        </div>

                                        <div className="space-y-4">
                                            <div className="rounded-xl border border-gray-200 bg-white p-3">
                                                <div className="flex items-center justify-between mb-2">
                                                    <label className="text-xs font-semibold text-gray-800 flex items-center gap-2">
                                                        <Type className="w-4 h-4 text-indigo-600" />
                                                        Font size
                                                    </label>
                                                    <span className="text-xs text-gray-600">{Math.round(styleSettings.fontScale * 100)}%</span>
                                                </div>
                                                <input
                                                    type="range"
                                                    min={0.6}
                                                    max={1.4}
                                                    step={0.01}
                                                    value={styleSettings.fontScale}
                                                    onChange={(e) => setStyleSettings(s => ({ ...s, fontScale: Number(e.target.value) }))}
                                                    className="w-full"
                                                />
                                            </div>

                                            <div className="rounded-xl border border-gray-200 bg-white p-3">
                                                <div className="flex items-center justify-between mb-2">
                                                    <label className="text-xs font-semibold text-gray-800 flex items-center gap-2">
                                                        <AlignLeft className="w-4 h-4 text-emerald-600" />
                                                        Paragraph gap
                                                    </label>
                                                    <span className="text-xs text-gray-600">{styleSettings.paragraphGapPx}px</span>
                                                </div>
                                                <input
                                                    type="range"
                                                    min={-40}
                                                    max={200}
                                                    step={1}
                                                    value={styleSettings.paragraphGapPx}
                                                    onChange={(e) => setStyleSettings(s => ({ ...s, paragraphGapPx: Number(e.target.value) }))}
                                                    className="w-full"
                                                />
                                            </div>

                                            <div className="rounded-xl border border-gray-200 bg-white p-3">
                                                <div className="flex items-center justify-between mb-2">
                                                    <label className="text-xs font-semibold text-gray-800 flex items-center gap-2">
                                                        <Rows className="w-4 h-4 text-purple-600" />
                                                        Section spacing
                                                    </label>
                                                    <span className="text-xs text-gray-600">{Math.round(styleSettings.spacingScale * 100)}%</span>
                                                </div>
                                                <input
                                                    type="range"
                                                    min={0}
                                                    max={5}
                                                    step={0.01}
                                                    value={styleSettings.spacingScale}
                                                    onChange={(e) => setStyleSettings(s => ({ ...s, spacingScale: Number(e.target.value) }))}
                                                    className="w-full"
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Edit fields (only visible in Edit Mode) */}
                                {inlineEditMode && (
                                    <div className="px-4 pb-4">
                                        <div className="rounded-2xl border border-gray-200 bg-white p-4">
                                            <div className="flex items-center justify-between mb-3">
                                                <h2 className="text-sm font-semibold text-gray-900">Edit fields</h2>
                                                <div className="flex items-center gap-2">
                                                    <button
                                                        type="button"
                                                        onClick={() => loadTemplateData()}
                                                        className="text-sm text-gray-600 hover:text-gray-800"
                                                        disabled={editSaving}
                                                    >
                                                        Reset
                                                    </button>
                                                </div>
                                            </div>

                                            {editSaveError && (
                                                <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">
                                                    {editSaveError}
                                                </div>
                                            )}
                                            {editSaveSuccess && (
                                                <div className="mb-3 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg p-2">
                                                    Saved.
                                                </div>
                                            )}

                                            {editSaveHubMessage && (
                                                <div className="mb-3 text-sm text-gray-800 bg-gray-50 border border-gray-200 rounded-lg p-2">
                                                    {editSaveHubMessage}
                                                </div>
                                            )}

                                            {aiEditError && (
                                                <div className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-2">
                                                    {aiEditError}
                                                </div>
                                            )}

                                            <div className="space-y-3">
                                                <Field label="Name">
                                                    <input
                                                        value={String(resumeData?.name ?? '')}
                                                        onChange={(e) => setField('name', e.target.value)}
                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                    />
                                                </Field>
                                                <Field label="Title">
                                                    <input
                                                        value={String(resumeData?.title ?? '')}
                                                        onChange={(e) => setField('title', e.target.value)}
                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                    />
                                                </Field>
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                                    <Field label="Email">
                                                        <input
                                                            value={String(resumeData?.email ?? '')}
                                                            onChange={(e) => setField('email', e.target.value)}
                                                            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                        />
                                                    </Field>
                                                    <Field label="Phone">
                                                        <input
                                                            value={String(resumeData?.phone ?? '')}
                                                            onChange={(e) => setField('phone', e.target.value)}
                                                            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                        />
                                                    </Field>
                                                </div>
                                                <Field label="Location">
                                                    <input
                                                        value={String(resumeData?.location ?? '')}
                                                        onChange={(e) => setField('location', e.target.value)}
                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                    />
                                                </Field>

                                                {(String(resumeData?.website ?? resumeData?.portfolio ?? '').trim() || linksList.length > 0) && (
                                                    <Field label="Website">
                                                        <input
                                                            value={String(resumeData?.website ?? resumeData?.portfolio ?? '')}
                                                            onChange={(e) => setField('website', e.target.value)}
                                                            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                        />
                                                    </Field>
                                                )}

                                                {(linksList.length > 0) && (
                                                    <div>
                                                        <div className="text-sm font-bold text-blue-700 border-b border-gray-200 pb-1">Links</div>
                                                        <div className="mt-2 space-y-2">
                                                            {linksList.map((l: any, idx: number) => {
                                                                const label = String(l?.label ?? l?.name ?? l?.title ?? '').trim();
                                                                const url = String(l?.url ?? l?.href ?? '').trim();
                                                                return (
                                                                    <div key={idx} className="rounded-xl border border-gray-200 p-3 bg-white">
                                                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                                            <Field label="Label">
                                                                                <input
                                                                                    value={label}
                                                                                    onChange={(e) => updateLinkField(idx, 'label', e.target.value)}
                                                                                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                />
                                                                            </Field>
                                                                            <Field label="URL">
                                                                                <input
                                                                                    value={url}
                                                                                    onChange={(e) => updateLinkField(idx, 'url', e.target.value)}
                                                                                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                />
                                                                            </Field>
                                                                        </div>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                )}
                                                {(() => {
                                                    const hidden = new Set((Array.isArray(hiddenSectionKeys) ? hiddenSectionKeys : []).map(String));
                                                    const blocks: Record<string, React.ReactNode> = {};

                                                    const skillsVals = normalizeList(resumeData?.skills);
                                                    const languageVals = normalizeList(resumeData?.languages);

                                                    blocks.summary = (
                                                        <label className="block">
                                                            <div className="flex items-center justify-between border-b border-gray-200 pb-1 mb-2">
                                                                <div className="text-sm font-bold text-blue-700">{getSectionLabel('summary', 'Professional summary')}</div>
                                                                <button
                                                                    type="button"
                                                                    className={
                                                                        'text-xs inline-flex items-center px-2 py-1 rounded-md border ' +
                                                                        (aiBusySummary
                                                                            ? 'bg-gray-100 border-gray-200 text-gray-500 cursor-not-allowed'
                                                                            : 'bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-50')
                                                                    }
                                                                    disabled={aiBusySummary}
                                                                    onClick={async () => {
                                                                        try {
                                                                            setAiBusySummary(true);
                                                                            const nextText = await aiRewriteResumeField({
                                                                                field: 'summary',
                                                                                text: String(resumeData?.summary ?? ''),
                                                                                meta: {
                                                                                    title: String(resumeData?.title ?? ''),
                                                                                },
                                                                            });
                                                                            setField('summary', nextText);
                                                                        } catch (e: any) {
                                                                            setAiEditError(String(e?.message || 'AI edit failed.'));
                                                                        } finally {
                                                                            setAiBusySummary(false);
                                                                        }
                                                                    }}
                                                                >
                                                                    {aiBusySummary ? (
                                                                        'Improving…'
                                                                    ) : (
                                                                        <>
                                                                            <Wand2 className="inline w-3 h-3 mr-1" />
                                                                            Assist with AI
                                                                        </>
                                                                    )}
                                                                </button>
                                                            </div>
                                                            <textarea
                                                                value={String(resumeData?.summary ?? '')}
                                                                onChange={(e) => setField('summary', e.target.value)}
                                                                rows={4}
                                                                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                            />
                                                        </label>
                                                    );

                                                    blocks.skills = (
                                                        <ListField
                                                            label={getSectionLabel('skills', 'Skills')}
                                                            hint={(() => {
                                                                const limit = getTemplateSkillsLimit(templateName);
                                                                if (!limit) return undefined;
                                                                return '# of skills limited by template';
                                                            })()}
                                                            values={skillsVals}
                                                            onChange={(vals: string[]) => setField('skills', vals)}
                                                        />
                                                    );

                                                    blocks.languages = (
                                                        <ListField
                                                            label={getSectionLabel('languages', 'Languages')}
                                                            values={languageVals}
                                                            onChange={(vals: string[]) => setField('languages', vals)}
                                                        />
                                                    );

                                                    blocks.education = (
                                                        <div>
                                                            <div className="flex items-center justify-between border-b border-gray-200 pb-1">
                                                                <div className="text-sm font-bold text-blue-700">{getSectionLabel('education', 'Education')}</div>
                                                                <button
                                                                    type="button"
                                                                    className="text-xs text-indigo-700 hover:text-indigo-800"
                                                                    onClick={addEducationItem}
                                                                >
                                                                    Add
                                                                </button>
                                                            </div>
                                                            {educationList.length === 0 ? (
                                                                <div className="mt-2 text-sm text-gray-500">No education entries yet.</div>
                                                            ) : (
                                                                <div className="mt-2 space-y-2">
                                                                    {educationList.map((edu: any, idx: number) => (
                                                                        <div key={idx} className="rounded-xl border border-gray-200 p-3 bg-white">
                                                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                                                <Field label="Degree">
                                                                                    <input
                                                                                        value={String(edu?.degree ?? '')}
                                                                                        onChange={(e) => updateEducationField(idx, 'degree', e.target.value)}
                                                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                    />
                                                                                </Field>
                                                                                <Field label="Year">
                                                                                    <input
                                                                                        value={String(edu?.year ?? '')}
                                                                                        onChange={(e) => updateEducationField(idx, 'year', e.target.value)}
                                                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                    />
                                                                                </Field>
                                                                            </div>
                                                                            <div className="mt-2">
                                                                                <Field label="Institution">
                                                                                    <input
                                                                                        value={String(edu?.institution ?? '')}
                                                                                        onChange={(e) => updateEducationField(idx, 'institution', e.target.value)}
                                                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                    />
                                                                                </Field>
                                                                                <div className="mt-2">
                                                                                    <Field label="GPA">
                                                                                        <input
                                                                                            value={String(edu?.gpa ?? '')}
                                                                                            onChange={(e) => updateEducationField(idx, 'gpa', e.target.value)}
                                                                                            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                        />
                                                                                    </Field>
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );

                                                    blocks.projects = (
                                                        <div>
                                                            <div className="flex items-center justify-between border-b border-gray-200 pb-1">
                                                                <div className="text-sm font-bold text-blue-700">{getSectionLabel('projects', 'Projects')}</div>
                                                                <div className="flex items-center gap-3">
                                                                    {projectsList.length > 0 && (
                                                                        <button
                                                                            type="button"
                                                                            className="text-xs text-gray-600 hover:text-gray-800"
                                                                            onClick={() => {
                                                                                if (showAllProjectDescriptions) {
                                                                                    setShowAllProjectDescriptions(false);
                                                                                    setEditingProjectIndex(null);
                                                                                    return;
                                                                                }
                                                                                if (editingProjectIndex !== null) {
                                                                                    setEditingProjectIndex(null);
                                                                                    return;
                                                                                }
                                                                                setShowAllProjectDescriptions(true);
                                                                            }}
                                                                        >
                                                                            {showAllProjectDescriptions
                                                                                ? 'Collapse all'
                                                                                : (editingProjectIndex !== null ? 'Collapse' : 'Expand all')}
                                                                        </button>
                                                                    )}
                                                                    <button
                                                                        type="button"
                                                                        className="text-xs text-indigo-700 hover:text-indigo-800"
                                                                        onClick={addProjectItem}
                                                                    >
                                                                        Add
                                                                    </button>
                                                                </div>
                                                            </div>
                                                            {projectsList.length === 0 ? (
                                                                <div className="mt-2 text-sm text-gray-500">No projects yet.</div>
                                                            ) : (
                                                                <div className="mt-2 space-y-2">
                                                                    {projectsList.map((proj: any, idx: number) => (
                                                                        (() => {
                                                                            const title = String(proj?.title ?? 'Project');
                                                                            const technologies = String(proj?.technologies ?? '').trim();
                                                                            const link = String(proj?.link ?? '').trim();
                                                                            const isOpen = showAllProjectDescriptions || editingProjectIndex === idx;
                                                                            return (
                                                                                <div key={idx} className="rounded-xl border border-gray-200 overflow-hidden">
                                                                                    <button
                                                                                        type="button"
                                                                                        onClick={() => {
                                                                                            if (showAllProjectDescriptions) {
                                                                                                setShowAllProjectDescriptions(false);
                                                                                                setEditingProjectIndex(idx);
                                                                                                return;
                                                                                            }
                                                                                            setEditingProjectIndex(isOpen ? null : idx);
                                                                                        }}
                                                                                        className="w-full px-3 py-2 bg-gray-50 hover:bg-gray-100 text-left flex items-start justify-between gap-3"
                                                                                    >
                                                                                        <div className="min-w-0">
                                                                                            <div className="text-sm font-semibold text-gray-900 truncate">
                                                                                                {title}
                                                                                            </div>
                                                                                            <div className="text-xs text-gray-600 truncate">
                                                                                                {[technologies, link].filter(Boolean).join(' · ') || ' '}
                                                                                            </div>
                                                                                        </div>
                                                                                        <div className="text-xs text-indigo-700 shrink-0">
                                                                                            {showAllProjectDescriptions ? 'Editing' : (isOpen ? 'Hide' : 'Edit')}
                                                                                        </div>
                                                                                    </button>

                                                                                    {isOpen && (
                                                                                        <div className="p-3 bg-white">
                                                                                            <Field label="Title">
                                                                                                <input
                                                                                                    value={String(proj?.title ?? '')}
                                                                                                    onChange={(e) => updateProjectField(idx, 'title', e.target.value)}
                                                                                                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                                />
                                                                                            </Field>
                                                                                            <div className="mt-2">
                                                                                                <Field label="Technologies">
                                                                                                    <input
                                                                                                        value={String(proj?.technologies ?? '')}
                                                                                                        onChange={(e) => updateProjectField(idx, 'technologies', e.target.value)}
                                                                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                                    />
                                                                                                </Field>
                                                                                            </div>
                                                                                            <div className="mt-2">
                                                                                                <Field label="Link">
                                                                                                    <input
                                                                                                        value={String(proj?.link ?? '')}
                                                                                                        onChange={(e) => updateProjectField(idx, 'link', e.target.value)}
                                                                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                                    />
                                                                                                </Field>
                                                                                            </div>
                                                                                            <div className="mt-2">
                                                                                                <label className="block">
                                                                                                    <div className="flex items-center justify-between mb-1">
                                                                                                        <div className="text-xs font-semibold text-gray-700">Description</div>
                                                                                                        <button
                                                                                                            type="button"
                                                                                                            className={
                                                                                                                'text-xs inline-flex items-center px-2 py-1 rounded-md border ' +
                                                                                                                ((aiBusyProjects[idx] ?? false)
                                                                                                                    ? 'bg-gray-100 border-gray-200 text-gray-500 cursor-not-allowed'
                                                                                                                    : 'bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-50')
                                                                                                            }
                                                                                                            disabled={aiBusyProjects[idx] ?? false}
                                                                                                            onClick={async () => {
                                                                                                                try {
                                                                                                                    setAiBusyProjects((prev) => ({ ...(prev || {}), [idx]: true }));
                                                                                                                    const nextText = await aiRewriteResumeField({
                                                                                                                        field: 'project_description',
                                                                                                                        text: String(proj?.description ?? ''),
                                                                                                                        meta: {
                                                                                                                            title: String(proj?.title ?? ''),
                                                                                                                            technologies: String(proj?.technologies ?? ''),
                                                                                                                            link: String(proj?.link ?? ''),
                                                                                                                        },
                                                                                                                    });
                                                                                                                    updateProjectField(idx, 'description', nextText);
                                                                                                                } catch (e: any) {
                                                                                                                    setAiEditError(String(e?.message || 'AI edit failed.'));
                                                                                                                } finally {
                                                                                                                    setAiBusyProjects((prev) => ({ ...(prev || {}), [idx]: false }));
                                                                                                                }
                                                                                                            }}
                                                                                                        >
                                                                                                            {(aiBusyProjects[idx] ?? false) ? (
                                                                                                                'Rewriting…'
                                                                                                            ) : (
                                                                                                                <>
                                                                                                                    <Wand2 className="inline w-3 h-3 mr-1" />
                                                                                                                    Assist with AI
                                                                                                                </>
                                                                                                            )}
                                                                                                        </button>
                                                                                                    </div>
                                                                                                    <textarea
                                                                                                        rows={4}
                                                                                                        value={String(proj?.description ?? '')}
                                                                                                        onChange={(e) => updateProjectField(idx, 'description', e.target.value)}
                                                                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                                    />
                                                                                                </label>
                                                                                            </div>
                                                                                        </div>
                                                                                    )}
                                                                                </div>
                                                                            );
                                                                        })()
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );

                                                    blocks.certifications = (
                                                        <div>
                                                            <div className="flex items-center justify-between border-b border-gray-200 pb-1">
                                                                <div className="text-sm font-bold text-blue-700">{getSectionLabel('certifications', 'Certifications')}</div>
                                                                <button
                                                                    type="button"
                                                                    className="text-xs text-indigo-700 hover:text-indigo-800"
                                                                    onClick={addCertificationItem}
                                                                >
                                                                    Add
                                                                </button>
                                                            </div>
                                                            {certificationsList.length === 0 ? (
                                                                <div className="mt-2 text-sm text-gray-500">No certifications yet.</div>
                                                            ) : (
                                                                <div className="mt-2 space-y-2">
                                                                    {certificationsList.map((cert: any, idx: number) => (
                                                                        <div key={idx} className="rounded-xl border border-gray-200 p-3 bg-white">
                                                                            {typeof cert === 'string' ? (
                                                                                <Field label="Certification">
                                                                                    <input
                                                                                        value={String(cert ?? '')}
                                                                                        onChange={(e) => updateCertification(idx, e.target.value)}
                                                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                    />
                                                                                </Field>
                                                                            ) : (
                                                                                <>
                                                                                    <Field label="Name">
                                                                                        <input
                                                                                            value={String(cert?.name ?? '')}
                                                                                            onChange={(e) => updateCertification(idx, { name: e.target.value })}
                                                                                            className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                        />
                                                                                    </Field>
                                                                                    <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                                                        <Field label="Issuer">
                                                                                            <input
                                                                                                value={String(cert?.issuer ?? '')}
                                                                                                onChange={(e) => updateCertification(idx, { issuer: e.target.value })}
                                                                                                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                            />
                                                                                        </Field>
                                                                                        <Field label="Year">
                                                                                            <input
                                                                                                value={String(cert?.year ?? '')}
                                                                                                onChange={(e) => updateCertification(idx, { year: e.target.value })}
                                                                                                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                            />
                                                                                        </Field>
                                                                                    </div>
                                                                                </>
                                                                            )}
                                                                        </div>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );

                                                    if (customSectionsList.length > 0) {
                                                        customSectionsList.forEach((sec: any, sIdx: number) => {
                                                            const heading = String(sec?.heading || sec?.title || sec?.label || `Section ${sIdx + 1}`).trim();
                                                            const items = Array.isArray(sec?.items) ? sec.items : [];
                                                            const body = sec?.content ?? sec?.text ?? sec?.body ?? '';
                                                            blocks[`custom_${sIdx}`] = (
                                                                <div>
                                                                    <div className="text-sm font-bold text-blue-700 border-b border-gray-200 pb-1">{heading || 'Custom section'}</div>
                                                                    <div className="mt-2 rounded-xl border border-gray-200 p-3 bg-white">
                                                                        <Field label="Section name">
                                                                            <input
                                                                                value={String(sec?.heading ?? heading)}
                                                                                onChange={(e) => updateCustomSectionHeading(sIdx, e.target.value)}
                                                                                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                            />
                                                                        </Field>

                                                                        {items.length > 0 ? (
                                                                            <div className="mt-2 space-y-2">
                                                                                {items.map((it: any, iIdx: number) => (
                                                                                    <div key={iIdx} className="rounded-lg border border-gray-100 bg-gray-50 p-2">
                                                                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                                                                            <Field label="Title">
                                                                                                <input
                                                                                                    value={String(it?.title ?? '')}
                                                                                                    onChange={(e) => updateCustomSectionItem(sIdx, iIdx, 'title', e.target.value)}
                                                                                                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white"
                                                                                                />
                                                                                            </Field>
                                                                                            <Field label="Date">
                                                                                                <input
                                                                                                    value={String(it?.date ?? '')}
                                                                                                    onChange={(e) => updateCustomSectionItem(sIdx, iIdx, 'date', e.target.value)}
                                                                                                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white"
                                                                                                />
                                                                                            </Field>
                                                                                        </div>
                                                                                        <div className="mt-2">
                                                                                            <Field label="Subtitle">
                                                                                                <input
                                                                                                    value={String(it?.subtitle ?? '')}
                                                                                                    onChange={(e) => updateCustomSectionItem(sIdx, iIdx, 'subtitle', e.target.value)}
                                                                                                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white"
                                                                                                />
                                                                                            </Field>
                                                                                        </div>
                                                                                        <div className="mt-2">
                                                                                            <label className="block">
                                                                                                <div className="flex items-center justify-between mb-1">
                                                                                                    <div className="text-xs font-semibold text-gray-700">Content</div>
                                                                                                    <button
                                                                                                        type="button"
                                                                                                        className={
                                                                                                            'text-xs inline-flex items-center px-2 py-1 rounded-md border ' +
                                                                                                            ((aiBusyCustom[`custom_${sIdx}_item_${iIdx}`] ?? false)
                                                                                                                ? 'bg-gray-100 border-gray-200 text-gray-500 cursor-not-allowed'
                                                                                                                : 'bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-50')
                                                                                                        }
                                                                                                        disabled={aiBusyCustom[`custom_${sIdx}_item_${iIdx}`] ?? false}
                                                                                                        onClick={async () => {
                                                                                                            const k = `custom_${sIdx}_item_${iIdx}`;
                                                                                                            try {
                                                                                                                setAiBusyCustom((prev) => ({ ...(prev || {}), [k]: true }));
                                                                                                                const nextText = await aiRewriteResumeField({
                                                                                                                    field: 'custom_section',
                                                                                                                    text: String(it?.content ?? ''),
                                                                                                                    meta: {
                                                                                                                        heading,
                                                                                                                        item_title: String(it?.title ?? ''),
                                                                                                                        item_subtitle: String(it?.subtitle ?? ''),
                                                                                                                    },
                                                                                                                });
                                                                                                                updateCustomSectionItem(sIdx, iIdx, 'content', nextText);
                                                                                                            } catch (e: any) {
                                                                                                                setAiEditError(String(e?.message || 'AI edit failed.'));
                                                                                                            } finally {
                                                                                                                setAiBusyCustom((prev) => ({ ...(prev || {}), [k]: false }));
                                                                                                            }
                                                                                                        }}
                                                                                                    >
                                                                                                        {(aiBusyCustom[`custom_${sIdx}_item_${iIdx}`] ?? false) ? (
                                                                                                            'Rewriting…'
                                                                                                        ) : (
                                                                                                            <>
                                                                                                                <Wand2 className="inline w-3 h-3 mr-1" />
                                                                                                                Assist with AI
                                                                                                            </>
                                                                                                        )}
                                                                                                    </button>
                                                                                                </div>
                                                                                                <textarea
                                                                                                    rows={4}
                                                                                                    value={String(it?.content ?? '')}
                                                                                                    onChange={(e) => updateCustomSectionItem(sIdx, iIdx, 'content', e.target.value)}
                                                                                                    className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white"
                                                                                                />
                                                                                            </label>
                                                                                        </div>
                                                                                    </div>
                                                                                ))}
                                                                            </div>
                                                                        ) : (
                                                                            <div className="mt-2">
                                                                                <label className="block">
                                                                                    <div className="flex items-center justify-between mb-1">
                                                                                        <div className="text-xs font-semibold text-gray-700">Content</div>
                                                                                        <button
                                                                                            type="button"
                                                                                            className={
                                                                                                'text-xs inline-flex items-center px-2 py-1 rounded-md border ' +
                                                                                                ((aiBusyCustom[`custom_${sIdx}_body`] ?? false)
                                                                                                    ? 'bg-gray-100 border-gray-200 text-gray-500 cursor-not-allowed'
                                                                                                    : 'bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-50')
                                                                                            }
                                                                                            disabled={aiBusyCustom[`custom_${sIdx}_body`] ?? false}
                                                                                            onClick={async () => {
                                                                                                const k = `custom_${sIdx}_body`;
                                                                                                try {
                                                                                                    setAiBusyCustom((prev) => ({ ...(prev || {}), [k]: true }));
                                                                                                    const nextText = await aiRewriteResumeField({
                                                                                                        field: 'custom_section',
                                                                                                        text: String(body ?? ''),
                                                                                                        meta: { heading },
                                                                                                    });
                                                                                                    updateCustomSectionBody(sIdx, nextText);
                                                                                                } catch (e: any) {
                                                                                                    setAiEditError(String(e?.message || 'AI edit failed.'));
                                                                                                } finally {
                                                                                                    setAiBusyCustom((prev) => ({ ...(prev || {}), [k]: false }));
                                                                                                }
                                                                                            }}
                                                                                        >
                                                                                            {(aiBusyCustom[`custom_${sIdx}_body`] ?? false) ? (
                                                                                                'Rewriting…'
                                                                                            ) : (
                                                                                                <>
                                                                                                    <Wand2 className="inline w-3 h-3 mr-1" />
                                                                                                    Assist with AI
                                                                                                </>
                                                                                            )}
                                                                                        </button>
                                                                                    </div>
                                                                                    <textarea
                                                                                        rows={5}
                                                                                        value={String(body ?? '')}
                                                                                        onChange={(e) => updateCustomSectionBody(sIdx, e.target.value)}
                                                                                        className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                    />
                                                                                </label>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            );
                                                        });
                                                    } else {
                                                        blocks.custom_sections = (
                                                            <div>
                                                                <div className="flex items-center justify-between border-b border-gray-200 pb-1">
                                                                    <div className="text-sm font-bold text-blue-700">Custom sections</div>
                                                                    <button
                                                                        type="button"
                                                                        className="text-xs text-indigo-700 hover:text-indigo-800"
                                                                        onClick={addCustomSection}
                                                                    >
                                                                        Add
                                                                    </button>
                                                                </div>
                                                                <div className="mt-2 text-sm text-gray-500">No custom sections yet.</div>
                                                            </div>
                                                        );
                                                    }

                                                    if (experienceList.length > 0) {
                                                        blocks.experience = (
                                                            <div className="pt-1">
                                                                <div className="flex items-center justify-between border-b border-gray-200 pb-1">
                                                                    <div className="text-sm font-bold text-blue-700">{getSectionLabel('experience', 'Work history')} descriptions</div>
                                                                    <button
                                                                        type="button"
                                                                        className="text-xs text-gray-600 hover:text-gray-800"
                                                                        onClick={() => {
                                                                            if (showAllWorkHistoryDescriptions) {
                                                                                setShowAllWorkHistoryDescriptions(false);
                                                                                setEditingExperienceIndex(null);
                                                                                return;
                                                                            }
                                                                            if (editingExperienceIndex !== null) {
                                                                                setEditingExperienceIndex(null);
                                                                                return;
                                                                            }
                                                                            setShowAllWorkHistoryDescriptions(true);
                                                                        }}
                                                                    >
                                                                        {showAllWorkHistoryDescriptions
                                                                            ? 'Collapse all'
                                                                            : (editingExperienceIndex !== null ? 'Collapse' : 'Expand all')}
                                                                    </button>
                                                                </div>

                                                                <div className="mt-2 space-y-2">
                                                                    {experienceList.map((exp: any, idx: number) => {
                                                                        const title = String(exp?.title || exp?.position || exp?.role || 'Role');
                                                                        const company = String(exp?.company || exp?.organization || '');
                                                                        const dates = String(exp?.duration || exp?.dates || [exp?.start, exp?.end].filter(Boolean).join(' - ') || '');
                                                                        const isOpen = showAllWorkHistoryDescriptions || editingExperienceIndex === idx;
                                                                        return (
                                                                            <div key={idx} className="rounded-xl border border-gray-200 overflow-hidden">
                                                                                <button
                                                                                    type="button"
                                                                                    onClick={() => {
                                                                                        if (showAllWorkHistoryDescriptions) {
                                                                                            setShowAllWorkHistoryDescriptions(false);
                                                                                            setEditingExperienceIndex(idx);
                                                                                            return;
                                                                                        }
                                                                                        setEditingExperienceIndex(isOpen ? null : idx);
                                                                                    }}
                                                                                    className="w-full px-3 py-2 bg-gray-50 hover:bg-gray-100 text-left flex items-start justify-between gap-3"
                                                                                >
                                                                                    <div className="min-w-0">
                                                                                        <div className="text-sm font-semibold text-gray-900 truncate">
                                                                                            {title}
                                                                                        </div>
                                                                                        <div className="text-xs text-gray-600 truncate">
                                                                                            {[company, dates].filter(Boolean).join(' · ')}
                                                                                        </div>
                                                                                    </div>
                                                                                    <div className="text-xs text-indigo-700 shrink-0">
                                                                                        {showAllWorkHistoryDescriptions ? 'Editing' : (isOpen ? 'Hide' : 'Edit')}
                                                                                    </div>
                                                                                </button>
                                                                                {isOpen && (
                                                                                    <div className="p-3 bg-white">
                                                                                        <label className="block">
                                                                                            <div className="flex items-center justify-between mb-1">
                                                                                                <div className="text-xs font-semibold text-gray-700">Description / bullets</div>
                                                                                                <button
                                                                                                    type="button"
                                                                                                    className={
                                                                                                        'text-xs inline-flex items-center px-2 py-1 rounded-md border ' +
                                                                                                        ((aiBusyExperience[idx] ?? false)
                                                                                                            ? 'bg-gray-100 border-gray-200 text-gray-500 cursor-not-allowed'
                                                                                                            : 'bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-50')
                                                                                                    }
                                                                                                    disabled={aiBusyExperience[idx] ?? false}
                                                                                                    onClick={async () => {
                                                                                                        try {
                                                                                                            setAiBusyExperience((prev) => ({ ...(prev || {}), [idx]: true }));
                                                                                                            const nextText = await aiRewriteResumeField({
                                                                                                                field: 'experience_description',
                                                                                                                text: String(exp?.description ?? ''),
                                                                                                                meta: {
                                                                                                                    title,
                                                                                                                    company,
                                                                                                                    dates,
                                                                                                                },
                                                                                                            });
                                                                                                            updateExperienceDescription(idx, nextText);
                                                                                                        } catch (e: any) {
                                                                                                            setAiEditError(String(e?.message || 'AI edit failed.'));
                                                                                                        } finally {
                                                                                                            setAiBusyExperience((prev) => ({ ...(prev || {}), [idx]: false }));
                                                                                                        }
                                                                                                    }}
                                                                                                >
                                                                                                    {(aiBusyExperience[idx] ?? false) ? (
                                                                                                        'Rewriting…'
                                                                                                    ) : (
                                                                                                        <>
                                                                                                            <Wand2 className="inline w-3 h-3 mr-1" />
                                                                                                            Assist with AI
                                                                                                        </>
                                                                                                    )}
                                                                                                </button>
                                                                                            </div>
                                                                                            <textarea
                                                                                                rows={6}
                                                                                                value={String(exp?.description ?? '')}
                                                                                                onChange={(e) => updateExperienceDescription(idx, e.target.value)}
                                                                                                placeholder={"Use bullets like:\n- Did X\n- Improved Y\n- Shipped Z"}
                                                                                                className="w-full px-3 py-2 rounded-lg border border-gray-200 text-sm"
                                                                                            />
                                                                                        </label>
                                                                                        <div className="mt-2 text-xs text-gray-500">
                                                                                            Tip: start lines with “- ” to render bullets.
                                                                                        </div>
                                                                                    </div>
                                                                                )}
                                                                            </div>
                                                                        );
                                                                    })}
                                                                </div>
                                                            </div>
                                                        );
                                                    }

                                                    const presentKeys = Object.keys(blocks).filter((k) => Boolean(blocks[k]));

                                                    const defaultOrder: string[] = [
                                                        'summary',
                                                        'experience',
                                                        ...(customSectionsList.length > 0
                                                            ? customSectionsList.map((_: any, i: number) => `custom_${i}`)
                                                            : ['custom_sections']),
                                                        'education',
                                                        'projects',
                                                        'certifications',
                                                        'skills',
                                                        'languages',
                                                    ];

                                                    const rawBase = (Array.isArray(sectionOrder) && sectionOrder.length > 0) ? sectionOrder : defaultOrder;
                                                    const base = (() => {
                                                        if (!blocks.custom_sections) return rawBase;
                                                        if (rawBase.includes('custom_sections')) return rawBase;
                                                        const expIdx = rawBase.indexOf('experience');
                                                        if (expIdx >= 0) {
                                                            return [...rawBase.slice(0, expIdx + 1), 'custom_sections', ...rawBase.slice(expIdx + 1)];
                                                        }
                                                        return [...rawBase, 'custom_sections'];
                                                    })();
                                                    const orderedKeys = [
                                                        ...base,
                                                        ...presentKeys.filter((k) => !base.includes(k)),
                                                    ].filter((k) => Boolean(blocks[k]) && !hidden.has(String(k)));

                                                    if (orderedKeys.length === 0) return null;

                                                    return (
                                                        <div className="divide-y divide-gray-200">
                                                            {orderedKeys.map((k) => (
                                                                <div key={k} className="py-3 first:pt-0">
                                                                    {blocks[k]}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    );
                                                })()}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* PDF view */}
                        <div className="min-w-0">
                            {mobilePreviewOpen && (
                                <div
                                    className="fixed inset-0 z-50 bg-gray-900/50 sm:hidden"
                                    onClick={() => setMobilePreviewOpen(false)}
                                    aria-hidden="true"
                                />
                            )}

                            <div className={mobilePreviewOpen ? 'fixed inset-0 z-[60] bg-gray-50 sm:static sm:z-auto sm:bg-transparent flex flex-col' : ''}>
                                {mobilePreviewOpen && (
                                    <div className="sm:hidden px-3 pt-3">
                                        <div className="bg-white border border-gray-200 rounded-xl px-3 py-2 flex items-center justify-between gap-2 shadow-sm">
                                            <div className="text-sm font-semibold text-gray-900">Full screen mode</div>
                                            <button
                                                type="button"
                                                className="px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-900 text-sm font-semibold"
                                                onClick={() => setMobilePreviewOpen(false)}
                                            >
                                                Close
                                            </button>
                                        </div>
                                        {inlineEditMode && (
                                            <div className="mt-2 text-xs text-gray-600">
                                                Click/Tap on any text to edit
                                            </div>
                                        )}
                                    </div>
                                )}

                                <div className={mobilePreviewOpen ? 'flex-1 min-h-0 px-3 pb-3 pt-2 sm:p-0' : ''}>
                                    {!isEmbed && !mobilePreviewOpen && (
                                        <div className="sm:hidden mb-2 flex items-center justify-between gap-2">
                                            <div className="min-w-0">
                                                {inlineEditMode && (
                                                    <div className="text-xs text-gray-600">Click/Tap on any text to edit</div>
                                                )}
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => setMobilePreviewOpen(true)}
                                                className="shrink-0 px-3 py-2 rounded-lg bg-white border border-gray-200 text-gray-800 hover:bg-gray-50 transition-colors"
                                            >
                                                Full screen
                                            </button>
                                        </div>
                                    )}
                                    <div
                                        ref={pdfPreviewContainerRef}
                                        className={`${isEmbed ? 'bg-transparent p-0 rounded-none overflow-hidden' : 'bg-gray-100 rounded-lg p-4'} ${mobilePreviewOpen ? 'h-full overflow-auto' : (!isEmbed ? 'overflow-x-auto' : '')}`}
                                    >
                                        {/* Hidden measurement render (used to compute pages + capture HTML snapshot) */}
                                        <div style={{ position: 'fixed', left: '-100000px', top: 0, width: '816px', visibility: 'hidden' }}>
                                            <div className="pdfPreviewPage">
                                                <div className="pdfPreviewTarget">
                                                    <div className="pdfPreviewViewport">
                                                        <div
                                                            ref={pdfPreviewMeasureInnerRef}
                                                            className="tv-style-root"
                                                            style={{
                                                                // @ts-ignore
                                                                ['--tv-paragraph-gap']: `${styleSettings.paragraphGapPx}px`,
                                                                // @ts-ignore
                                                                ['--tv-font-scale']: String(styleSettings.fontScale),
                                                                // @ts-ignore
                                                                ['--tv-space-scale']: String(styleSettings.spacingScale),
                                                            }}
                                                        >
                                                            <TemplateComponent
                                                                content={content}
                                                                editMode={false}
                                                                sectionOrder={sectionOrder}
                                                                onSectionOrderChange={setSectionOrder}
                                                                hiddenSectionKeys={hiddenSectionKeys}
                                                                onHiddenSectionKeysChange={setHiddenSectionKeys}
                                                            />
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {(() => {
                                            const PAGE_W = 816;
                                            const twoUpGapPx = 24;
                                            const pagesForLayout = inlineEditMode ? 1 : pdfPreviewPages;
                                            const totalW = pagesForLayout === 2 ? ((PAGE_W * 2) + twoUpGapPx) : PAGE_W;
                                            const scaledW = Math.max(1, Math.ceil(totalW * pdfPreviewPageScale));
                                            return (
                                                <div style={{ width: `${scaledW}px`, margin: '0 auto' }}>
                                                    {inlineEditMode ? (
                                                        <div className="mb-3 rounded-xl border border-gray-200 bg-white px-3 py-2 sm:px-4 sm:py-3">
                                                            <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-3">

                                                                <div className="text-xs sm:text-sm text-gray-600 flex flex-col gap-1 leading-snug">
                                                                    <div className="break-words">Click/Tap any content to edit.</div>
                                                                    <div className="flex items-start gap-2">
                                                                        <Grip className="w-4 h-4 text-gray-500 shrink-0 mt-0.5" />
                                                                        <span className="break-words">Drag sections using the handle on the left of each section. Drop on the right to delete.</span>
                                                                    </div>
                                                                    <div className="flex items-start gap-2 flex-wrap">
                                                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] sm:text-xs rounded bg-orange-200 text-black border border-orange-300">
                                                                            <Wand2 className="w-3 h-3" />
                                                                            <span>Assist with AI</span>
                                                                        </span>
                                                                        <span className="break-words">On the left sidebar, editing and AI rewriting are also available.</span>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ) : null}
                                                    <div
                                                        style={isEmbed
                                                            ? ({ zoom: pdfPreviewPageScale } as any)
                                                            : ({ transform: `scale(${pdfPreviewPageScale})`, transformOrigin: 'top left' })}
                                                    >
                                                        {inlineEditMode ? (
                                                            // Edit mode: render a continuous scroll canvas (no page slicing).
                                                            <div className="pdfPreviewPage pdfPreviewPageContinuous">
                                                                <div className="pdfPreviewTarget pdfPreviewTargetContinuous">
                                                                    <div
                                                                        style={{
                                                                            transform: `scale(${pdfPreviewContentScale})`,
                                                                            transformOrigin: 'top left',
                                                                        }}
                                                                    >
                                                                        <div
                                                                            className="tv-style-root"
                                                                            data-tv-preview="true"
                                                                            style={{
                                                                                // @ts-ignore
                                                                                ['--tv-paragraph-gap']: `${styleSettings.paragraphGapPx}px`,
                                                                                // @ts-ignore
                                                                                ['--tv-font-scale']: String(styleSettings.fontScale),
                                                                                // @ts-ignore
                                                                                ['--tv-space-scale']: String(styleSettings.spacingScale),
                                                                            }}
                                                                        >
                                                                            <TemplateComponent
                                                                                content={content}
                                                                                editMode={inlineEditMode}
                                                                                sectionOrder={sectionOrder}
                                                                                onSectionOrderChange={setSectionOrder}
                                                                                hiddenSectionKeys={hiddenSectionKeys}
                                                                                onHiddenSectionKeysChange={setHiddenSectionKeys}
                                                                                onContentChange={(changes: any) => setInlineEditChanges((prev: any) => ({ ...prev, ...changes }))}
                                                                            />
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        ) : (
                                                            // View mode: paged preview (with optional snapshot windowing).
                                                            <div className={pdfPreviewPages === 2 ? 'grid grid-cols-[816px_816px] gap-6 items-start' : 'space-y-6'}>
                                                                {Array.from({ length: pdfPreviewPages }).map((_, idx) => (
                                                                    <div key={idx} className={isEmbed ? '' : 'space-y-8'}>
                                                                        {!isEmbed && (
                                                                            <div className="inline-flex items-center gap-3 w-full">
                                                                                <div
                                                                                    className={
                                                                                        'inline-flex items-center rounded-full bg-white text-gray-700 ring-1 ring-gray-200 font-semibold ' +
                                                                                        (pdfPreviewPages === 2 ? 'px-6 py-3 text-3xl' : 'px-4 py-2 text-lg')
                                                                                    }
                                                                                >
                                                                                    Page {idx + 1}{pdfPreviewPages > 1 ? ` of ${pdfPreviewPages}` : ''}
                                                                                </div>
                                                                                <div className="h-px flex-1 bg-gray-300/80" />
                                                                            </div>
                                                                        )}
                                                                        <div
                                                                            className={
                                                                                `pdfPreviewPage` +
                                                                                `${pdfPreviewPages === 2 ? ' pdfPreviewPageTwoUp' : ''}` +
                                                                                `${idx === pdfPreviewPages - 1 ? ' pdfPreviewPageLast' : ''}`
                                                                            }
                                                                            style={{
                                                                                // Shrink only the last page frame to the remaining content height
                                                                                // (removes trailing bottom edge/shadow line at end-of-document)
                                                                                // @ts-ignore
                                                                                ['--pdf-page-h']: `${(idx === pdfPreviewPages - 1 && pdfPreviewPages !== 2) ? pdfPreviewLastPageHeightPx : 1138}px`,
                                                                            }}
                                                                        >
                                                                            <div className="pdfPreviewTarget">
                                                                                <div className="pdfPreviewViewport">
                                                                                    {(() => {
                                                                                        // Keep stride equal to the viewport height.
                                                                                        // (The viewport is fixed at Letter height; padding is outside it.)
                                                                                        const VIEW_H = 1056;
                                                                                        // Avoid 1px overlap at page boundaries (can duplicate the last line on the next page)
                                                                                        // due to rounding/subpixel rasterization.
                                                                                        const y = (idx * VIEW_H) + (idx > 0 ? 1 : 0);
                                                                                        return !pdfPreviewSnapshotHtml ? (
                                                                                            <div
                                                                                                style={{
                                                                                                    transform: `translateY(-${y}px) scale(${pdfPreviewContentScale})`,
                                                                                                    transformOrigin: 'top left',
                                                                                                }}
                                                                                            >
                                                                                                <div
                                                                                                    className="tv-style-root"
                                                                                                    style={{
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-paragraph-gap']: `${styleSettings.paragraphGapPx}px`,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-font-scale']: String(styleSettings.fontScale),
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-space-scale']: String(styleSettings.spacingScale),
                                                                                                    }}
                                                                                                >
                                                                                                    <TemplateComponent
                                                                                                        content={content}
                                                                                                        editMode={false}
                                                                                                        sectionOrder={sectionOrder}
                                                                                                        onSectionOrderChange={setSectionOrder}
                                                                                                        hiddenSectionKeys={hiddenSectionKeys}
                                                                                                        onHiddenSectionKeysChange={setHiddenSectionKeys}
                                                                                                    />
                                                                                                </div>
                                                                                            </div>
                                                                                        ) : (
                                                                                            <div
                                                                                                style={{
                                                                                                    transform: `translateY(-${y}px) scale(${pdfPreviewContentScale})`,
                                                                                                    transformOrigin: 'top left',
                                                                                                }}
                                                                                                // eslint-disable-next-line react/no-danger
                                                                                                dangerouslySetInnerHTML={{ __html: pdfPreviewSnapshotHtml }}
                                                                                            />
                                                                                        );
                                                                                    })()}
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            );
                                        })()}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {!isEmbed && downloadFeedbackOpen && (
                    <div
                        className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 p-4"
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="downloadFeedbackTitle"
                        onClick={(e) => {
                            if (e.target === e.currentTarget && !downloadFeedbackSubmitting) closeDownloadFeedbackModal();
                        }}
                    >
                        <div className="bg-white w-full max-w-md rounded-2xl shadow-2xl overflow-hidden">
                            <div className="flex items-center justify-between px-5 py-4 border-b">
                                <h3 id="downloadFeedbackTitle" className="font-semibold text-lg text-gray-800">How was your resume?</h3>
                                <button
                                    type="button"
                                    className="text-gray-500 hover:text-gray-800"
                                    aria-label="Close"
                                    onClick={closeDownloadFeedbackModal}
                                    disabled={downloadFeedbackSubmitting}
                                >
                                    ×
                                </button>
                            </div>

                            <div className="p-5 space-y-4">
                                <p className="text-sm text-gray-600">Your feedback helps us improve ResumaticAI.</p>

                                <div className="space-y-2">
                                    <div className="text-sm font-medium text-gray-800">Overall, how satisfied are you?</div>
                                    <div className="flex items-center gap-1" aria-label="Rating">
                                        {[1, 2, 3, 4, 5].map((val) => {
                                            const active = (downloadFeedbackHoverRating || downloadFeedbackRating) >= val;
                                            return (
                                                <button
                                                    key={val}
                                                    type="button"
                                                    className={(active ? 'text-amber-400' : 'text-gray-300') + ' text-xl leading-none'}
                                                    onClick={() => setDownloadFeedbackRating(val)}
                                                    onMouseEnter={() => setDownloadFeedbackHoverRating(val)}
                                                    onMouseLeave={() => setDownloadFeedbackHoverRating(0)}
                                                    disabled={downloadFeedbackSubmitting}
                                                    aria-label={`${val} star${val === 1 ? '' : 's'}`}
                                                >
                                                    ★
                                                </button>
                                            );
                                        })}
                                    </div>
                                    <div className="text-xs text-gray-500 h-4">
                                        {(() => {
                                            const n = downloadFeedbackHoverRating || downloadFeedbackRating;
                                            const map: Record<number, string> = {
                                                1: 'Very dissatisfied',
                                                2: 'Dissatisfied',
                                                3: 'Neutral',
                                                4: 'Satisfied',
                                                5: 'Very satisfied',
                                            };
                                            return map[n] || '';
                                        })()}
                                    </div>

                                    <div className="mt-3 space-y-2">
                                        <div className="text-sm font-medium text-gray-800">Compared to your original resume, this is:</div>
                                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                                            {([
                                                { value: 'improved', label: 'Improved' },
                                                { value: 'same', label: 'About the same' },
                                                { value: 'worse', label: 'Worse' },
                                            ] as const).map((opt) => {
                                                const selected = downloadFeedbackComparison === opt.value;
                                                return (
                                                    <button
                                                        key={opt.value}
                                                        type="button"
                                                        className={
                                                            'inline-flex items-center justify-center gap-2 cursor-pointer border rounded-full px-3 py-1 text-sm transition-colors ' +
                                                            (selected
                                                                ? 'bg-blue-50 border-blue-300 text-blue-800'
                                                                : 'border-gray-300 text-gray-700 hover:bg-gray-50')
                                                        }
                                                        onClick={() => setDownloadFeedbackComparison((prev) => (prev === opt.value ? '' : opt.value))}
                                                        aria-pressed={selected}
                                                        disabled={downloadFeedbackSubmitting}
                                                    >
                                                        {opt.label}
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </div>

                                <div>
                                    <label htmlFor="downloadFeedbackComment" className="block text-sm font-medium text-gray-800 mb-1">Anything we could improve?</label>
                                    <textarea
                                        id="downloadFeedbackComment"
                                        className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        placeholder="Optional"
                                        value={downloadFeedbackComment}
                                        onChange={(e) => setDownloadFeedbackComment(e.target.value)}
                                        disabled={downloadFeedbackSubmitting}
                                    />
                                </div>
                            </div>

                            <div className="px-5 py-4 border-t flex items-center justify-end gap-2">
                                <button
                                    type="button"
                                    className="px-4 py-2 text-gray-700 hover:text-gray-900"
                                    onClick={closeDownloadFeedbackModal}
                                    disabled={downloadFeedbackSubmitting}
                                >
                                    Maybe later
                                </button>
                                <button
                                    type="button"
                                    className={
                                        'px-4 py-2 rounded-md text-white ' +
                                        (downloadFeedbackSubmitting ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700')
                                    }
                                    onClick={submitDownloadFeedback}
                                    disabled={downloadFeedbackSubmitting}
                                >
                                    Send feedback
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <label className="block">
            <div className="text-xs font-semibold text-gray-700 mb-1">{label}</div>
            {children}
        </label>
    );
}

function ListField({
    label,
    hint,
    values,
    onChange,
}: {
    label: string;
    hint?: string;
    values: string[];
    onChange: (vals: string[]) => void;
}) {
    const [draft, setDraft] = React.useState('');
    return (
        <div>
            <div className="flex items-center justify-between border-b border-gray-200 pb-1">
                <div className="flex items-baseline gap-2 min-w-0">
                    <div className="text-sm font-bold text-blue-700 truncate">{label}</div>
                    {hint ? <div className="text-xs font-normal text-gray-500 whitespace-nowrap">{hint}</div> : null}
                </div>
                <button
                    type="button"
                    className="text-xs text-indigo-700 hover:text-indigo-800"
                    onClick={() => {
                        const v = draft.trim();
                        if (!v) return;
                        onChange([...(values || []), v]);
                        setDraft('');
                    }}
                >
                    Add
                </button>
            </div>
            <div className="flex gap-2">
                <input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder={`Add ${label.toLowerCase()}…`}
                    className="flex-1 px-3 py-2 rounded-lg border border-gray-200 text-sm"
                />
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
                {(values || []).map((v, idx) => (
                    <span
                        key={`${v}-${idx}`}
                        className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-gray-100 border border-gray-200 text-sm text-gray-800"
                    >
                        {v}
                        <button
                            type="button"
                            className="text-gray-500 hover:text-gray-800"
                            onClick={() => onChange(values.filter((_, i) => i !== idx))}
                            aria-label={`Remove ${v}`}
                        >
                            ×
                        </button>
                    </span>
                ))}
            </div>
        </div>
    );
}

