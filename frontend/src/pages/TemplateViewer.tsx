import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useLocation, useParams } from 'react-router-dom';
import ProfessionalTemplate from '../components/templates/ProfessionalTemplate';
import ExecutiveTemplate from '../components/templates/ExecutiveTemplate';
import Creative2Template from '../components/templates/Creative2Template';
import ClassicRoseTemplate from '../components/templates/ClassicRoseTemplate';
import BoldProfessionalTemplate from '../components/templates/BoldProfessionalTemplate';
import ContemporaryTemplate from '../components/templates/ContemporaryTemplate';
import ModernTemplate from '../components/templates/ModernTemplate';
import StylishTemplate from '../components/templates/StylishTemplate';
import { TemplateAiAssistProvider } from '../components/templates/EditableSection';
import { Type, AlignLeft, Rows, RotateCcw, Lightbulb, Edit3, Grip, Wand2, Sparkles, AlertTriangle, Languages } from 'lucide-react';
import { mixWithBlack, mixWithWhite, normalizeHexColor } from '../utils/accentColor';
import {
    PREVIEW_TRANSLATE_NONE_VALUE,
    PREVIEW_TRANSLATE_OPTIONS,
    PREVIEW_TRANSLATE_RESET_TO_ENGLISH_VALUE,
} from '../constants/previewTranslateLanguages';

type TemplateViewerStyleSettings = {
    fontScale: number;
    paragraphGapPx: number;
    spacingScale: number;
};

type TemplateViewerLayoutSettings = {
    sectionOrderByTemplate: Record<string, string[]>;
    hiddenSectionKeysByTemplate: Record<string, string[]>;
};

const DEFAULT_TEMPLATE_VIEWER_STYLE_SETTINGS: TemplateViewerStyleSettings = {
    fontScale: 1,
    paragraphGapPx: 0,
    spacingScale: 1,
};

const PROFESSIONAL_BACKGROUND_TONES: Array<{ name: string; value: string }> = [
    { name: 'Soft Slate', value: '#B4C5DD' },
    { name: 'Mist Gray', value: '#D2D4D9' },
    { name: 'Warm Stone', value: '#cbbcae' },
    { name: 'Steel Mist', value: '#A8B7CF' },
    { name: 'Sage Mist', value: '#b9c8bc' },
    { name: 'Powder Blue', value: '#B6D7F2' },
    { name: 'Cloud Lilac', value: '#c7bbcf' },
];

function clampNumber(value: any, lo: number, hi: number, fallback: number): number {
    const n = Number(value);
    if (!Number.isFinite(n)) return fallback;
    return Math.min(hi, Math.max(lo, n));
}

function normalizeTemplateViewerStyleSettings(raw: any): TemplateViewerStyleSettings | null {
    if (!raw || typeof raw !== 'object') return null;
    const fontScale = clampNumber(raw.fontScale, 0.6, 1.4, DEFAULT_TEMPLATE_VIEWER_STYLE_SETTINGS.fontScale);
    const paragraphGapPx = clampNumber(raw.paragraphGapPx, -40, 200, DEFAULT_TEMPLATE_VIEWER_STYLE_SETTINGS.paragraphGapPx);
    const spacingScale = clampNumber(raw.spacingScale, 0, 5, DEFAULT_TEMPLATE_VIEWER_STYLE_SETTINGS.spacingScale);
    return { fontScale, paragraphGapPx, spacingScale };
}

function withTemplateViewerStyleSettings(resume: any, settings: TemplateViewerStyleSettings): any {
    if (!resume || typeof resume !== 'object') return resume;
    const baseStyle = (resume.style && typeof resume.style === 'object') ? resume.style : {};
    return {
        ...(resume || {}),
        style: {
            ...(baseStyle || {}),
            templateViewerSettings: {
                fontScale: settings.fontScale,
                paragraphGapPx: settings.paragraphGapPx,
                spacingScale: settings.spacingScale,
            },
        },
    };
}

function normalizeTemplateViewerLayoutSettings(raw: any): TemplateViewerLayoutSettings | null {
    if (!raw || typeof raw !== 'object') return null;

    const normalizeMap = (v: any): Record<string, string[]> => {
        if (!v || typeof v !== 'object') return {};
        const out: Record<string, string[]> = {};
        for (const [k, arr] of Object.entries(v)) {
            const key = String(k || '');
            if (!key) continue;
            const list = Array.isArray(arr) ? (arr as any[]).map((x) => String(x)).filter(Boolean) : [];
            out[key] = list;
        }
        return out;
    };

    return {
        sectionOrderByTemplate: normalizeMap((raw as any).sectionOrderByTemplate),
        hiddenSectionKeysByTemplate: normalizeMap((raw as any).hiddenSectionKeysByTemplate),
    };
}

function withTemplateViewerLayoutPatch(
    resume: any,
    templateKeyRaw: any,
    patch: { sectionOrder?: string[]; hiddenSectionKeys?: string[] }
): any {
    if (!resume || typeof resume !== 'object') return resume;

    const templateKey = String(templateKeyRaw || '');
    if (!templateKey) return resume;

    const baseStyle = (resume.style && typeof resume.style === 'object') ? resume.style : {};
    const baseLayout = (baseStyle as any).templateViewerLayout;
    const normalizedBase = normalizeTemplateViewerLayoutSettings(baseLayout) || {
        sectionOrderByTemplate: {},
        hiddenSectionKeysByTemplate: {},
    };

    const nextSectionOrderByTemplate = {
        ...(normalizedBase.sectionOrderByTemplate || {}),
    };
    const nextHiddenSectionKeysByTemplate = {
        ...(normalizedBase.hiddenSectionKeysByTemplate || {}),
    };

    if ('sectionOrder' in patch) {
        nextSectionOrderByTemplate[templateKey] = Array.isArray(patch.sectionOrder)
            ? patch.sectionOrder.map((x) => String(x)).filter(Boolean)
            : [];
    }
    if ('hiddenSectionKeys' in patch) {
        nextHiddenSectionKeysByTemplate[templateKey] = Array.isArray(patch.hiddenSectionKeys)
            ? patch.hiddenSectionKeys.map((x) => String(x)).filter(Boolean)
            : [];
    }

    return {
        ...(resume || {}),
        style: {
            ...(baseStyle || {}),
            templateViewerLayout: {
                sectionOrderByTemplate: nextSectionOrderByTemplate,
                hiddenSectionKeysByTemplate: nextHiddenSectionKeysByTemplate,
            },
        },
    };
}

const TEMPLATE_DISPLAY_NAMES: Record<string, string> = {
    classicrose: 'Classic',
    classic_rose: 'Classic',
    minimalsidebar: 'Stylish',
    minimal_sidebar: 'Stylish',
    creative2: 'Creative',
    creative_2: 'Creative',
    traditional: 'Contemporary',
    bluelineclassic: 'Contemporary',
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
        case 'classic':
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
        case 'contemporary':
            return 12;

        case 'modern':
        case 'cleansidebar':
            return 18;

        case 'minimalsidebar':
        case 'stylish':
            return 10;

        default:
            return null;
    }
}

