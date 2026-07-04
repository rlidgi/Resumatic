import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Grip, Sparkles, Trash2 } from 'lucide-react';

type AiAssistField = 'summary' | 'experience_description' | 'project_description' | 'custom_section';

type TemplateAiAssistContextValue = {
    rewriteField: (args: {
        field: AiAssistField;
        text: string;
        meta?: any;
    }) => Promise<string>;
    reportError?: (message: string | null) => void;
};

const TemplateAiAssistContext = React.createContext<TemplateAiAssistContextValue | null>(null);

export function TemplateAiAssistProvider({
    value,
    children,
}: {
    value: TemplateAiAssistContextValue | null;
    children: React.ReactNode;
}) {
    return <TemplateAiAssistContext.Provider value={value}>{children}</TemplateAiAssistContext.Provider>;
}

interface EditableSectionProps {
    id: string;
    children: React.ReactNode;
    editMode: boolean;
    sectionTitle?: string;
    onRemoveSection?: (id: string) => void;
}

export function EditableSection({ id, children, editMode, sectionTitle, onRemoveSection }: EditableSectionProps) {
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

    if (!editMode) {
        return <>{children}</>;
    }

    return (
        <div
            ref={setNodeRef}
            style={style}
            className="relative group"
            data-tv-section-key={id}
            tabIndex={-1}
        >
            {/* Drag handle - absolutely positioned outside the content flow */}
            <div
                className="absolute -left-8 top-0 opacity-100 transition-opacity z-20 flex flex-col items-center gap-2"
                style={{ width: '32px' }}
            >
                <button
                    {...attributes}
                    {...listeners}
                    className="p-1 hover:bg-indigo-100 rounded cursor-grab active:cursor-grabbing touch-none border border-indigo-200 bg-white shadow-sm"
                    aria-label={`Drag to reorder ${sectionTitle || 'section'}`}
                    title="Drag section to re-position"
                    type="button"
                >
                    <Grip className="w-4 h-4 text-indigo-600" />
                </button>
                <button
                    type="button"
                    onClick={() => onRemoveSection?.(id)}
                    className="p-1 hover:bg-red-100 rounded border border-red-200 bg-white shadow-sm text-red-600 transition-colors"
                    aria-label={`Delete ${sectionTitle || 'section'}`}
                    title="Delete section"
                >
                    <Trash2 className="w-4 h-4" />
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

interface AiAssistEditableTextProps extends EditableTextProps {
    aiField: AiAssistField;
    aiMeta?: any;
    aiLabel?: string;
    wrapperClassName?: string;
    buttonClassName?: string;
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

export function AiAssistEditableText({
    aiField,
    aiMeta,
    aiLabel = 'Assist with AI',
    wrapperClassName = '',
    buttonClassName = '',
    value,
    onChange,
    editMode,
    className,
    as,
    multiline,
    liveUpdate,
    layoutSafe,
    placeholder,
}: AiAssistEditableTextProps) {
    const aiAssist = React.useContext(TemplateAiAssistContext);
    const [busy, setBusy] = React.useState(false);

    const handleAssist = async (e: React.MouseEvent<HTMLButtonElement>) => {
        e.preventDefault();
        e.stopPropagation();
        if (!editMode || !aiAssist || busy) return;

        try {
            setBusy(true);
            const nextText = await aiAssist.rewriteField({
                field: aiField,
                text: String(value || ''),
                meta: typeof aiMeta === 'function' ? aiMeta() : aiMeta,
            });
            onChange(nextText);
        } catch (error: any) {
            aiAssist.reportError?.(String(error?.message || 'AI assist failed.'));
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className={`relative group/ai ${wrapperClassName}`.trim()}>
            <EditableText
                value={value}
                onChange={onChange}
                editMode={editMode}
                className={className}
                as={as}
                multiline={multiline}
                liveUpdate={liveUpdate}
                layoutSafe={layoutSafe}
                placeholder={placeholder}
            />
            {editMode && aiAssist ? (
                <button
                    type="button"
                    onClick={handleAssist}
                    className={`absolute right-1 top-1 z-10 inline-flex items-center rounded-md border border-indigo-600 bg-indigo-600 px-2 py-1 text-[10px] font-medium text-white shadow-sm opacity-0 transition-opacity hover:bg-indigo-700 focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 group-hover/ai:opacity-100 ${buttonClassName}`.trim()}
                    aria-label={aiLabel}
                    title={aiLabel}
                    disabled={busy}
                >
                    {busy ? (
                        'AI working'
                    ) : (
                        <>
                            <Sparkles className="inline w-3 h-3 mr-1" />
                            {aiLabel}
                        </>
                    )}
                </button>
            ) : null}
        </div>
    );
}

