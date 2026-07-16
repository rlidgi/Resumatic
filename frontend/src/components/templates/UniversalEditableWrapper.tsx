import React, { useState, useEffect, useCallback, useRef } from 'react';

interface UniversalEditableWrapperProps {
    children: React.ReactNode;
    data: any;
    editMode: boolean;
    onDataChange?: (newData: any) => void;
    activationSelection?: 'all' | 'caret';
}

/**
 * Makes all text content in the resume directly editable via contentEditable
 */
export function UniversalEditableWrapper({
    children,
    data,
    editMode,
    onDataChange,
    activationSelection = 'all'
}: UniversalEditableWrapperProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [editedData, setEditedData] = useState(data);

    useEffect(() => {
        setEditedData(data);
    }, [data]);

    useEffect(() => {
        if (!editMode || !containerRef.current) return;

        const container = containerRef.current;

        // Remove any legacy "click to edit" hint badges if they exist
        const hintCandidates = container.querySelectorAll('div, span');
        hintCandidates.forEach((el) => {
            const text = el.textContent || '';
            if (text.includes('Click to edit') || text.includes('✏️')) {
                (el as HTMLElement).style.display = 'none';
            }
        });

        // Find all text-bearing elements, including nested ones
        const textElements = container.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, div, li, td, th');

        let editableCount = 0;

        const applyActiveStyles = (element: HTMLElement) => {
            element.style.outline = '2px solid #6366f1';
            element.style.outlineOffset = '2px';
            element.style.background = '#fef3c7';
        };

        textElements.forEach((el) => {
            const element = el as HTMLElement;

            // Skip if already has contentEditable set
            if (element.getAttribute('contenteditable') !== null) return;

            // Skip if it has no text at all
            if (!element.textContent?.trim().length) return;

            // Skip pure structural containers (elements that only contain other elements, no direct text)
            const hasDirectText = Array.from(element.childNodes).some(
                node => node.nodeType === Node.TEXT_NODE && node.textContent?.trim()
            );
            const isLeafElement = element.children.length === 0;

            // Only make editable if it's a leaf (no children) OR has direct text content
            if (!hasDirectText && !isLeafElement) return;

            // Add hover effect (pencil cursor comes from .tv-pencil-cursor / [data-editable] CSS)
            element.style.transition = 'all 0.2s ease';
            element.classList.add('tv-pencil-cursor');
            element.setAttribute('data-editable', 'true');
            editableCount++;

            // Make editable on click
            const makeEditableSelectAll = (e: MouseEvent) => {
                e.stopPropagation();
                element.contentEditable = 'true';
                applyActiveStyles(element);
                element.focus();

                const range = document.createRange();
                range.selectNodeContents(element);
                const sel = window.getSelection();
                sel?.removeAllRanges();
                sel?.addRange(range);
            };

            // For caret mode: enable contentEditable on mousedown so the browser can place the caret
            // naturally at the click location (no manual selection needed).
            const makeEditableCaret = (e: MouseEvent) => {
                e.stopPropagation();
                element.contentEditable = 'true';
                applyActiveStyles(element);
                // Let the subsequent mouseup/click position the caret.
                // Focus after enabling editability.
                try {
                    element.focus();
                } catch {
                    // ignore focus errors
                }
            };

            if (activationSelection === 'all') {
                // @ts-ignore
                element.__uewMakeEditable = makeEditableSelectAll;
                element.addEventListener('click', makeEditableSelectAll);
            } else {
                // @ts-ignore
                element.__uewMakeEditable = makeEditableCaret;
                element.addEventListener('mousedown', makeEditableCaret);
            }

            // Show hover hint
            element.addEventListener('mouseenter', function () {
                if (element.contentEditable !== 'true') {
                    element.style.outline = '1px dashed #a5b4fc';
                    element.style.outlineOffset = '2px';
                }
            });

            element.addEventListener('mouseleave', function () {
                if (element.contentEditable !== 'true') {
                    element.style.outline = 'none';
                }
            });

            // Save on blur
            element.addEventListener('blur', function () {
                element.contentEditable = 'false';
                element.style.outline = 'none';
                element.style.background = 'transparent';

                // Trigger data change
                if (onDataChange) {
                    // Simple approach: collect all text and notify parent
                    const newText = element.textContent || '';
                    console.log('Text changed:', newText);
                    // You would implement proper data mapping here
                }
            });
        });

        console.log(`✅ Made ${editableCount} elements editable in edit mode`);

        // Cleanup
        return () => {
            const editableElements = container.querySelectorAll('[data-editable="true"]');
            editableElements.forEach((el) => {
                const element = el as HTMLElement;
                // Remove event listeners we added
                // @ts-ignore
                if (element.__uewMakeEditable) {
                    // @ts-ignore
                    element.removeEventListener('click', element.__uewMakeEditable);
                    // @ts-ignore
                    element.removeEventListener('mousedown', element.__uewMakeEditable);
                    // @ts-ignore
                    delete element.__uewMakeEditable;
                }
                element.classList.remove('tv-pencil-cursor');
                element.style.outline = '';
                element.style.background = '';
                element.contentEditable = 'false';
                element.removeAttribute('data-editable');
            });
        };
    }, [editMode, onDataChange, activationSelection]);

    if (!editMode) {
        return <>{children}</>;
    }

    return (
        <div ref={containerRef} className="relative">
            {children}
        </div>
    );
}
