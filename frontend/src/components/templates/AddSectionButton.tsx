import React from "react";

export default function AddSectionButton({
    onClick,
    className = "",
    title = "Adds a new custom section.",
    label = "Add section",
}: {
    onClick: () => void;
    className?: string;
    title?: string;
    label?: string;
}) {
    const focusNewestCustomSection = React.useCallback(() => {
        if (typeof window === 'undefined') return;

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
            const previewContainer = document.querySelector<HTMLElement>('[data-tv-preview="true"]')?.closest('div');
            const scrollParent = findScrollParent(target) || findScrollParent(previewContainer);

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

        let attempts = 0;

        const tryFocus = () => {
            const visiblePreviewRoot = document.querySelector<HTMLElement>('[data-tv-preview="true"]');
            const customSections = Array.from(
                visiblePreviewRoot?.querySelectorAll<HTMLElement>('[data-tv-section-key^="custom_"]') || []
            );

            const newestSection = customSections
                .map((section) => {
                    const key = String(section.dataset.tvSectionKey || '');
                    const match = key.match(/^custom_(\d+)$/);
                    return { section, order: match ? Number(match[1]) : -1 };
                })
                .sort((a, b) => b.order - a.order)[0]?.section || null;

            if (!newestSection) {
                attempts += 1;
                if (attempts < 20) {
                    window.setTimeout(tryFocus, 60);
                }
                return;
            }

            const editableTargets = Array.from(
                newestSection.querySelectorAll<HTMLElement>('[contenteditable="true"], input, textarea, select')
            );
            const target = editableTargets[editableTargets.length - 1] || newestSection;
            scrollTargetIntoView(target);

            newestSection.classList.add('ring-4', 'ring-indigo-300', 'ring-offset-2');

            window.setTimeout(() => {
                target.focus();
                window.setTimeout(() => {
                    newestSection.classList.remove('ring-4', 'ring-indigo-300', 'ring-offset-2');
                }, 1200);
            }, 220);
        };

        window.setTimeout(tryFocus, 0);
    }, []);

    return (
        <div className={`print:hidden ${className}`.trim()} data-html2canvas-ignore="true">
            <button
                type="button"
                onClick={() => {
                    onClick();
                    focusNewestCustomSection();
                }}
                title={title}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg bg-gradient-to-r from-indigo-600 to-sky-600 text-white shadow-md hover:shadow-lg hover:from-indigo-700 hover:to-sky-700 active:shadow focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:ring-offset-2"
            >
                <span aria-hidden="true" className="inline-flex items-center justify-center w-5 h-5 rounded-md bg-white/15">
                    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
                        <path d="M10 4v12M4 10h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                </span>
                {label}
            </button>
        </div>
    );
}