export default function TemplateViewer() {
    const { templateName } = useParams<{ templateName: string }>();
    const location = useLocation();
    const isDownloadOnly = location.pathname.includes('/template-download/');

    const templateKey = String(templateName || '').trim().toLowerCase();

    // Debug helper: when enabled, make PDF outputs draw a visible top-edge marker so we can
    // distinguish real layout whitespace from the PDF viewer's page border.
    const pdfDebugEnabled = (() => {
        try {
            const params = new URLSearchParams(location.search || '');
            return params.get('pdfdebug') === '1';
        } catch {
            return false;
        }
    })();

    const templateDisplayName = formatTemplateDisplayName(templateName);

    const qs = new URLSearchParams(location.search || '');
    const returnTo = String(qs.get('return') || '').trim();
    const editParam = String(qs.get('edit') || '').trim().toLowerCase();
    const ridParam = String(qs.get('rid') || '').trim();
    const embedParam = String(qs.get('embed') || '').trim().toLowerCase();
    const isEmbed = embedParam === '1' || embedParam === 'true';
    const thumbParam = String(qs.get('thumb') || '').trim().toLowerCase();
    const isThumbnail = thumbParam === '1' || thumbParam === 'true';
    const allowTranslateParam = String(qs.get('allowTranslate') || '').trim().toLowerCase();
    const allowEmbedTranslate = allowTranslateParam === '1' || allowTranslateParam === 'true';
    const embedFlushParam = String(qs.get('flush') || '').trim().toLowerCase();
    const isEmbedFlush = embedFlushParam === '1' || embedFlushParam === 'true';
    const firstPageOnlyParam = String(qs.get('firstpage') || '').trim().toLowerCase();
    /** Plans-page iframe: show only page 1 and scale as a single page (no multi-page stack). */
    const embedFirstPageOnly = isEmbed && (firstPageOnlyParam === '1' || firstPageOnlyParam === 'true');

    /** Optional zoom for embedded previews (e.g. create-resume pane). Default 1; capped for safety. */
    const embedZoomRaw = String(qs.get('embedZoom') || '').trim();
    const embedZoomMultiplier = React.useMemo(() => {
        if (!isEmbed) return 1;
        const n = parseFloat(embedZoomRaw);
        if (!Number.isFinite(n) || n <= 0) return 1;
        return Math.min(1.85, Math.max(1, n));
    }, [isEmbed, embedZoomRaw]);

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

            // Always allow vertical scrolling in embed mode.
            // Some layouts (notably scaled PDF previews) can temporarily confuse scrollHeight measurements;
            // forcing overflowY=auto prevents accidental clipping where only the top of the page is visible.
            root.style.overflowY = 'auto';
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
    const [redirectingToPlans, setRedirectingToPlans] = useState(false);
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
    const [accentColor, setAccentColor] = useState<string>('');
    const [primaryColor, setPrimaryColor] = useState<string>('');
    const [secondaryColor, setSecondaryColor] = useState<string>('');
    const accentInitRef = useRef(false);
    const primaryInitRef = useRef(false);
    const secondaryInitRef = useRef(false);
    const accentSaveTimerRef = useRef<number | null>(null);
    const [pdfPreviewPageScale, setPdfPreviewPageScale] = useState(1);
    const [pdfPreviewContentScale, setPdfPreviewContentScale] = useState(1);
    const [pdfPreviewPages, setPdfPreviewPages] = useState(1);
    const [pdfPreviewLastPageHeightPx, setPdfPreviewLastPageHeightPx] = useState(1064);
    const [pdfPreviewSnapshotHtml, setPdfPreviewSnapshotHtml] = useState<string>('');
    const embedRootRef = useRef<HTMLDivElement | null>(null);
    const pdfPreviewContainerRef = useRef<HTMLDivElement | null>(null);
    const pdfPreviewMeasureInnerRef = useRef<HTMLDivElement | null>(null);
    const autoDownloadTriggeredRef = useRef(false);
    const editAutoAppliedRef = useRef(false);

    useEffect(() => {
        const root = embedRootRef.current;
        if (!root) return;

        const resumeSelector = '.pdfPreviewPage, .pdfPreviewTarget, .pdfPreviewViewport, .tv-style-root';

        const targetInResume = (target: EventTarget | null) => {
            if (!(target instanceof Node)) return false;
            const el = target instanceof Element ? target : target.parentElement;
            if (!el || !root.contains(el)) return false;
            return Boolean(el.closest(resumeSelector));
        };

        const allowResumeInteraction = (target: EventTarget | null) => {
            if (!(target instanceof Element)) return false;
            return Boolean(
                target.closest('[contenteditable="true"]') ||
                target.closest('input, textarea, select') ||
                target.closest('button, a, [role="button"]')
            );
        };

        const blockResumeClipboard = (e: Event) => {
            if (!targetInResume(e.target)) return;
            if (allowResumeInteraction(e.target)) return;
            e.preventDefault();
        };

        const onContextMenu = (e: MouseEvent) => {
            if (!targetInResume(e.target)) return;
            if (allowResumeInteraction(e.target)) return;
            e.preventDefault();
        };

        const onDragStart = (e: DragEvent) => {
            if (!targetInResume(e.target)) return;
            if (allowResumeInteraction(e.target)) return;
            e.preventDefault();
        };

        root.addEventListener('copy', blockResumeClipboard);
        root.addEventListener('cut', blockResumeClipboard);
        root.addEventListener('selectstart', blockResumeClipboard);
        root.addEventListener('contextmenu', onContextMenu);
        root.addEventListener('dragstart', onDragStart);

        return () => {
            root.removeEventListener('copy', blockResumeClipboard);
            root.removeEventListener('cut', blockResumeClipboard);
            root.removeEventListener('selectstart', blockResumeClipboard);
            root.removeEventListener('contextmenu', onContextMenu);
            root.removeEventListener('dragstart', onDragStart);
        };
    }, []);

    const [editSaving, setEditSaving] = useState(false);
    const [editSaveError, setEditSaveError] = useState<string | null>(null);
    const [editSaveSuccess, setEditSaveSuccess] = useState(false);
    const [editSaveHubMessage, setEditSaveHubMessage] = useState<string | null>(null);
    // AI edit assistance
    const [aiEditError, setAiEditError] = useState<string | null>(null);

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
    const [pendingAddedSectionKey, setPendingAddedSectionKey] = useState<string | null>(null);
    const [pendingPreviewAddTick, setPendingPreviewAddTick] = useState(0);
    const setSectionOrder = React.useCallback((order: string[]) => {
        const nextOrder = Array.isArray(order) ? order : [];
        const templateKey = String(templateName || '');

        // Persist layout into the editable draft so it is included in Save Changes
        // and so later style auto-saves don't accidentally wipe it.
        if (templateKey) {
            if (inlineEditMode) {
                setInlineEditChanges((prev: any) => {
                    const prevStyle = (prev?.style && typeof prev.style === 'object') ? prev.style : {};
                    const baseStyle = (resumeData?.style && typeof resumeData.style === 'object') ? resumeData.style : {};
                    const mergedResume = { ...(resumeData || {}), ...(prev || {}), style: { ...baseStyle, ...prevStyle } };
                    const patched = withTemplateViewerLayoutPatch(mergedResume, templateKey, { sectionOrder: nextOrder });
                    return {
                        ...(prev || {}),
                        style: {
                            ...((patched?.style && typeof patched.style === 'object') ? patched.style : {}),
                        },
                    };
                });
            } else {
                setResumeData((prev: any) => withTemplateViewerLayoutPatch(prev, templateKey, { sectionOrder: nextOrder }));
            }
        }

        setSectionOrderByTemplate((prev) => {
            const prevOrder = Array.isArray(prev?.[templateKey]) ? prev[templateKey] : [];
            const addedKeys = nextOrder.filter((key) => !prevOrder.includes(key));
            const addedCustomKeys = addedKeys.filter((key) => String(key).startsWith('custom_'));
            if (prevOrder.length > 0 && addedCustomKeys.length > 0) {
                setPendingAddedSectionKey(addedCustomKeys[addedCustomKeys.length - 1]);
            }
            return {
                ...(prev || {}),
                [templateKey]: nextOrder,
            };
        });
    }, [inlineEditMode, resumeData, templateName]);

    const [hiddenSectionKeysByTemplate, setHiddenSectionKeysByTemplate] = useState<Record<string, string[]>>({});
    const hiddenSectionKeys = hiddenSectionKeysByTemplate[String(templateName || '')] || [];
    const setHiddenSectionKeys = React.useCallback((keys: string[]) => {
        const nextKeys = Array.isArray(keys) ? keys : [];
        const templateKey = String(templateName || '');

        if (templateKey) {
            if (inlineEditMode) {
                setInlineEditChanges((prev: any) => {
                    const prevStyle = (prev?.style && typeof prev.style === 'object') ? prev.style : {};
                    const baseStyle = (resumeData?.style && typeof resumeData.style === 'object') ? resumeData.style : {};
                    const mergedResume = { ...(resumeData || {}), ...(prev || {}), style: { ...baseStyle, ...prevStyle } };
                    const patched = withTemplateViewerLayoutPatch(mergedResume, templateKey, { hiddenSectionKeys: nextKeys });
                    return {
                        ...(prev || {}),
                        style: {
                            ...((patched?.style && typeof patched.style === 'object') ? patched.style : {}),
                        },
                    };
                });
            } else {
                setResumeData((prev: any) => withTemplateViewerLayoutPatch(prev, templateKey, { hiddenSectionKeys: nextKeys }));
            }
        }

        setHiddenSectionKeysByTemplate((prev) => ({
            ...(prev || {}),
            ...(templateKey ? { [templateKey]: nextKeys } : {}),
        }));
    }, [inlineEditMode, resumeData, templateName]);
    const [inlineEditChanges, setInlineEditChanges] = useState<any>({});

    useEffect(() => {
        const handlePreviewAddButtonClick = () => setPendingPreviewAddTick((prev) => prev + 1);
        window.addEventListener('tv:add-section-button-click', handlePreviewAddButtonClick as EventListener);
        return () => {
            window.removeEventListener('tv:add-section-button-click', handlePreviewAddButtonClick as EventListener);
        };
    }, []);

    useEffect(() => {
        if (!inlineEditMode || !pendingAddedSectionKey) return;

        let cancelled = false;
        let attempts = 0;
        let timeoutId: number | null = null;

        const findScrollParent = (node: HTMLElement | null): HTMLElement | null => {
            let current = node?.parentElement || null;
            while (current) {
                const style = window.getComputedStyle(current);
                const overflowY = style.overflowY || '';
                if ((overflowY === 'auto' || overflowY === 'scroll') && current.scrollHeight > current.clientHeight + 4) {
                    return current;
                }
                current = current.parentElement;
            }
            return null;
        };

        const scrollTargetIntoView = (target: HTMLElement) => {
            const scrollParent =
                findScrollParent(target) ||
                findScrollParent(pdfPreviewContainerRef.current) ||
                pdfPreviewContainerRef.current;

            if (scrollParent && scrollParent.scrollHeight > scrollParent.clientHeight + 4) {
                const parentRect = scrollParent.getBoundingClientRect();
                const targetRect = target.getBoundingClientRect();
                const topPadding = Math.max(40, parentRect.height * 0.18);
                const nextTop = scrollParent.scrollTop + (targetRect.top - parentRect.top) - topPadding;
                scrollParent.scrollTo({
                    top: Math.max(0, nextTop),
                    behavior: 'smooth',
                });
                return;
            }

            const targetRect = target.getBoundingClientRect();
            const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
            const topPadding = Math.max(40, viewportHeight * 0.18);
            const nextTop = window.scrollY + targetRect.top - topPadding;
            window.scrollTo({
                top: Math.max(0, nextTop),
                behavior: 'smooth',
            });
        };

        const focusNewSection = () => {
            if (cancelled) return;

            const escapedKey = typeof CSS !== 'undefined' && typeof CSS.escape === 'function'
                ? CSS.escape(pendingAddedSectionKey)
                : pendingAddedSectionKey.replace(/"/g, '\\"');
            const visiblePreviewRoot =
                pdfPreviewContainerRef.current?.querySelector<HTMLElement>('[data-tv-preview="true"]') ||
                document.querySelector<HTMLElement>('[data-tv-preview="true"]');
            const section =
                visiblePreviewRoot?.querySelector<HTMLElement>(`[data-tv-section-key="${escapedKey}"]`) ||
                null;

            if (!section) {
                attempts += 1;
                if (attempts < 12) {
                    timeoutId = window.setTimeout(focusNewSection, 50);
                }
                return;
            }

            const editableTargets = Array.from(
                section.querySelectorAll<HTMLElement>('[contenteditable="true"], input, textarea, select')
            );
            const preferredTarget = editableTargets[editableTargets.length - 1] || section;
            scrollTargetIntoView(preferredTarget);

            section.classList.add('ring-4', 'ring-indigo-300', 'ring-offset-2');

            window.setTimeout(() => {
                if (cancelled) return;
                preferredTarget.focus();
                window.setTimeout(() => section.classList.remove('ring-4', 'ring-indigo-300', 'ring-offset-2'), 1200);
                setPendingAddedSectionKey(null);
            }, 220);
        };

        timeoutId = window.setTimeout(focusNewSection, 0);

        return () => {
            cancelled = true;
            if (timeoutId !== null) window.clearTimeout(timeoutId);
        };
    }, [inlineEditMode, pendingAddedSectionKey]);

    const mergeResumeDraft = React.useCallback((baseResume: any, draftChanges: any) => {
        const base = (baseResume && typeof baseResume === 'object') ? baseResume : {};
        const draft = (draftChanges && typeof draftChanges === 'object') ? draftChanges : {};
        return {
            ...base,
            ...draft,
            style: {
                ...((base?.style && typeof base.style === 'object') ? base.style : {}),
                ...((draft?.style && typeof draft.style === 'object') ? draft.style : {}),
            },
        };
    }, []);

    const getCustomSectionCount = React.useCallback((resumeLike: any): number => {
        const customSections = resumeLike?.custom_sections;
        return Array.isArray(customSections) ? customSections.length : 0;
    }, []);

    const draftResume = React.useMemo(() => mergeResumeDraft(resumeData, inlineEditChanges), [inlineEditChanges, mergeResumeDraft, resumeData]);

    const draftResumeJsonStable = React.useMemo(() => JSON.stringify(draftResume ?? {}), [draftResume]);

    const [previewTargetLang, setPreviewTargetLang] = useState(PREVIEW_TRANSLATE_NONE_VALUE);
    const [translatedResume, setTranslatedResume] = useState<any | null>(null);
    const [translateLoading, setTranslateLoading] = useState(false);
    const [translateError, setTranslateError] = useState<string | null>(null);

    const previewLangActive = React.useMemo(
        () => (
            Boolean(previewTargetLang) &&
            previewTargetLang !== PREVIEW_TRANSLATE_NONE_VALUE &&
            previewTargetLang !== PREVIEW_TRANSLATE_RESET_TO_ENGLISH_VALUE
        ),
        [previewTargetLang],
    );

    // Safety: if the reset option ever lands in state (e.g. due to browser quirks),
    // immediately normalize back to the default "Translate" value.
    useEffect(() => {
        if (previewTargetLang !== PREVIEW_TRANSLATE_RESET_TO_ENGLISH_VALUE) return;
        setPreviewTargetLang(PREVIEW_TRANSLATE_NONE_VALUE);
        setTranslatedResume(null);
        setTranslateError(null);
        setTranslateLoading(false);
    }, [previewTargetLang]);

    const displayResume = React.useMemo(() => {
        if (!previewLangActive) return draftResume;
        return translatedResume ?? draftResume;
    }, [previewLangActive, translatedResume, draftResume]);

    const previewContentKey = React.useMemo(() => JSON.stringify(displayResume ?? {}), [displayResume]);

    useEffect(() => {
        if (inlineEditMode) {
            setPreviewTargetLang(PREVIEW_TRANSLATE_NONE_VALUE);
            setTranslatedResume(null);
            setTranslateError(null);
        }
    }, [inlineEditMode]);

    useEffect(() => {
        if (!previewLangActive) {
            setTranslatedResume(null);
            setTranslateError(null);
            setTranslateLoading(false);
            return;
        }
        let cancelled = false;
        const timer = window.setTimeout(async () => {
            setTranslateLoading(true);
            setTranslateError(null);
            try {
                const res = await fetch('/api/translate-resume', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        resume: draftResume,
                        target: previewTargetLang,
                        template: String(templateName || 'professional'),
                    }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data?.success) {
                    throw new Error(String(data?.error || `Translation failed (${res.status})`));
                }
                if (!cancelled) setTranslatedResume(data.resume);
            } catch (e: any) {
                if (!cancelled) {
                    setTranslatedResume(null);
                    setTranslateError(e?.message || 'Translation failed.');
                }
            } finally {
                if (!cancelled) setTranslateLoading(false);
            }
        }, 450);
        return () => {
            cancelled = true;
            window.clearTimeout(timer);
            // If the user switches back to English while a request is in flight,
            // don't leave the UI stuck in a loading state.
            setTranslateLoading(false);
        };
    }, [previewTargetLang, draftResumeJsonStable]);

    const previousDraftCustomCountRef = useRef(0);
    useEffect(() => {
        const nextCustomCount = getCustomSectionCount(draftResume);
        const prevCustomCount = previousDraftCustomCountRef.current;

        if (pendingPreviewAddTick > 0 && nextCustomCount > prevCustomCount) {
            setPendingAddedSectionKey(`custom_${nextCustomCount - 1}`);
            setPendingPreviewAddTick(0);
        }

        previousDraftCustomCountRef.current = nextCustomCount;
    }, [draftResume, getCustomSectionCount, pendingPreviewAddTick]);

    const handleTemplateContentChange = React.useCallback((changes: any) => {
        setInlineEditChanges((prev: any) => {
            const mergedPrev = mergeResumeDraft(resumeData, prev);
            const mergedNext = mergeResumeDraft(resumeData, {
                ...(prev || {}),
                ...(changes || {}),
            });

            const prevCustomCount = getCustomSectionCount(mergedPrev);
            const nextCustomCount = getCustomSectionCount(mergedNext);
            if (nextCustomCount > prevCustomCount) {
                setPendingAddedSectionKey(`custom_${nextCustomCount - 1}`);
            }

            return { ...(prev || {}), ...(changes || {}) };
        });
    }, [getCustomSectionCount, mergeResumeDraft, resumeData]);

    const defaultAccent = React.useMemo(() => normalizeHexColor(getTemplateDefaultAccent(templateName)) || '#243c6b', [templateName]);
    // Keep a derived default text tone around for templates that want it.
    const defaultText = React.useMemo(() => mixWithBlack(defaultAccent, 0.45), [defaultAccent]);

    const backgroundColorControlSupported = ![
        // Background setting has no effect for these templates, so hide it.
        'boldprofessional',
        'orangeheader',
        'traditional',
        'bluelineclassic',
        'creative2',
        'popart',
    ].includes(templateKey);

    // Only 1 user-facing color control exists (Background) when supported by the template.
    // Keep the primary/accent tone pinned to the template default accent (not the dark text tone).
    // Bold Professional relies on --tv-primary being orange for the accent text/borders.
    const safePrimary = React.useMemo(() => defaultAccent, [defaultAccent]);

    const safeAccent = safePrimary;
    const safeAccent40 = React.useMemo(() => `${safeAccent}40`, [safeAccent]);
    const safeAccent60 = React.useMemo(() => `${safeAccent}60`, [safeAccent]);
    const safeAccentLight = React.useMemo(() => mixWithWhite(safeAccent, 0.65), [safeAccent]);
    const safeAccentDark = React.useMemo(() => mixWithBlack(safeAccent, 0.45), [safeAccent]);

    const derivedSecondaryFromAccent = React.useMemo(() => mixWithWhite(safeAccent, 0.85), [safeAccent]);
    const safeSecondary = React.useMemo(() => (
        normalizeHexColor(secondaryColor) ||
        normalizeHexColor(resumeData?.style?.secondaryColor) ||
        derivedSecondaryFromAccent
    ), [secondaryColor, resumeData, derivedSecondaryFromAccent]);

    const safePrimaryLight = React.useMemo(() => mixWithWhite(safePrimary, 0.65), [safePrimary]);
    const safePrimaryDark = React.useMemo(() => mixWithBlack(safePrimary, 0.35), [safePrimary]);
    const safeSecondaryLight = React.useMemo(() => mixWithWhite(safeSecondary, 0.6), [safeSecondary]);
    const safeSecondaryDark = React.useMemo(() => mixWithBlack(safeSecondary, 0.24), [safeSecondary]);

    const persistTemplateStylePatch = React.useCallback((stylePatch: Record<string, any>) => {
        if (!stylePatch || typeof stylePatch !== 'object') return;

        // In inline edit mode, avoid mutating resumeData (it would update `content` and
        // can reset template internal state / wipe unsaved edits).
        if (inlineEditMode) {
            setInlineEditChanges((prev: any) => {
                const prevStyle = (prev?.style && typeof prev.style === 'object') ? prev.style : {};
                const baseStyle = (resumeData?.style && typeof resumeData.style === 'object') ? resumeData.style : {};
                return {
                    ...(prev || {}),
                    style: {
                        ...baseStyle,
                        ...prevStyle,
                        ...stylePatch,
                    },
                };
            });
            return;
        }

        if (!resumeData) return;
        const nextResume = {
            ...(resumeData || {}),
            style: {
                ...((resumeData?.style && typeof resumeData.style === 'object') ? resumeData.style : {}),
                ...stylePatch,
            },
        };
        const nextResumeWithSettings = withTemplateViewerStyleSettings(nextResume, styleSettings);
        setResumeData(nextResumeWithSettings);

        if (accentSaveTimerRef.current) window.clearTimeout(accentSaveTimerRef.current);
        accentSaveTimerRef.current = window.setTimeout(() => {
            (async () => {
                try {
                    const res = await fetch('/api/template-data', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({ resume: nextResumeWithSettings, source_revision_id: sourceRevisionId }),
                    });
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok || !data?.success) {
                        console.warn('Style save failed:', data?.error || `HTTP ${res.status}`);
                    }
                } catch (e) {
                    console.warn('Style save failed:', e);
                }
            })();
        }, 600);
    }, [inlineEditMode, resumeData, sourceRevisionId, styleSettings]);

    const handleAccentColorChange = React.useCallback((next: string) => {
        const normalized = normalizeHexColor(next);
        if (!normalized) return;

        setAccentColor(normalized);

        persistTemplateStylePatch({ accentColor: normalized });
    }, [persistTemplateStylePatch]);

    const handlePrimaryColorChange = React.useCallback((next: string) => {
        const normalized = normalizeHexColor(next);
        if (!normalized) return;
        // Primary is the user-facing "Text color".
        setPrimaryColor(normalized);
        // Keep legacy state in sync (even though we don't expose or persist it as independent).
        setAccentColor(normalized);
        persistTemplateStylePatch({ primaryColor: normalized });
    }, [persistTemplateStylePatch]);

    const handleSecondaryColorChange = React.useCallback((next: string) => {
        if (!backgroundColorControlSupported) return;
        const normalized = normalizeHexColor(next);
        if (!normalized) return;
        setSecondaryColor(normalized);
        persistTemplateStylePatch({ secondaryColor: normalized });
    }, [backgroundColorControlSupported, persistTemplateStylePatch]);

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

    const downloadOnlyReturnToHub = React.useCallback(() => {
        const ret = new URLSearchParams(window.location.search || '').get('return') || '';
        window.location.href = ret || '/my_revisions';
    }, []);

    useEffect(() => {
        let cancelled = false;
        const loadMe = () => {
            fetch('/api/me', { credentials: 'same-origin' })
                .then(r => r.json())
                .then(data => { if (!cancelled) setMe(data); })
                .catch(() => { if (!cancelled) setMe({ is_authenticated: false, is_paid: false, free_revision_limit: 1, revisions_used: 0 }); });
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
                    html, body, #printTarget, #printTarget .tv-style-root {
            --tv-font-scale: ${fs};
            --tv-paragraph-gap: ${pg};
            --tv-space-scale: ${ss};
                        --tv-accent: ${safeAccent};
                        --tv-accent-40: ${safeAccent40};
                        --tv-accent-60: ${safeAccent60};
                        --tv-accent-light: ${safeAccentLight};
                        --tv-accent-dark: ${safeAccentDark};
                        --tv-primary: ${safePrimary};
                        --tv-primary-light: ${safePrimaryLight};
                        --tv-primary-dark: ${safePrimaryDark};
                        --tv-secondary: ${safeSecondary};
                        --tv-secondary-light: ${safeSecondaryLight};
                        --tv-secondary-dark: ${safeSecondaryDark};
          }
                                                    /* Bottom margin on ALL pages; top margin only from page 2 onward.
                                                         Keep left/right at 0 so full-bleed sidebars/headers can still reach the page edge. */
                                                    @page { size: letter; margin: 0.5in 0in 0.5in 0in !important; }
                                                    @page:first { margin-top: 0in !important; }
          html, body {
            width: ${pageWidthPx}px;
            margin: 0 !important;
            padding: 0 !important;
            ${isOnePage ? `height: ${pageHeightPx}px; overflow: hidden !important;` : `height: auto; overflow: visible !important;`}
            background: #fff !important;
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }

                    /* Per-page vertical background fills (repeats on every printed page via position:fixed).
                         This fixes the "vertical color stops at end of content" issue on the last page. */
                    body { position: relative !important; }
                    body::after {
                        content: "";
                        position: fixed;
                        top: 0;
                        left: 0;
                        right: 0;
                        bottom: 0;
                        z-index: 0;
                        pointer-events: none;
                        background: transparent;
                    }
                    #printPage { position: relative; z-index: 1; }
                    body[data-pdf-template="clean"]::after {
                        background: linear-gradient(to right,
                            var(--tv-secondary) 0%,
                            var(--tv-secondary) 33.333%,
                            #ffffff 33.333%,
                            #ffffff 100%
                        );
                    }
                    body[data-pdf-template="classicrose"]::after {
                        background: linear-gradient(to right,
                            var(--tv-secondary) 0%,
                            var(--tv-secondary) 33.333%,
                            #ffffff 33.333%,
                            #ffffff 100%
                        );
                    }
                    body[data-pdf-template="modern"]::after {
                        background: linear-gradient(to right,
                            #ffffff 0%,
                            #ffffff 60%,
                            var(--tv-secondary) 60%,
                            var(--tv-secondary) 100%
                        );
                    }
                    body[data-pdf-template="creative2"]::after {
                        background: #ffffff;
                    }

                    /* Allow the per-page background gradient to show through inside the resume.
                       Many templates render an opaque white "card" wrapper (bg-white) which would otherwise
                       hide the page-level background fills. */
                    #printTarget [data-template="clean"],
                    #printTarget [data-template="classicrose"],
                    #printTarget [data-template="modern"] {
                        background: transparent !important;
                    }
                    /* Creative2: keep an opaque card background in PDF/print to avoid edge shading artifacts */
                    #printTarget [data-template="creative2"].creative2-template {
                        background: #ffffff !important;
                    }
                                        ${pdfDebugEnabled ? `
                    /* Debug marker: magenta bar at absolute page top */
                    body::before {
                        content: "";
                        position: fixed;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 10px;
                        background: #ff00ff !important;
                        z-index: 2147483647;
                    }
                    ` : ``}
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
                                        /* Prevent first-child top-margin collapse (can look like a top strip in PDFs) */
                                        #printTarget { display: flow-root !important; }
                                        #printTarget .tv-style-root { display: flow-root !important; }
                                        /* PDF seam fix: remove wrapper rounding/overflow clipping only in print context */
                                        #printTarget > * { border-radius: 0 !important; overflow: visible !important; }
                                        #printTarget .tv-style-root > * { border-radius: 0 !important; overflow: visible !important; }

                                        /* Chromium print seam fix: sometimes a ~1px white line appears at the very top edge
                                           above a colored header background when printing/saving as PDF. Nudge the header up
                                           by 1px in the print-only iframe to cover the rasterization seam. */
                                        /* Apply generally to the top-most resume block so ALL templates are protected. */
                                        #printTarget .tv-style-root > *:first-child {
                                            margin-top: -1px !important;
                                        }

                                        /* Back-compat: keep the older template-specific selector too. */
                                        #printTarget [data-template="professional"] > div:first-child {
                                            margin-top: -1px !important;
                                        }
                    /* NOTE: Do NOT strip first-page top padding/margins. Requirement: page 1 top must remain unchanged.
                       Page 2+ top breathing room is handled via @page margin-top. */


          /* Prevent individual resume entries from being split across pages */
          #printTarget section,
          #printTarget .space-y-4 > div,
          #printTarget .space-y-5 > div,
          #printTarget .space-y-3 > div,
          #printTarget .space-y-2 > div,
          #printTarget .creative2-item {
            break-inside: avoid;
            page-break-inside: avoid;
          }
          /* Two-column templates: convert grid to block flow for proper pagination */
          #printTarget .grid.grid-cols-12 { display: block !important; }
          #printTarget .grid.grid-cols-12::after { content: ""; display: block; clear: both; }
          #printTarget .grid.grid-cols-12 > .col-span-7 { float: left !important; width: 58% !important; }
          #printTarget .grid.grid-cols-12 > .col-span-5 { float: right !important; width: 40% !important; }
          #printTarget .grid.grid-cols-12 > .col-span-4 { float: left !important; width: 33% !important; }
          #printTarget .grid.grid-cols-12 > .col-span-8 { float: right !important; width: 65% !important; }

                    /* Full-height vertical backgrounds:
                         - The float-based pagination shim above breaks equal-height columns, so templates with
                             colored sidebars need a grid override in print/PDF.
                         - Keep this narrowly scoped to avoid re-introducing grid fragmentation issues elsewhere. */
                    #printTarget [data-template="clean"] .grid.grid-cols-12 {
                        display: grid !important;
                        grid-template-columns: repeat(12, minmax(0, 1fr)) !important;
                        min-height: 10.5in !important;
                    }
                    #printTarget [data-template="clean"] .grid.grid-cols-12::after { content: none !important; display: none !important; }
                    #printTarget [data-template="clean"] .grid.grid-cols-12 > * { float: none !important; width: auto !important; }

                    /* Creative2 vertical accent container: extend to page bottom for one-page resumes */
                    #printTarget [data-template="creative2"].creative2-template > div.relative { min-height: 10.5in !important; }
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
                        // Detect which template is being printed so we can apply the correct per-page background.
                        const tmplEl = (child.matches && child.matches('[data-template]'))
                            ? child
                            : (child.querySelector ? (child.querySelector('[data-template]') as HTMLElement | null) : null);
                        const tmpl = String(tmplEl?.getAttribute('data-template') || '').trim();
                        if (tmpl) doc.body.setAttribute('data-pdf-template', tmpl);

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

    const redirectingToPlansRef = useRef(false);

    function redirectToPlansForPdfDownload() {
        if (redirectingToPlansRef.current) return;
        redirectingToPlansRef.current = true;
        setRedirectingToPlans(true);
        const next = `${window.location.pathname}${window.location.search || ''}`;
        void persistStyleSettingsBestEffort();
        window.location.href = `/plans/template-pdf?next=${encodeURIComponent(next)}`;
    }

    /** Returns false when the user cannot download (unpaid or plan status still loading). */
    function ensurePaidForPdfDownload(): boolean {
        const user = meRef.current ?? me;
        if (!user) return false;
        if (!user.is_paid) {
            redirectToPlansForPdfDownload();
            return false;
        }
        return true;
    }

    async function downloadPdf() {
        if (downloadingPdf) return;
        if (!ensurePaidForPdfDownload()) return;
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
        if (!ensurePaidForPdfDownload()) return false;
        if (previewLangActive && translateLoading) {
            alert('Wait for the preview to finish translating, then download the PDF.');
            return;
        }
        if (previewLangActive && !translatedResume) {
            alert('Translation is not ready yet. Try again in a moment, or pick the language again.');
            return;
        }
        setDownloadingPdf(true);

        const draftMerged = mergeResumeDraft(resumeData, inlineEditChanges);
        const useTranslatedPdf = Boolean(previewLangActive && translatedResume);
        const pdfBaseResume = useTranslatedPdf ? translatedResume : draftMerged;
        const buildSessionResumePayload = (base: any) =>
            withTemplateViewerStyleSettings(
                withTemplateViewerLayoutPatch(base, templateKey, { sectionOrder, hiddenSectionKeys }),
                styleSettings,
            );

        try {
            let pdfSnapshotToken = '';
            if (useTranslatedPdf) {
                const snapRes = await fetch('/api/template-pdf/snapshot', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        resume: buildSessionResumePayload(pdfBaseResume),
                        template: templateName,
                    }),
                });
                const snapData = await snapRes.json().catch(() => ({}));
                if (!snapRes.ok || !snapData?.success || !snapData?.token) {
                    throw new Error(String(snapData?.error || `Could not prepare translated PDF (HTTP ${snapRes.status})`));
                }
                pdfSnapshotToken = String(snapData.token || '').trim();
            }

            const baseName = `resume-${String(templateName || 'resume')}`;
            let filename = `${baseName}.pdf`;
            // In local dev, PDF viewers can keep showing an already-open file tab even after you
            // "re-download" the same filename. Use a unique filename to make changes obvious.
            try {
                const host = String(window.location.hostname || '').toLowerCase();
                const isLocal = host === 'localhost' || host === '127.0.0.1';
                if (isLocal) filename = `${baseName}-${Date.now()}.pdf`;
            } catch {
                // ignore
            }
            const safeTemplate = String(templateName || 'professional');
            const qs = new URLSearchParams({
                fontScale: String(styleSettings.fontScale),
                paragraphGapPx: String(styleSettings.paragraphGapPx),
                spacingScale: String(styleSettings.spacingScale),
            });
            // Debug mode is opt-in via ?pdfdebug=1.
            if (pdfDebugEnabled) qs.set('debug', '1');
            // Cache-bust: browsers/proxies sometimes cache GET PDFs even when content changes.
            qs.set('_ts', String(Date.now()));
            if (pdfSnapshotToken) qs.set('pdfSnapshot', pdfSnapshotToken);
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
            if (res.status === 402) {
                redirectToPlansForPdfDownload();
                return false;
            }
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

    async function persistStyleSettingsBestEffort() {
        try {
            if (!resumeData) return;
            const payloadResumeWithSettings = withTemplateViewerStyleSettings(resumeData, styleSettings);
            const controller = new AbortController();
            const timeoutId = window.setTimeout(() => {
                try {
                    controller.abort();
                } catch {
                    // ignore
                }
            }, 3000);
            const res = await fetch('/api/template-data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                keepalive: true,
                signal: controller.signal,
                body: JSON.stringify({ resume: payloadResumeWithSettings, source_revision_id: sourceRevisionId }),
            });
            window.clearTimeout(timeoutId);
            if (!res.ok) {
                // Keep redirect behavior, but log for diagnosis.
                console.warn('Pre-redirect style save failed:', res.status);
            }
        } catch {
            // Ignore; redirect should still proceed.
        }
    }

    const loadTemplateData = React.useCallback(async () => {
        try {
            const qs = location.search || '';
            const res = await fetch(`/api/template-data${qs}`, { credentials: 'same-origin' });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.error || `HTTP error! status: ${res.status}`);
            }
            const data = await res.json();
            if (data.success) {
                const urlRid = new URLSearchParams(window.location.search || '').get('rid') || '';
                const apiRid = String(data.source_revision_id || '').trim();
                const effectiveRid = (apiRid || urlRid).trim();
                if (effectiveRid) setSourceRevisionId(effectiveRid);

                if (!data.resume || Object.keys(data.resume).length === 0) {
                    setError('Resume data is empty. The resume may not have been parsed correctly.');
                } else {
                    // Hydrate layout settings immediately so print/PDF paths don't briefly render
                    // default order before effects run.
                    const templateKey = String(templateName || '');
                    const savedLayout = normalizeTemplateViewerLayoutSettings(data.resume?.style?.templateViewerLayout);
                    if (savedLayout && templateKey) {
                        const savedOrder = savedLayout.sectionOrderByTemplate?.[templateKey];
                        const savedHidden = savedLayout.hiddenSectionKeysByTemplate?.[templateKey];
                        if (Array.isArray(savedOrder) && savedOrder.length > 0) {
                            setSectionOrderByTemplate((prev) => ({
                                ...(prev || {}),
                                [templateKey]: savedOrder,
                            }));
                        }
                        if (Array.isArray(savedHidden) && savedHidden.length > 0) {
                            setHiddenSectionKeysByTemplate((prev) => ({
                                ...(prev || {}),
                                [templateKey]: savedHidden,
                            }));
                        }
                    }
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
    }, [templateName, location.search]);

    useEffect(() => {
        loadTemplateData();
    }, [loadTemplateData]);

    // Create-resume / embedded preview: parent updates session via POST then asks us to refetch
    // without reloading the iframe (stable src + postMessage).
    useLayoutEffect(() => {
        if (!isEmbed) return;
        const onMessage = (ev: MessageEvent) => {
            if (ev.origin !== window.location.origin) return;
            const d = ev.data as { type?: string } | null;
            if (!d || typeof d !== 'object') return;
            if (d.type !== 'RESUMATIC_TEMPLATE_SESSION_REFRESH') return;
            void loadTemplateData();
        };
        window.addEventListener('message', onMessage);
        return () => window.removeEventListener('message', onMessage);
    }, [isEmbed, loadTemplateData]);

    const styleSettingsInitRef = useRef(false);
    useEffect(() => {
        // Allow re-hydration on template changes.
        styleSettingsInitRef.current = false;
        setStyleSettings(DEFAULT_TEMPLATE_VIEWER_STYLE_SETTINGS);
    }, [templateName]);

    const layoutSettingsInitRef = useRef(false);
    useEffect(() => {
        layoutSettingsInitRef.current = false;
        // Keep per-template state, but clear current template values on change to avoid
        // leaking a previous template's order into a new one before hydration.
        setSectionOrderByTemplate({});
        setHiddenSectionKeysByTemplate({});
    }, [templateName]);

    useEffect(() => {
        if (!resumeData) return;
        if (styleSettingsInitRef.current) return;

        const saved = normalizeTemplateViewerStyleSettings(resumeData?.style?.templateViewerSettings);
        if (saved) {
            setStyleSettings(saved);
        }
        styleSettingsInitRef.current = true;
    }, [resumeData, templateName]);

    useEffect(() => {
        if (!resumeData) return;
        if (layoutSettingsInitRef.current) return;

        const templateKey = String(templateName || '');
        const saved = normalizeTemplateViewerLayoutSettings(resumeData?.style?.templateViewerLayout);
        if (saved && templateKey) {
            const savedOrder = saved.sectionOrderByTemplate?.[templateKey];
            const savedHidden = saved.hiddenSectionKeysByTemplate?.[templateKey];

            if (Array.isArray(savedOrder) && savedOrder.length > 0) {
                setSectionOrderByTemplate((prev) => ({
                    ...(prev || {}),
                    [templateKey]: savedOrder,
                }));
            }
            if (Array.isArray(savedHidden) && savedHidden.length > 0) {
                setHiddenSectionKeysByTemplate((prev) => ({
                    ...(prev || {}),
                    [templateKey]: savedHidden,
                }));
            }
        }

        layoutSettingsInitRef.current = true;
    }, [resumeData, templateName]);

    useEffect(() => {
        if (!resumeData) return;

        const fromAccent = normalizeHexColor(resumeData?.style?.accentColor);
        const fromPrimary = normalizeHexColor(resumeData?.style?.primaryColor);
        const fromSecondary = normalizeHexColor(resumeData?.style?.secondaryColor);

        // Legacy migration: if an older resume saved only accentColor, treat it as the new Text color.
        const effectivePrimary = fromPrimary || fromAccent;

        if (!accentInitRef.current) {
            // Accent is derived from Text; keep internal state aligned so any dependent code stays consistent.
            setAccentColor(effectivePrimary || defaultAccent);
            accentInitRef.current = true;
        }

        if (!primaryInitRef.current) {
            setPrimaryColor(effectivePrimary || '');
            primaryInitRef.current = true;
        } else {
            if (effectivePrimary && effectivePrimary !== normalizeHexColor(primaryColor)) {
                setPrimaryColor(effectivePrimary);
            }
        }

        if (!secondaryInitRef.current) {
            setSecondaryColor(fromSecondary || '');
            secondaryInitRef.current = true;
        } else {
            if (fromSecondary && fromSecondary !== normalizeHexColor(secondaryColor)) {
                setSecondaryColor(fromSecondary);
            }
        }
    }, [resumeData, defaultAccent, accentColor, primaryColor, secondaryColor]);

    useEffect(() => {
        return () => {
            if (accentSaveTimerRef.current != null) {
                window.clearTimeout(accentSaveTimerRef.current);
                accentSaveTimerRef.current = null;
            }
        };
    }, []);

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
        if (!me) return;

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

        if (!me.is_paid) {
            redirectToPlansForPdfDownload();
            return;
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
                (async () => {
                    try {
                        const ok = await downloadPdfAsFile();
                        if (ok && isDownloadOnly) setDownloadOnlyStatus('done');
                    } catch (e: any) {
                        if (isDownloadOnly) {
                            setDownloadOnlyStatus('failed');
                            setDownloadOnlyError(String(e?.message || 'Download failed.'));
                        }
                    }
                })();
                return;
            }
            if (attempts < maxAttempts) {
                window.setTimeout(attemptDownload, 200);
            }
        };
        window.setTimeout(attemptDownload, 100);
    }, [resumeData, loading, error, isDownloadOnly, me]);

    const saveEditedResume = React.useCallback(
        async (
            resumeOverride?: any,
            afterSuccess?: (payloadResumeWithSettings: any) => void,
            opts?: { quiet?: boolean },
        ) => {
            const payloadResume = resumeOverride ?? resumeData;
            if (!payloadResume) return;
            const templateKey = String(templateName || '');
            const payloadResumeWithLayout = withTemplateViewerLayoutPatch(payloadResume, templateKey, {
                sectionOrder,
                hiddenSectionKeys,
            });
            const payloadResumeWithSettings = withTemplateViewerStyleSettings(payloadResumeWithLayout, styleSettings);
            const quiet = Boolean(opts?.quiet);
            if (!quiet) {
                setEditSaving(true);
            }
            setEditSaveError(null);
            if (!quiet) {
                setEditSaveSuccess(false);
                setEditSaveHubMessage(null);
            }
            try {
                const res = await fetch('/api/template-data', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ resume: payloadResumeWithSettings, source_revision_id: sourceRevisionId }),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok || !data?.success) {
                    throw new Error(data?.error || `Failed to save (HTTP ${res.status})`);
                }
                afterSuccess?.(payloadResumeWithSettings);
                if (!quiet) {
                    setEditSaveSuccess(true);
                    window.setTimeout(() => setEditSaveSuccess(false), 2000);

                    if (data?.persisted_to_hub) {
                        setEditSaveHubMessage('Saved to Job Search Hub.');
                        window.setTimeout(() => setEditSaveHubMessage(null), 5000);
                    } else if (typeof data?.persist_reason === 'string' && data.persist_reason) {
                        const reason = String(data.persist_reason);
                        if (reason === 'missing_source_revision_id') {
                            setEditSaveHubMessage(
                                'Saved here, but not linked to a Hub revision (open from Job Search Hub / View Analysis first).',
                            );
                        } else if (reason === 'revision_not_found') {
                            setEditSaveHubMessage(
                                'Saved here, but the Hub revision could not be found (try refreshing Job Search Hub and saving again).',
                            );
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
                }
            } catch (e: any) {
                setEditSaveError(e?.message || 'Failed to save changes.');
            } finally {
                if (!quiet) {
                    setEditSaving(false);
                }
            }
        },
        [resumeData, templateName, sectionOrder, hiddenSectionKeys, styleSettings, sourceRevisionId],
    );

    // Preview translation is intentionally non-destructive: it should not overwrite the
    // underlying resume data. Users can return to the original English version by selecting
    // "English (default)" in the language selector.

    const updateDraftResume = React.useCallback((updater: (prev: any) => any) => {
        if (inlineEditMode) {
            setInlineEditChanges((prevDraft: any) => {
                const mergedPrev = mergeResumeDraft(resumeData, prevDraft);
                const nextMerged = updater(mergedPrev);
                return { ...(nextMerged || {}) };
            });
            return;
        }

        setResumeData((prev: any) => updater(prev));
    }, [inlineEditMode, mergeResumeDraft, resumeData]);

    const ensureSectionVisible = React.useCallback((sectionKey: string) => {
        const nextHidden = (Array.isArray(hiddenSectionKeys) ? hiddenSectionKeys : []).filter((k) => String(k) !== sectionKey);
        setHiddenSectionKeys(nextHidden);

        if (Array.isArray(sectionOrder) && sectionOrder.length > 0 && !sectionOrder.includes(sectionKey)) {
            setSectionOrder([...sectionOrder, sectionKey]);
        }
    }, [hiddenSectionKeys, sectionOrder, setHiddenSectionKeys, setSectionOrder]);

    const resolvePreviewSectionKey = React.useCallback((sectionKey: string) => {
        if (sectionKey === 'experience' && (templateKey === 'traditional' || templateKey === 'bluelineclassic')) {
            return 'work';
        }
        return sectionKey;
    }, [templateKey]);

    const addExperienceItem = () => {
        const previewSectionKey = resolvePreviewSectionKey('experience');
        ensureSectionVisible(previewSectionKey);
        setPendingAddedSectionKey(previewSectionKey);
        updateDraftResume((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.experience) ? prev.experience : [];
            const nextArr = [...prevArr, { title: '', company: '', duration: '', description: '' }];
            return { ...(prev || {}), experience: nextArr };
        });
    };

    const addEducationItem = () => {
        ensureSectionVisible('education');
        setPendingAddedSectionKey('education');
        updateDraftResume((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.education) ? prev.education : [];
            const nextArr = [...prevArr, { degree: '', year: '', institution: '', gpa: '' }];
            return { ...(prev || {}), education: nextArr };
        });
    };

    const addProjectItem = () => {
        ensureSectionVisible('projects');
        setPendingAddedSectionKey('projects');
        updateDraftResume((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.projects) ? prev.projects : [];
            const nextArr = [...prevArr, { title: '', dates: '', technologies: '', link: '', description: '' }];
            return { ...(prev || {}), projects: nextArr };
        });
    };

    const addCertificationItem = () => {
        ensureSectionVisible('certifications');
        setPendingAddedSectionKey('certifications');
        updateDraftResume((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.certifications) ? prev.certifications : [];
            const normalizedTemplateKey = String(templateKey || '').toLowerCase().replace(/[_-]/g, '');
            const nextItem = (normalizedTemplateKey === 'boldprofessional' || normalizedTemplateKey === 'orangeheader')
                ? ''
                : { name: '', issuer: '', year: '' };
            const nextArr = [...prevArr, nextItem];
            return { ...(prev || {}), certifications: nextArr };
        });
    };

    const addCustomSection = () => {
        const nextCustomIndex = Array.isArray(draftResume?.custom_sections) ? draftResume.custom_sections.length : 0;
        setPendingAddedSectionKey(`custom_${nextCustomIndex}`);
        updateDraftResume((prev: any) => {
            const prevArr: any[] = Array.isArray(prev?.custom_sections) ? prev.custom_sections : [];
            const nextArr = [...prevArr, {
                heading: 'New Section',
                items: [
                    {
                        title: 'Header',
                        content: '- First bullet point\n- Second bullet point',
                    },
                ],
            }];
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

    // Display settings are persisted in the saved resume snapshot (resume.style.templateViewerSettings).

    // PDF preview sizing:
    // - "Page scale" fits the Letter page into the preview area visually
    // - "Content scale" matches the Save-as-PDF fit logic (width-fit)
    useEffect(() => {
        const PAGE_W = 816;
        // Match the PDF content area with a safety margin.
        // Letter = 1056px @96dpi. We add top/bottom margins in the actual PDFs.
        // Keep a small safety buffer (12px) to absorb font rendering differences.
        const PAGE_H = 1056;
        const SAFETY_PX = 12;
        // Requirement: page 1 top unchanged, but bottom margin applies to all pages.
        // Simulate that in the preview with different top padding for page 1 vs page 2+.
        const PAD_TOP_FIRST = 0;
        const PAD_TOP_REST = 48; // 0.5in
        const PAD_BOTTOM = 48; // 0.5in
        const VIEW_H_FIRST = Math.max(1, PAGE_H - PAD_TOP_FIRST - PAD_BOTTOM - SAFETY_PX);
        const VIEW_H_REST = Math.max(1, PAGE_H - PAD_TOP_REST - PAD_BOTTOM - SAFETY_PX);
        const EXTRA_FRAME_PX = 20;
        const PAGE_FRAME_H_FIRST = VIEW_H_FIRST + PAD_TOP_FIRST + PAD_BOTTOM + EXTRA_FRAME_PX;
        const PAGE_FRAME_H_REST = VIEW_H_REST + PAD_TOP_REST + PAD_BOTTOM + EXTRA_FRAME_PX;
        const container = pdfPreviewContainerRef.current;
        const inner = pdfPreviewMeasureInnerRef.current;
        if (!container || !inner) return;

        const compute = () => {
            // Account for the preview container padding (p-4 => 16px on each side). Embed (wizard iframe) has p-0.
            const containerW = Math.max(1, container.clientWidth - (isEmbed ? 0 : 32));
            // Measure unscaled template content and compute the same shrink-to-fit as the print iframe
            const contentW = Math.max(1, inner.scrollWidth || inner.getBoundingClientRect().width);
            const contentH = Math.max(1, inner.scrollHeight || inner.getBoundingClientRect().height);
            const scaleW = PAGE_W / contentW;
            const s = Math.min(1, scaleW);
            setPdfPreviewContentScale(s);

            // Build a snapshot with explicit "push to next page" spacers.
            // This prevents resume blocks from being visually cut at page boundaries in the
            // preview, simulating Chromium's break-inside:avoid behavior in the PDF.
            //
            // Strategy:
            //  1. Find all block-level resume elements (sections, individual entries)
            //  2. Skip elements inside CSS grid containers (two-column layouts) — spacers
            //     in one column would desync the other column
            //  3. For each eligible element, if it would be split by a page boundary AND fits
            //     on a single page, insert a spacer to push it to the next page
            let extraSpacerPx = 0;
            if (!inlineEditMode) {
                try {
                    const innerRect = inner.getBoundingClientRect();

                    // Select breakable blocks: <section> elements, individual resume item
                    // containers (.mb-4, .mb-3 children in space-y-* wrappers), and
                    // Creative2 items. These are the elements that break-inside:avoid
                    // protects in the actual PDF.
                    const BREAKABLE_SELECTOR = [
                        'section',                                    // ModernTemplate sections
                        '.space-y-4 > div', '.space-y-5 > div',     // Individual entries (experience, education, projects)
                        '.space-y-3 > div', '.space-y-2 > div',
                        '.creative2-item',                           // Creative2 individual items
                        '.mb-4.last\\:mb-0', '.mb-3.last\\:mb-0',   // Direct item containers
                    ].join(', ');

                    const allCandidates = Array.from(inner.querySelectorAll(BREAKABLE_SELECTOR)) as HTMLElement[];

                    // Filter out elements inside CSS grid containers — spacers in one grid
                    // column would push content down without affecting the other column.
                    const isInsideGrid = (el: HTMLElement): boolean => {
                        let p = el.parentElement;
                        while (p && p !== inner) {
                            const d = window.getComputedStyle(p).display;
                            if (d === 'grid' || d === 'inline-grid') return true;
                            p = p.parentElement;
                        }
                        return false;
                    };
                    const breakables = allCandidates.filter((el) => !isInsideGrid(el));

                    // Tag each live element with a unique index so we can match it to the
                    // cloned snapshot DOM later.
                    breakables.forEach((el, i) => el.setAttribute('data-tv-brk-idx', String(i)));

                    const spacerByIdx = new Map<number, number>();
                    let shift = 0;
                    for (let i = 0; i < breakables.length; i++) {
                        const el = breakables[i];
                        const r = el.getBoundingClientRect();
                        const topUnscaled = Math.max(0, r.top - innerRect.top);
                        const hUnscaled = Math.max(1, r.height);

                        const top = (topUnscaled * s) + shift;
                        const h = hUnscaled * s;
                        // Too tall to keep together — allow it to span pages
                        const maxViewH = Math.max(VIEW_H_FIRST, VIEW_H_REST);
                        if (h >= (maxViewH - 1)) continue;

                        // Find which page this element starts on with variable per-page view heights.
                        const pageStartY = (pageIdx: number): number => (pageIdx <= 0 ? 0 : (VIEW_H_FIRST + (pageIdx - 1) * VIEW_H_REST));
                        const pageViewH = (pageIdx: number): number => (pageIdx <= 0 ? VIEW_H_FIRST : VIEW_H_REST);
                        const findPageIdx = (yPos: number): number => {
                            if (yPos < VIEW_H_FIRST) return 0;
                            return 1 + Math.floor((yPos - VIEW_H_FIRST) / VIEW_H_REST);
                        };

                        const pageIdx = findPageIdx(top);
                        const within = top - pageStartY(pageIdx);
                        const remaining = pageViewH(pageIdx) - within;
                        // Element would be split across pages — push it to the next page
                        if (remaining > 0.5 && remaining < (h - 0.5)) {
                            const spacer = Math.max(1, Math.ceil(remaining));
                            spacerByIdx.set(i, spacer);
                            shift += spacer;
                        }
                    }
                    extraSpacerPx = shift;

                    // Clean up temporary attributes
                    breakables.forEach((el) => el.removeAttribute('data-tv-brk-idx'));

                    const rawHtml = inner.outerHTML || '';
                    if (rawHtml) {
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(rawHtml, 'text/html');
                        const root = doc.body.firstElementChild as HTMLElement | null;
                        if (root && spacerByIdx.size > 0) {
                            const denom = Math.max(0.0001, s);
                            // Re-select the same elements in the snapshot DOM using the temp index
                            const snapshotEls = Array.from(root.querySelectorAll('[data-tv-brk-idx]')) as HTMLElement[];
                            for (const node of snapshotEls) {
                                const idx = parseInt(node.getAttribute('data-tv-brk-idx') || '', 10);
                                node.removeAttribute('data-tv-brk-idx');
                                const spacerH = spacerByIdx.get(idx);
                                if (!spacerH) continue;
                                const spacer = doc.createElement('div');
                                spacer.setAttribute('data-tv-preview-spacer', 'true');
                                spacer.style.display = 'block';
                                spacer.style.width = '100%';
                                // Convert scaled px back to unscaled px for the snapshot
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
            const pages = (() => {
                if (scaledH <= (VIEW_H_FIRST + EPS_PX)) return 1;
                const remaining = Math.max(0, scaledH - VIEW_H_FIRST);
                return 1 + Math.max(1, Math.ceil((remaining - EPS_PX) / VIEW_H_REST));
            })();
            setPdfPreviewPages(pages);

            const layoutPages = embedFirstPageOnly ? 1 : pages;

            // Prefer filling available width. If there are exactly 2 pages, scale so both pages can sit side-by-side.
            const twoUpGapPx = 24; // matches Tailwind gap-6 (1.5rem)
            // In edit mode we render a continuous scroll (no page split / 2-up), so always scale to a single page width.
            const pagesForLayout = inlineEditMode ? 1 : layoutPages;
            const totalW = pagesForLayout === 2 ? ((PAGE_W * 2) + twoUpGapPx) : PAGE_W;
            // Add a tiny safety margin to avoid accidental horizontal scroll due to rounding/subpixel layout.
            const fitScaleRaw = (containerW / totalW) * (isEmbedFlush ? 1 : 0.995);
            const fitScale = (isEmbed && isEmbedFlush)
                ? Math.max(0.1, fitScaleRaw)
                : Math.min(1, fitScaleRaw);
            // Normal mode deterrence: keep the preview fairly small even on wide screens.
            // (Edit mode remains full-size for usability.)
            const NORMAL_MODE_MAX_SCALE = 0.56;

            // Shrink the last "page frame" to the actual remaining content height to avoid a trailing bottom edge/shadow line.
            // (Must run before pageScale in embed: height-fit uses the same model as the paged layout.)
            const keepFullLastPageFrame = ['clean', 'creative2'].includes(String(templateName || '').toLowerCase());
            const lastPageFramePx = (() => {
                if (inlineEditMode) return PAGE_FRAME_H_FIRST;
                if (layoutPages <= 1) return PAGE_FRAME_H_FIRST;
                if (keepFullLastPageFrame) return PAGE_FRAME_H_REST;
                const remainderAfterFirst = Math.max(0, scaledH - VIEW_H_FIRST);
                const pagesAfterFirst = Math.max(1, Math.ceil(remainderAfterFirst / VIEW_H_REST));
                const remainderContent = Math.max(1, remainderAfterFirst - (pagesAfterFirst - 1) * VIEW_H_REST);
                return Math.min(
                    PAGE_FRAME_H_REST,
                    (PAD_TOP_REST + PAD_BOTTOM + EXTRA_FRAME_PX + Math.ceil(remainderContent)),
                );
            })();

            // Embed (create-resume wizard iframe): also scale down so the full preview height fits the iframe — width-only
            // fit was leaving a one-page "letter" preview taller than the pane and forcing a .tv-embed scrollbar.
            const GAP_PX = 24; // matches space-y-6 in the paged preview
            const unzoomedPreviewHeightPx = (() => {
                if (inlineEditMode) {
                    return Math.max(1, scaledH + 32);
                }
                if (layoutPages === 1) {
                    return PAGE_FRAME_H_FIRST;
                }
                if (layoutPages === 2) {
                    // 2-up row: a single page row height
                    return PAGE_FRAME_H_FIRST;
                }
                let h = PAGE_FRAME_H_FIRST;
                for (let i = 1; i < layoutPages; i++) {
                    h += GAP_PX;
                    h += (i < layoutPages - 1) ? PAGE_FRAME_H_REST : lastPageFramePx;
                }
                return h;
            })();
            const EMBED_HEIGHT_PAD = 12;
            const availableViewportH = Math.max(1, (typeof window !== 'undefined' ? window.innerHeight : 0) - EMBED_HEIGHT_PAD);
            const heightFitScaleRaw = (availableViewportH / Math.max(1, unzoomedPreviewHeightPx)) * 0.99;
            const heightFitScale =
                isEmbed
                    ? ((isEmbedFlush ? Math.max(0.1, heightFitScaleRaw) : Math.min(1, heightFitScaleRaw)))
                    : 1;
            const pageScale = (!isEmbed && !inlineEditMode)
                ? Math.min(fitScale, NORMAL_MODE_MAX_SCALE)
                : (isEmbed
                    ? (isEmbedFlush ? fitScale : Math.min(fitScale, heightFitScale, 1))
                    : fitScale);
            const pageScaleZoomed =
                isEmbed && embedZoomMultiplier > 1
                    ? Math.min(pageScale * embedZoomMultiplier, 1.85)
                    : pageScale;
            setPdfPreviewPageScale(pageScaleZoomed);

            // In inline edit mode, content height can change frequently; keep a full first-page frame to avoid a thin strip.
            if (inlineEditMode || layoutPages <= 1) {
                setPdfPreviewLastPageHeightPx(PAGE_FRAME_H_FIRST);
            } else {
                setPdfPreviewLastPageHeightPx(lastPageFramePx);
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
        // Iframe / viewport height does not always trigger ResizeObserver on the preview node.
        let winResize = false;
        if (isEmbed && ro) {
            window.addEventListener('resize', compute);
            winResize = true;
        }

        return () => {
            window.clearTimeout(t1);
            window.clearTimeout(t2);
            if (ro) ro.disconnect();
            else window.removeEventListener('resize', compute);
            if (winResize) window.removeEventListener('resize', compute);
        };
    }, [templateName, resumeData, previewContentKey, styleSettings, inlineEditMode, isEmbed, isEmbedFlush, embedFirstPageOnly, embedZoomMultiplier]);

    // Best-effort zoom deterrence: prevent ctrl/meta+wheel zoom while the pointer is over the preview.
    // (Cannot reliably block browser zoom or OS-level capture globally.)
    useEffect(() => {
        const container = pdfPreviewContainerRef.current;
        if (!container) return;
        if (isEmbed) return;

        const onWheel = (e: WheelEvent) => {
            if (inlineEditMode) return;
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
            }
        };

        container.addEventListener('wheel', onWheel, { passive: false });
        return () => container.removeEventListener('wheel', onWheel as EventListener);
    }, [inlineEditMode, isEmbed]);

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

    // Preview uses optional translated copy; offscreen PDF root matches visible preview (including translation).
    const previewContent = JSON.stringify(displayResume);

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
        // Resume builder / UI label "Classic"
        case 'classic':
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
        // Resume builder / UI label "Contemporary"
        case 'contemporary':
            TemplateComponent = ContemporaryTemplate;
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
        // Resume builder / UI label "Stylish"
        case 'stylish':
            TemplateComponent = StylishTemplate;
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

    const previewLanguageToolbar = (
        <div className="flex flex-col items-stretch gap-1">
            <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-2 py-1.5 shadow-sm">
                <Languages className="w-4 h-4 text-gray-500 shrink-0" aria-hidden />
                <select
                    className="min-w-0 flex-1 text-sm text-gray-800 bg-transparent border-0 focus:ring-0 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    value={previewTargetLang}
                    onChange={(e) => {
                        const next = String(e.target.value || '');
                        if (next === PREVIEW_TRANSLATE_RESET_TO_ENGLISH_VALUE) {
                            setPreviewTargetLang(PREVIEW_TRANSLATE_NONE_VALUE);
                            setTranslatedResume(null);
                            setTranslateError(null);
                            return;
                        }
                        setPreviewTargetLang(next);
                    }}
                    disabled={inlineEditMode || translateLoading}
                    aria-label="Translate"
                    title={inlineEditMode ? 'Exit edit mode to translate the preview' : 'Translate preview text using Google Translate'}
                >
                    {PREVIEW_TRANSLATE_OPTIONS.map((o) => (
                        <option key={o.code ? o.code : 'original'} value={o.code}>
                            {o.label}
                        </option>
                    ))}
                </select>
                {translateLoading ? (
                    <span className="text-xs text-indigo-600 whitespace-nowrap">Translating…</span>
                ) : null}
            </div>
            {translateError ? (
                <div className="text-xs text-red-600 max-w-xs">{translateError}</div>
            ) : null}
        </div>
    );

    if (isThumbnail) {
        return (
            <div className="bg-white overflow-hidden">
                <div
                    className="origin-top-left"
                    style={{
                        width: '816px',
                        transform: 'scale(0.62)',
                        transformOrigin: 'top left',
                    }}
                >
                    <div id="templatePrintRoot" className={inlineEditMode ? 'tv-inline-edit' : undefined}>
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
                                // @ts-ignore
                                ['--tv-accent']: safeAccent,
                                // @ts-ignore
                                ['--tv-accent-40']: safeAccent40,
                                // @ts-ignore
                                ['--tv-accent-60']: safeAccent60,
                                // @ts-ignore
                                ['--tv-accent-light']: safeAccentLight,
                                // @ts-ignore
                                ['--tv-accent-dark']: safeAccentDark,
                                // @ts-ignore
                                ['--tv-primary']: safePrimary,
                                // @ts-ignore
                                ['--tv-primary-light']: safePrimaryLight,
                                // @ts-ignore
                                ['--tv-primary-dark']: safePrimaryDark,
                                // @ts-ignore
                                ['--tv-secondary']: safeSecondary,
                                // @ts-ignore
                                ['--tv-secondary-light']: safeSecondaryLight,
                                // @ts-ignore
                                ['--tv-secondary-dark']: safeSecondaryDark,
                            }}
                        >
                            <TemplateComponent
                                content={previewContent}
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
        );
    }

    return (
        <div
            ref={embedRootRef}
            id="templateViewerPage"
            className={
                isEmbed
                    ? `tv-embed bg-gray-100 ${embedZoomMultiplier > 1 ? 'overflow-x-auto' : 'overflow-x-hidden'} overflow-y-hidden h-screen`
                    : 'min-h-screen bg-gray-100'
            }
        >
            {/* Offscreen export root (used by server-side Playwright PDF generation)
               NOTE: keep this out of the document's scrollable overflow area to avoid
               spurious scrollbars (especially in iframe embed mode). */}
            <div style={{ position: 'fixed', left: '-100000px', top: 0, width: '816px', opacity: 0, pointerEvents: 'none' }}>
                <div id="templatePrintRoot" className={inlineEditMode ? 'tv-inline-edit' : undefined}>
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
                            // @ts-ignore
                            ['--tv-accent']: safeAccent,
                            // @ts-ignore
                            ['--tv-accent-40']: safeAccent40,
                            // @ts-ignore
                            ['--tv-accent-60']: safeAccent60,
                            // @ts-ignore
                            ['--tv-accent-light']: safeAccentLight,
                            // @ts-ignore
                            ['--tv-accent-dark']: safeAccentDark,
                            // @ts-ignore
                            ['--tv-primary']: safePrimary,
                            // @ts-ignore
                            ['--tv-primary-light']: safePrimaryLight,
                            // @ts-ignore
                            ['--tv-primary-dark']: safePrimaryDark,
                            // @ts-ignore
                            ['--tv-secondary']: safeSecondary,
                            // @ts-ignore
                            ['--tv-secondary-light']: safeSecondaryLight,
                            // @ts-ignore
                            ['--tv-secondary-dark']: safeSecondaryDark,
                        }}
                    >
                        <TemplateComponent
                            content={previewContent}
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
                    <header className="sticky top-0 z-50 border-b bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/90">
                        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 flex items-center justify-between">
                            <a href="/" className="inline-flex items-center gap-3">
                                <img src="/static/images/logo23_small.webp" alt="Resumatic AI" className="h-8 w-auto object-contain" width={96} height={96} loading="lazy" />
                            </a>

                            <nav className="hidden md:flex items-center gap-6 text-gray-700" aria-label="Primary">
                                <a href="/" className="hover:text-indigo-600 font-semibold">Home</a>
                                <a href="/blog" className="hover:text-indigo-600 font-semibold">Blog</a>
                                <a href="/about" className="hover:text-indigo-600 font-semibold">About</a>
                                {me?.is_authenticated ? (
                                    <>
                                        <a href="/my_revisions" className="text-white bg-indigo-600 px-4 py-2 rounded-xl hover:bg-indigo-700">
                                            Career Dashboard
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
                                    <a className="block px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 text-center" href="/my_revisions" onClick={() => setMobileNavOpen(false)}>Career Dashboard</a>
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
                {isEmbed && !isDownloadOnly && !embedFirstPageOnly && allowEmbedTranslate ? (
                    <div className="flex justify-end px-2 pt-2 pb-1 border-b border-gray-200 bg-gray-100 shrink-0">
                        {previewLanguageToolbar}
                    </div>
                ) : null}
                <div className={isEmbed ? '' : 'max-w-7xl mx-auto'}>
                    <style>{`
                  /* Mobile should match desktop: make key md:* utilities behave like desktop even on small viewports. */
                  #templatePrintRoot .md\\:flex-row { flex-direction: row !important; }
                  #templatePrintRoot .md\\:w-\\[300px\\] { width: 300px !important; }
                  #templatePrintRoot .md\\:flex-shrink-0 { flex-shrink: 0 !important; }
                  #templatePrintRoot .md\\:text-base { font-size: 1rem !important; line-height: 1.5rem !important; }
                  #templatePrintRoot .md\\:grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)) !important; }

                  /* Strip first-child top padding on the offscreen print root (matches PDF export) */
                  #templatePrintRoot .tv-style-root > *:first-child {
                    margin-top: 0 !important;
                    padding-top: 0 !important;
                  }
                  #templatePrintRoot .tv-style-root > *:first-child > :first-of-type {
                    margin-top: 0 !important;
                    padding-top: 0 !important;
                  }
                  #templatePrintRoot .tv-style-root > *:first-child > :first-of-type > :first-of-type {
                    margin-top: 0 !important;
                    padding-top: 0 !important;
                  }

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

                  /* In Template Viewer edit mode, disable link click-through for all templates */
                  #templatePrintRoot.tv-inline-edit .tv-style-root a {
                    pointer-events: none !important;
                    cursor: default !important;
                  }

                  /* Disable copying resume preview content */
                  #templateViewerPage .pdfPreviewPage,
                  #templateViewerPage .pdfPreviewPage *,
                  #templateViewerPage .pdfPreviewTarget,
                  #templateViewerPage .pdfPreviewTarget *,
                  #templateViewerPage .pdfPreviewViewport .tv-style-root,
                  #templateViewerPage .pdfPreviewViewport .tv-style-root * {
                    -webkit-user-select: none;
                    user-select: none;
                    -webkit-touch-callout: none;
                  }
                  #templateViewerPage .tv-inline-edit [contenteditable="true"],
                  #templateViewerPage .tv-inline-edit input,
                  #templateViewerPage .tv-inline-edit textarea {
                    -webkit-user-select: text;
                    user-select: text;
                  }

                  /* PDF preview page styling (HTML-only simulation of the PDF) */
                  .pdfPreviewPage {
                    width: 816px;
                                                                                                                                                                                                                                                                                                                                height: var(--pdf-page-h, 1064px);
                                        background: var(--pdf-page-bg, #fff);
                    position: relative;
                                        overflow: hidden;
                    box-shadow: 0 12px 30px rgba(0,0,0,0.12);
                  }

                                    /* Full-height vertical backgrounds in preview (last-page aesthetics):
                                         match the PDF intent where sidebars/vertical accents fill the page even if text ends early. */
                                    /* IMPORTANT: Do not force min-height on layout containers here.
                                       It creates a visible blank gap after the last content block.
                                       Instead, rely on the page-level background gradient (pdfPreviewPage)
                                       and make the template wrapper transparent so the gradient shows through. */
                                    .pdfPreviewViewport [data-template="clean"],
                                    .pdfPreviewViewport [data-template="classicrose"],
                                    .pdfPreviewViewport [data-template="modern"] {
                                        background: transparent !important;
                                    }
                                    /* Creative2: keep an opaque card background in preview to match the on-screen template */
                                    .pdfPreviewViewport [data-template="creative2"].creative2-template {
                                        background: #ffffff !important;
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
                  /* Embedded wizard iframe: no floating “page card” chrome */
                  .pdfPreviewPageEmbed {
                    box-shadow: none !important;
                  }
                  .pdfPreviewTarget {
                    position: relative;
                    top: 0;
                    left: 0;
                    width: 816px;
                                                                                                                                                                                                                                                                                                                                height: var(--pdf-page-h, 1064px);
                                        overflow: hidden;
                                        contain: paint;
                                                                                                                                                                --pdf-pad-top-first: 0px;
                                                                                                                                                                --pdf-pad-top-rest: 48px;
                                                                                                                                                                --pdf-pad-bottom: 48px;
                                                                                                                                                                --pdf-view-h-first: 996px;
                                                                                                                                                                --pdf-view-h-rest: 948px;
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
                                                                            height: var(--pdf-view-h);
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

                        /* NOTE: Do NOT strip first-page top padding/margins. Requirement: page 1 top must remain unchanged.
                            Page 2+ top breathing room is handled via the simulated page padding in the viewport. */



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

                        /* Prevent free users from using browser print-to-PDF as an export path.
                            NOTE: this is scoped to the main page root so it does NOT affect the hidden print iframe. */
                        ${(!me?.is_paid) ? `@media print { #templateViewerPage { display: none !important; } }` : ''}
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

                                {downloadOnlyStatus === 'failed' && downloadOnlyError && (
                                    <div className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                                        {downloadOnlyError}
                                    </div>
                                )}

                                <div className="mt-4 flex flex-col sm:flex-row gap-2">
                                    <button
                                        type="button"
                                        className={`px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors ${(downloadingPdf || redirectingToPlans) ? 'opacity-60 cursor-not-allowed' : ''}`}
                                        disabled={downloadingPdf || redirectingToPlans}
                                        onClick={async () => {
                                            if (!ensurePaidForPdfDownload()) return;
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
                                        {redirectingToPlans ? 'Loading...' : (downloadingPdf ? 'Preparing…' : 'Download PDF')}
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
                                        {previewLanguageToolbar}
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
                                                    const mergedBase = mergeResumeDraft(resumeData, inlineEditChanges);
                                                    const merged = withTemplateViewerStyleSettings(mergedBase, styleSettings);
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
                                                    Click "Exit Edit Mode" for <span className="text-indigo-600 font-medium">PDF download</span>.
                                                </span>
                                            </div>
                                        ) : (
                                            <div className="flex items-center gap-2">

                                                <button
                                                    type="button"
                                                    onClick={async () => {
                                                        if (downloadingPdf) return;
                                                        if (redirectingToPlans) return;
                                                        if (!ensurePaidForPdfDownload()) return;
                                                        try {
                                                            await downloadPdfAsFile();
                                                        } catch (e: any) {
                                                            console.error('PDF download failed:', e);
                                                            alert(`PDF download failed (${e?.message || 'unknown error'}).`);
                                                        }
                                                    }}
                                                    className={`px-3 py-2 rounded-lg bg-white border border-gray-200 text-gray-800 hover:bg-gray-50 transition-colors ${(downloadingPdf || redirectingToPlans) ? 'opacity-60 cursor-not-allowed' : ''}`}
                                                    disabled={downloadingPdf || redirectingToPlans || !me}
                                                >
                                                    {!me ? 'Loading…' : (redirectingToPlans ? 'Loading...' : (downloadingPdf ? 'Preparing…' : 'Download PDF'))}
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

                    <div
                        className={`grid ${(isDownloadOnly || isEmbed || inlineEditMode) ? 'grid-cols-1' : 'grid-cols-[125px_minmax(0,1fr)] sm:grid-cols-[300px_minmax(0,1fr)] md:grid-cols-[360px_minmax(0,1fr)]'} ${isEmbed ? 'gap-0' : 'gap-4 sm:gap-6'}`}
                    >
                        {/* Left settings panel */}
                        {!isDownloadOnly && !isEmbed && !inlineEditMode && (
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

                                        </div>
                                    </div>
                                </div>

                                <div className="p-4">
                                    <div>
                                        {!inlineEditMode && (
                                            <div className="mb-4">
                                                <button
                                                    type="button"
                                                    onClick={async () => {
                                                        if (!resumeData) return;
                                                        const merged = withTemplateViewerStyleSettings(resumeData, styleSettings);
                                                        setResumeData(merged);
                                                        await saveEditedResume(merged);
                                                    }}
                                                    className={`px-4 py-2 rounded-lg border transition-colors inline-flex items-center justify-center gap-2 ${editSaving
                                                        ? 'bg-gray-100 text-gray-500 border-gray-200 cursor-not-allowed'
                                                        : 'bg-green-600 text-white border-green-600 hover:bg-green-700'
                                                        }`}
                                                    disabled={editSaving || !resumeData}
                                                >
                                                    {editSaving ? 'Saving…' : 'Save Changes'}
                                                </button>
                                            </div>
                                        )}

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
                                            {backgroundColorControlSupported && (
                                                <div className="rounded-xl border border-gray-200 bg-white p-3">
                                                    <div className="flex items-center justify-between mb-2">
                                                        <label className="text-xs font-semibold text-gray-800 flex items-center gap-2">
                                                            <Wand2 className="w-4 h-4 text-sky-600" />
                                                            Background color
                                                        </label>
                                                    </div>
                                                    <div className="flex flex-wrap gap-2">
                                                        {PROFESSIONAL_BACKGROUND_TONES.map((tone) => {
                                                            const active = safeSecondary.toLowerCase() === tone.value.toLowerCase();
                                                            return (
                                                                <button
                                                                    key={tone.value}
                                                                    type="button"
                                                                    title={tone.name}
                                                                    aria-label={tone.name}
                                                                    aria-pressed={active}
                                                                    onClick={() => handleSecondaryColorChange(tone.value)}
                                                                    disabled={!resumeData}
                                                                    className={`h-8 w-8 rounded-full border transition ${active
                                                                        ? 'ring-2 ring-offset-2 ring-sky-500 border-sky-500'
                                                                        : 'border-gray-300 hover:border-gray-500'
                                                                        } ${!resumeData ? 'opacity-50 cursor-not-allowed' : ''}`}
                                                                    style={{ backgroundColor: tone.value }}
                                                                />
                                                            );
                                                        })}
                                                    </div>
                                                </div>
                                            )}

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
                                        className={`${isEmbed ? 'bg-gray-100 p-0 rounded-none overflow-hidden' : 'bg-gray-100 rounded-lg p-4'} ${mobilePreviewOpen ? 'h-full overflow-auto' : (!isEmbed ? 'overflow-x-auto' : '')}`}
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
                                                                // @ts-ignore
                                                                ['--tv-accent']: safeAccent,
                                                                // @ts-ignore
                                                                ['--tv-accent-40']: safeAccent40,
                                                                // @ts-ignore
                                                                ['--tv-accent-60']: safeAccent60,
                                                                // @ts-ignore
                                                                ['--tv-accent-light']: safeAccentLight,
                                                                // @ts-ignore
                                                                ['--tv-accent-dark']: safeAccentDark,
                                                                // @ts-ignore
                                                                ['--tv-primary']: safePrimary,
                                                                // @ts-ignore
                                                                ['--tv-primary-light']: safePrimaryLight,
                                                                // @ts-ignore
                                                                ['--tv-primary-dark']: safePrimaryDark,
                                                                // @ts-ignore
                                                                ['--tv-secondary']: safeSecondary,
                                                                // @ts-ignore
                                                                ['--tv-secondary-light']: safeSecondaryLight,
                                                                // @ts-ignore
                                                                ['--tv-secondary-dark']: safeSecondaryDark,
                                                            }}
                                                        >
                                                            <TemplateComponent
                                                                content={previewContent}
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
                                            const displayPdfPages = embedFirstPageOnly ? 1 : pdfPreviewPages;
                                            const pagesForLayout = inlineEditMode ? 1 : displayPdfPages;
                                            const totalW = pagesForLayout === 2 ? ((PAGE_W * 2) + twoUpGapPx) : PAGE_W;
                                            const scaledW = Math.max(1, Math.ceil(totalW * pdfPreviewPageScale));
                                            const templateKey = String(templateName || '').toLowerCase();
                                            const pageBg = (() => {
                                                if (templateKey === 'clean') {
                                                    return `linear-gradient(to right, ${safeSecondary} 0%, ${safeSecondary} 33.333%, #ffffff 33.333%, #ffffff 100%)`;
                                                }
                                                if (templateKey === 'classicrose') {
                                                    return `linear-gradient(to right, ${safeSecondary} 0%, ${safeSecondary} 33.333%, #ffffff 33.333%, #ffffff 100%)`;
                                                }
                                                if (templateKey === 'modern') {
                                                    return `linear-gradient(to right, #ffffff 0%, #ffffff 60%, ${safeSecondary} 60%, ${safeSecondary} 100%)`;
                                                }
                                                if (templateKey === 'creative2') {
                                                    return '#ffffff';
                                                }
                                                return '#ffffff';
                                            })();
                                            return (
                                                <div style={isEmbedFlush ? { width: '100%', margin: 0 } : { width: `${scaledW}px`, margin: '0 auto' }}>
                                                    {inlineEditMode ? (
                                                        <div className="mb-3 space-y-2">
                                                            <div className="rounded-xl border border-gray-200 bg-white px-3 py-2 sm:px-4 sm:py-3">
                                                                <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-3">
                                                                    <div className="text-xs sm:text-sm text-gray-600 flex flex-col gap-1 leading-snug">
                                                                        <div className="break-words">Click/Tap any content to edit.</div>
                                                                        <div className="flex items-start gap-2">
                                                                            <Grip className="w-4 h-4 text-gray-500 shrink-0 mt-0.5" />
                                                                            <span className="break-words">Drag sections using the handle on the left of each section. Drop on the right to delete.</span>
                                                                        </div>
                                                                        <div className="flex items-start gap-2 flex-wrap">
                                                                            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] sm:text-xs rounded bg-orange-200 text-black border border-orange-300">
                                                                                <Sparkles className="w-3 h-3" />
                                                                                <span>Assist with AI</span>
                                                                            </span>
                                                                            <span className="break-words">AI rewriting is available directly on supported fields in the editor.</span>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            </div>

                                                            <div className="rounded-xl border border-gray-200 bg-white px-3 py-2 sm:px-4 sm:py-3">
                                                                <div className="text-xs sm:text-sm font-medium text-gray-700 mb-2">Add a section:</div>
                                                                <div className="flex flex-wrap gap-2">
                                                                    {[
                                                                        { label: 'Experience', onClick: addExperienceItem },
                                                                        { label: 'Project', onClick: addProjectItem },
                                                                        { label: 'Education', onClick: addEducationItem },
                                                                        { label: 'Certification', onClick: addCertificationItem },
                                                                        { label: 'Custom Section', onClick: addCustomSection },
                                                                    ].map((action) => (
                                                                        <button
                                                                            key={action.label}
                                                                            type="button"
                                                                            onClick={action.onClick}
                                                                            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100 hover:border-indigo-300"
                                                                        >
                                                                            <span className="inline-flex h-5 items-center justify-center rounded-full bg-indigo-600 px-2 text-white text-xs leading-none">Add</span>
                                                                            <span>{action.label}</span>
                                                                        </button>
                                                                    ))}
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
                                                                                // @ts-ignore
                                                                                ['--tv-accent']: safeAccent,
                                                                                // @ts-ignore
                                                                                ['--tv-accent-40']: safeAccent40,
                                                                                // @ts-ignore
                                                                                ['--tv-accent-60']: safeAccent60,
                                                                                // @ts-ignore
                                                                                ['--tv-accent-light']: safeAccentLight,
                                                                                // @ts-ignore
                                                                                ['--tv-accent-dark']: safeAccentDark,
                                                                                // @ts-ignore
                                                                                ['--tv-primary']: safePrimary,
                                                                                // @ts-ignore
                                                                                ['--tv-primary-light']: safePrimaryLight,
                                                                                // @ts-ignore
                                                                                ['--tv-primary-dark']: safePrimaryDark,
                                                                                // @ts-ignore
                                                                                ['--tv-secondary']: safeSecondary,
                                                                                // @ts-ignore
                                                                                ['--tv-secondary-light']: safeSecondaryLight,
                                                                                // @ts-ignore
                                                                                ['--tv-secondary-dark']: safeSecondaryDark,
                                                                            }}
                                                                        >
                                                                            <TemplateAiAssistProvider
                                                                                value={inlineEditMode ? { rewriteField: aiRewriteResumeField, reportError: setAiEditError } : null}
                                                                            >
                                                                                <TemplateComponent
                                                                                    content={previewContent}
                                                                                    editMode={inlineEditMode}
                                                                                    sectionOrder={sectionOrder}
                                                                                    onSectionOrderChange={setSectionOrder}
                                                                                    hiddenSectionKeys={hiddenSectionKeys}
                                                                                    onHiddenSectionKeysChange={setHiddenSectionKeys}
                                                                                    onContentChange={handleTemplateContentChange}
                                                                                />
                                                                            </TemplateAiAssistProvider>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        ) : (
                                                            // View mode: paged preview (with optional snapshot windowing).
                                                            <div
                                                                className={
                                                                    displayPdfPages === 2
                                                                        ? isEmbed
                                                                            ? 'grid grid-cols-[816px_816px] gap-0 items-start'
                                                                            : 'grid grid-cols-[816px_816px] gap-6 items-start'
                                                                        : isEmbed
                                                                            ? 'space-y-0'
                                                                            : 'space-y-6'
                                                                }
                                                            >
                                                                {Array.from({ length: displayPdfPages }).map((_, idx) => (
                                                                    <div key={idx} className={isEmbed ? '' : 'space-y-8'}>
                                                                        {!isEmbed && (
                                                                            <div className="inline-flex items-center gap-3 w-full">
                                                                                <div
                                                                                    className={
                                                                                        'inline-flex items-center rounded-full bg-white text-gray-700 ring-1 ring-gray-200 font-semibold ' +
                                                                                        (displayPdfPages === 2 ? 'px-6 py-3 text-3xl' : 'px-4 py-2 text-lg')
                                                                                    }
                                                                                >
                                                                                    Page {idx + 1}{displayPdfPages > 1 ? ` of ${displayPdfPages}` : ''}
                                                                                </div>
                                                                                <div className="h-px flex-1 bg-gray-300/80" />
                                                                            </div>
                                                                        )}
                                                                        <div
                                                                            className={
                                                                                `pdfPreviewPage` +
                                                                                `${displayPdfPages === 2 ? ' pdfPreviewPageTwoUp' : ''}` +
                                                                                `${idx === displayPdfPages - 1 ? ' pdfPreviewPageLast' : ''}` +
                                                                                `${isEmbed ? ' pdfPreviewPageEmbed' : ''}`
                                                                            }
                                                                            style={{
                                                                                // Shrink only the last page frame to the remaining content height
                                                                                // (removes trailing bottom edge/shadow line at end-of-document)
                                                                                // @ts-ignore
                                                                                ['--pdf-page-h']: `${(idx === displayPdfPages - 1 && displayPdfPages !== 2) ? pdfPreviewLastPageHeightPx : 1064}px`,
                                                                                // @ts-ignore
                                                                                ['--pdf-page-bg']: pageBg,
                                                                                // Page 1: keep top unchanged. Page 2+: add top breathing room.
                                                                                // @ts-ignore
                                                                                ['--pdf-pad-top']: idx === 0 ? '0px' : '48px',
                                                                                // @ts-ignore
                                                                                ['--pdf-view-h']: idx === 0 ? '996px' : '948px',
                                                                            }}
                                                                        >
                                                                            <div className="pdfPreviewTarget">
                                                                                <div className="pdfPreviewViewport">
                                                                                    {(() => {
                                                                                        // Stride = PDF content area height (with safety margin).
                                                                                        const VIEW_H_FIRST = 996;
                                                                                        const VIEW_H_REST = 948;
                                                                                        // Avoid 1px overlap at page boundaries (can duplicate the last line on the next page)
                                                                                        // due to rounding/subpixel rasterization.
                                                                                        const y = (idx === 0)
                                                                                            ? 0
                                                                                            : (VIEW_H_FIRST + ((idx - 1) * VIEW_H_REST) + 1);
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
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-accent']: safeAccent,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-accent-40']: safeAccent40,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-accent-60']: safeAccent60,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-accent-light']: safeAccentLight,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-accent-dark']: safeAccentDark,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-primary']: safePrimary,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-primary-light']: safePrimaryLight,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-primary-dark']: safePrimaryDark,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-secondary']: safeSecondary,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-secondary-light']: safeSecondaryLight,
                                                                                                        // @ts-ignore
                                                                                                        ['--tv-secondary-dark']: safeSecondaryDark,
                                                                                                    }}
                                                                                                >
                                                                                                    <TemplateComponent
                                                                                                        content={previewContent}
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

function getTemplateDefaultAccent(rawTemplateName?: string): string {
    const key = String(rawTemplateName || '')
        .trim()
        .toLowerCase()
        .replace(/[_-]/g, '');

    switch (key) {
        case 'classicrose':
        case 'elegant':
        case 'lavenderclassic':
            return '#a67c6b';

        case 'boldprofessional':
        case 'orangeheader':
            return '#f36b1c';

        // Default (professional-style blue)
        default:
            return '#243c6b';
    }
}






