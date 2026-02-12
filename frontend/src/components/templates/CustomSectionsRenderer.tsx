import React from "react";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import { EditableText } from "./EditableSection";

export type CustomSectionItem = {
    title?: string;
    subtitle?: string;
    date?: string;
    content?: string;
};

export type CustomSection = {
    heading?: string;
    title?: string;
    label?: string;
    items?: CustomSectionItem[];
    content?: any;
    text?: any;
    body?: any;
};

export default function CustomSectionsRenderer({
    customSections,
    editMode = false,
    showSectionHeadings = true,
    headingClassName = "text-sm font-semibold text-slate-900",
    itemTitleClassName = "text-sm font-semibold text-slate-900",
    itemMetaClassName = "text-xs text-slate-500",
    itemBodyClassName = "text-sm text-slate-700 leading-relaxed",
    onHeadingChange,
    onItemChange,
    onBodyChange,
}: {
    customSections: CustomSection[];
    editMode?: boolean;
    showSectionHeadings?: boolean;
    headingClassName?: string;
    itemTitleClassName?: string;
    itemMetaClassName?: string;
    itemBodyClassName?: string;
    onHeadingChange?: (sectionIndex: number, value: string) => void;
    onItemChange?: (sectionIndex: number, itemIndex: number, field: keyof CustomSectionItem, value: string) => void;
    onBodyChange?: (sectionIndex: number, value: string) => void;
}) {
    const sections = Array.isArray(customSections) ? customSections : [];
    if (sections.length === 0) return null;

    return (
        <div className="space-y-6">
            {sections.map((sec: any, idx: number) => {
                const heading = String(sec?.heading || sec?.title || sec?.label || "Additional").trim();
                const items = Array.isArray(sec?.items) ? sec.items : [];
                const rawBody = sec?.content ?? sec?.text ?? sec?.body ?? "";

                return (
                    <div key={idx}>
                        {showSectionHeadings ? (
                            editMode ? (
                                <EditableText
                                    value={heading}
                                    onChange={(v) => onHeadingChange?.(idx, v)}
                                    editMode={editMode}
                                    liveUpdate
                                    layoutSafe
                                    className={headingClassName}
                                    as="div"
                                />
                            ) : (
                                <div className={headingClassName}>{heading}</div>
                            )
                        ) : null}
                        <div className={`${showSectionHeadings ? "mt-2" : ""} space-y-3`}>
                            {items.length > 0 ? (
                                items.map((it: any, i: number) => {
                                    const title = String(it?.title || "").trim();
                                    const subtitle = String(it?.subtitle || "").trim();
                                    const date = String(it?.date || "").trim();
                                    const content = String(it?.content || "");

                                    const meta = [subtitle, date].filter(Boolean).join(" • ");

                                    const showHeaderRow = editMode || Boolean(title) || Boolean(meta);
                                    const showBody = editMode || Boolean(content);

                                    return (
                                        <div key={i}>
                                            {showHeaderRow ? (
                                                <div className="flex items-baseline justify-between gap-3">
                                                    {editMode ? (
                                                        <EditableText
                                                            value={title}
                                                            onChange={(v) => onItemChange?.(idx, i, 'title', v)}
                                                            editMode={editMode}
                                                            liveUpdate
                                                            layoutSafe
                                                            className={`${itemTitleClassName} inline-block min-w-[6ch] min-h-[1em]`.trim()}
                                                            as="div"
                                                        />
                                                    ) : (
                                                        <div className={itemTitleClassName}>{title}</div>
                                                    )}
                                                    {editMode ? (
                                                        <div className={itemMetaClassName}>
                                                            <EditableText
                                                                value={subtitle}
                                                                onChange={(v) => onItemChange?.(idx, i, 'subtitle', v)}
                                                                editMode={editMode}
                                                                liveUpdate
                                                                layoutSafe
                                                                className="inline-block min-w-[4ch] min-h-[1em]"
                                                                as="span"
                                                            />
                                                            {(subtitle && date) ? <span> • </span> : null}
                                                            <EditableText
                                                                value={date}
                                                                onChange={(v) => onItemChange?.(idx, i, 'date', v)}
                                                                editMode={editMode}
                                                                liveUpdate
                                                                layoutSafe
                                                                className="inline-block min-w-[4ch] min-h-[1em]"
                                                                as="span"
                                                            />
                                                        </div>
                                                    ) : (
                                                        meta ? <div className={itemMetaClassName}>{meta}</div> : null
                                                    )}
                                                </div>
                                            ) : null}
                                            {showBody ? (
                                                <div className="mt-1">
                                                    {editMode ? (
                                                        <EditableText
                                                            value={content}
                                                            onChange={(v) => onItemChange?.(idx, i, 'content', v)}
                                                            editMode={editMode}
                                                            liveUpdate
                                                            layoutSafe
                                                            className={`${itemBodyClassName} min-h-[1.25em]`.trim()}
                                                            as="div"
                                                            multiline
                                                        />
                                                    ) : (
                                                        <RenderMaybeBullets
                                                            text={content}
                                                            forceBullets
                                                            className={itemBodyClassName}
                                                        />
                                                    )}
                                                </div>
                                            ) : null}
                                        </div>
                                    );
                                })
                            ) : editMode ? (
                                <EditableText
                                    value={String(rawBody || '')}
                                    onChange={(v) => onBodyChange?.(idx, v)}
                                    editMode={editMode}
                                    liveUpdate
                                    layoutSafe
                                    className={`${itemBodyClassName} min-h-[1.25em]`.trim()}
                                    as="div"
                                    multiline
                                />
                            ) : rawBody ? (
                                <RenderMaybeBullets
                                    text={String(rawBody)}
                                    forceBullets
                                    className={itemBodyClassName}
                                />
                            ) : (
                                <div className={itemMetaClassName}>No content.</div>
                            )}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
