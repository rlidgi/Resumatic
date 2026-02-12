import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';

interface EditableSectionProps {
    id: string;
    children: React.ReactNode;
    editMode: boolean;
    sectionTitle?: string;
}

export function EditableSection({ id, children, editMode, sectionTitle }: EditableSectionProps) {
    // Debug logging
    React.useEffect(() => {
        console.log(`EditableSection[${id}]: editMode=${editMode}, sectionTitle=${sectionTitle}`);
    }, [id, editMode, sectionTitle]);

    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging,
    } = useSortable({ id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
    };

    console.log(`EditableSection[${id}]: Rendering with editMode=${editMode}`);

    if (!editMode) {
        console.log(`EditableSection[${id}]: Returning plain children (editMode is false)`);
        return <>{children}</>;
    }

    return (
        <div
            ref={setNodeRef}
            style={style}
            className="relative group"
        >
            {/* Drag handle - absolutely positioned outside the content flow */}
            <div
                className="absolute -left-8 top-0 opacity-0 group-hover:opacity-100 transition-opacity z-20"
                style={{ width: '32px' }}
            >
                <button
                    {...attributes}
                    {...listeners}
                    className="p-1 hover:bg-indigo-100 rounded cursor-grab active:cursor-grabbing touch-none border border-indigo-200 bg-white shadow-sm"
                    aria-label={`Drag to reorder ${sectionTitle || 'section'}`}
                    type="button"
                >
                    <GripVertical className="w-4 h-4 text-indigo-600" />
                </button>
            </div>

            {/* Visual indicator - subtle border */}
            <div className="border-2 border-indigo-300 rounded-lg shadow-sm bg-indigo-50/20 hover:bg-indigo-50/40 transition-colors p-2">
                <div className="bg-white rounded">
                    {children}
                </div>
            </div>
        </div>
    );
}

interface EditableTextProps {
    value: string;
    onChange: (value: string) => void;
    editMode: boolean;
    className?: string;
    as?: 'h1' | 'h2' | 'h3' | 'p' | 'span' | 'div';
    multiline?: boolean;
    liveUpdate?: boolean;
    layoutSafe?: boolean;
    placeholder?: string;
}

export function EditableText({
    value,
    onChange,
    editMode,
    className = '',
    as: Component = 'p',
    multiline = false,
    liveUpdate = false,
    layoutSafe = false,
    placeholder,
}: EditableTextProps) {
    const [isFocused, setIsFocused] = React.useState(false);
    const elementRef = React.useRef<HTMLElement | null>(null);

    // Keep the DOM in sync with `value` only when NOT focused.
    // When focused, React-driven updates to innerHTML/text can reset the caret/selection,
    // causing the cursor to jump (commonly to the beginning) after typing.
    React.useLayoutEffect(() => {
        const el = elementRef.current;
        if (!el) return;
        if (isFocused) return;

        const current = multiline ? (el.innerText ?? '') : (el.textContent ?? '');
        const next = String(value ?? '');
        if (current !== next) {
            // Use innerText for multiline so newlines are preserved.
            if (multiline) {
                el.innerText = next;
            } else {
                el.textContent = next;
            }
        }
    }, [value, isFocused, multiline]);

    const handleBlur = (e: React.FocusEvent<HTMLElement>) => {
        const newValue = multiline ? (e.currentTarget.innerText || '') : (e.currentTarget.textContent || '');
        if (newValue !== value) {
            onChange(newValue);
        }
        setIsFocused(false);
    };

    const handleFocus = () => {
        setIsFocused(true);
    };

    const handleInput = (e: React.FormEvent<HTMLElement>) => {
        if (!editMode || !liveUpdate) return;
        const newValue = multiline ? (e.currentTarget.innerText || '') : (e.currentTarget.textContent || '');
        if (newValue !== value) {
            onChange(newValue);
        }
    };

    if (!editMode) {
        return React.createElement(Component, { className }, value);
    }

    const editClasses = editMode
        ? (layoutSafe
            // Layout-safe: do NOT add padding/margins that could change line-wrapping or page height.
            ? 'cursor-text outline-none rounded transition-colors ring-1 ring-transparent hover:ring-2 hover:ring-amber-300 focus:ring-2 focus:ring-indigo-400 focus:bg-white'
            // Default: slightly padded for easier click/visual affordance (may affect layout).
            : 'cursor-text outline-none rounded transition-colors ring-1 ring-transparent hover:ring-2 hover:ring-amber-300 focus:ring-2 focus:ring-indigo-400 focus:bg-white rounded px-2 py-1 transition-colors')
        : '';

    const multilineWhitespace = multiline ? 'whitespace-pre-wrap' : '';

    // Important: do not wrap with an extra <div>. Wrapping changes layout (e.g. span becomes block-like),
    // which can cause content to spill to an extra page in edit mode.
    const Tag = Component as keyof JSX.IntrinsicElements;
    return (
        <Tag
            ref={(node: any) => {
                elementRef.current = node as HTMLElement | null;
            }}
            contentEditable
            suppressContentEditableWarning
            onBlur={handleBlur}
            onFocus={handleFocus}
            onInput={handleInput}
            data-placeholder={placeholder ? String(placeholder) : undefined}
            className={`${className} ${editClasses} ${multilineWhitespace} ${placeholder ? 'editable-text--placeholder' : ''}`.trim()}
        />
    );
}

