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
    const scrollToNewestCustomSection = React.useCallback(() => {
        if (typeof document === 'undefined') return;

        const previewRoot = (document.querySelector('[data-tv-preview="true"]') as HTMLElement | null) || document.body;
        if (!previewRoot) return;

        const nodes = previewRoot.querySelectorAll('[data-custom-section="true"]');
        if (!nodes || nodes.length === 0) return;

        const target = nodes[nodes.length - 1] as HTMLElement | null;
        if (!target) return;

        try {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch {
            target.scrollIntoView();
        }

        // Try to focus the first editable field in the new section (so the user can start typing immediately).
        const firstEditable = target.querySelector('[contenteditable="true"]') as HTMLElement | null;
        if (firstEditable) {
            // Defer focus slightly so scroll has started.
            setTimeout(() => {
                try {
                    firstEditable.focus();
                } catch {
                    // ignore
                }
            }, 50);
        }
    }, []);

    return (
        <div className={`print:hidden ${className}`.trim()} data-html2canvas-ignore="true">
            <button
                type="button"
                onClick={() => {
                    if (typeof document === 'undefined') {
                        onClick();
                        return;
                    }

                    const previewRoot = (document.querySelector('[data-tv-preview="true"]') as HTMLElement | null) || document.body;
                    const beforeCount = previewRoot ? previewRoot.querySelectorAll('[data-custom-section="true"]').length : 0;

                    onClick();

                    // Wait for the new section to render (state update + React render) then scroll.
                    const maxAttempts = 20;
                    let attempts = 0;
                    const tick = () => {
                        attempts += 1;
                        const currentCount = previewRoot ? previewRoot.querySelectorAll('[data-custom-section="true"]').length : 0;
                        if (currentCount > beforeCount) {
                            scrollToNewestCustomSection();
                            return;
                        }
                        if (attempts >= maxAttempts) {
                            // Fallback: scroll anyway to the last known section.
                            scrollToNewestCustomSection();
                            return;
                        }
                        requestAnimationFrame(tick);
                    };

                    requestAnimationFrame(tick);
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
