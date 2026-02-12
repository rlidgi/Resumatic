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
    return (
        <div className={`print:hidden ${className}`.trim()} data-html2canvas-ignore="true">
            <button
                type="button"
                onClick={onClick}
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
