import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import {
    DndContext,
    closestCenter,
    pointerWithin,
    rectIntersection,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent,
    DragStartEvent,
    DragCancelEvent,
    useDroppable,
    MeasuringStrategy,
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { EditableSection, EditableText } from './EditableSection';
import AddSectionButton from "./AddSectionButton";

type ExecutiveSectionHeadings = Record<string, string>;

type ExecutiveData = {
    name?: string;
    phone?: string;
    email?: string;
    location?: string;
    summary?: string;
    skills?: string[];
    experience?: Array<Record<string, any>>;
    projects?: Array<Record<string, any>>;
    education?: Array<Record<string, any>>;
    custom_sections?: Array<Record<string, any>>;
    section_headings?: ExecutiveSectionHeadings;
    [key: string]: any;
};

interface ExecutiveTemplateProps {
    content: string;
    editMode?: boolean;
    sectionOrder?: string[];
    onSectionOrderChange?: (order: string[]) => void;
    onContentChange?: (changes: ExecutiveData) => void;
    hiddenSectionKeys?: string[];
    onHiddenSectionKeysChange?: (keys: string[]) => void;
}

const TRASH_DROP_ID = '__trash_drop_zone__';

/**
 * ExecutiveTemplate
 * Timeline-style executive layout:
 * - Header row: initials badge + name + contact line
 * - Left column: section labels
 * - Middle: vertical timeline line with dots
 * - Right: section contents
 */
export default function ExecutiveTemplate({
    content,
    editMode = false,
    sectionOrder = [],
    onSectionOrderChange,
    onContentChange,
    hiddenSectionKeys = [],
    onHiddenSectionKeysChange,
}: ExecutiveTemplateProps) {
    const sections = (parseResumeContent(content) || {}) as ExecutiveData;

    const safeHidden = Array.isArray(hiddenSectionKeys) ? hiddenSectionKeys : [];
    const hiddenSet = useMemo(() => new Set(safeHidden.map(String)), [safeHidden]);

    // Local state for inline editing - store entire sections object
    const [editedData, setEditedData] = useState<ExecutiveData>(sections);

    useEffect(() => {
        if (sections) {
            setEditedData(sections);
        }
    }, [content]);

    // Generic update function
    const updateField = useCallback((field: string, value: string) => {
        setEditedData((prev) => {
            const updated = { ...prev, [field]: value };
            if (onContentChange) {
                onContentChange(updated);
            }
            return updated;
        });
    }, [onContentChange]);

    // Update experience field
    const updateExperience = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev) => {
            const updatedExp = [...(prev.experience || [])];
            updatedExp[index] = { ...updatedExp[index], [field]: value };
            const updated = { ...prev, experience: updatedExp };
            if (onContentChange) {
                onContentChange(updated);
            }
            return updated;
        });
    }, [onContentChange]);

    // Update education field
    const updateEducation = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev) => {
            const updatedEdu = [...(prev.education || [])];
            updatedEdu[index] = { ...updatedEdu[index], [field]: value };
            const updated = { ...prev, education: updatedEdu };
            if (onContentChange) {
                onContentChange(updated);
            }
            return updated;
        });
    }, [onContentChange]);

    const updateSectionHeading = useCallback((key: string, heading: string) => {
        setEditedData((prev) => {
            const next = {
                ...prev,
                section_headings: {
                    ...(prev.section_headings || {}),
                    [key]: heading,
                },
            };
            onContentChange?.(next);
            return next;
        });
    }, [onContentChange]);

    const getHeading = useCallback((key: string, fallback: string) => {
        const map = editedData?.section_headings || {};
        const value = map?.[key];
        return typeof value === 'string' && value.trim() ? value : fallback;
    }, [editedData]);

    const updateCustomHeading = useCallback((index: number, heading: string) => {
        setEditedData((prev) => {
            const nextCustom = [...(prev.custom_sections || [])];
            nextCustom[index] = { ...(nextCustom[index] || {}), heading };
            const next = { ...prev, custom_sections: nextCustom };
            onContentChange?.(next);
            return next;
        });
    }, [onContentChange]);

    const name = String(editedData.name || "Your Name");
    const initials = getInitials(name);
    const phone = String(editedData.phone || "").trim();
    const email = String(editedData.email || "").trim();
    const location = String(editedData.location || "").trim();

    const summary = String(editedData.summary || "").trim();
    const skills: string[] = Array.isArray(editedData.skills) ? editedData.skills : [];
    const languages = normalizeList((editedData as any)?.languages);
    const certifications = normalizeCertifications((editedData as any)?.certifications);
    const experience = Array.isArray(editedData.experience) ? editedData.experience : [];
    const projects = Array.isArray(editedData.projects) ? editedData.projects : [];
    const education = Array.isArray(editedData.education) ? editedData.education : [];
    const customSections = Array.isArray(editedData.custom_sections) ? editedData.custom_sections : [];

    const showEmpty = !!(editMode && (editedData as any)?._show_empty_sections);

    // Update projects field
    const updateProject = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev) => {
            const updatedProjects = [...(prev.projects || [])];
            updatedProjects[index] = { ...updatedProjects[index], [field]: value };
            const updated = { ...prev, projects: updatedProjects };
            if (onContentChange) {
                onContentChange(updated);
            }
            return updated;
        });
    }, [onContentChange]);

    const updateSkill = useCallback((index: number, value: string) => {
        setEditedData((prev) => {
            const nextSkills = [...(prev.skills || [])];
            nextSkills[index] = value;
            const next = { ...prev, skills: nextSkills };
            onContentChange?.(next);
            return next;
        });
    }, [onContentChange]);

    const updateLanguageItem = useCallback((index: number, value: string) => {
        setEditedData((prev) => {
            const list = normalizeList((prev as any)?.languages);
            const nextList = [...list];
            nextList[index] = value;
            const cleaned = nextList.map((s) => String(s || '').trim()).filter(Boolean);
            const next = { ...prev, languages: cleaned };
            onContentChange?.(next);
            return next;
        });
    }, [onContentChange]);

    const updateCertificationField = useCallback((index: number, field: 'name' | 'issuer' | 'year', value: string) => {
        setEditedData((prev) => {
            const current = normalizeCertifications((prev as any)?.certifications);
            const nextArr = [...current];
            nextArr[index] = { ...(nextArr[index] || { name: '', issuer: '', year: '' }), [field]: value };
            const cleaned = nextArr.filter((c) => String((c as any)?.name || '').trim());
            const next = { ...prev, certifications: cleaned };
            onContentChange?.(next);
            return next;
        });
    }, [onContentChange]);

    const updateCustomItem = useCallback((sectionIndex: number, itemIndex: number, field: string, value: string) => {
        setEditedData((prev) => {
            const nextCustom = [...(prev.custom_sections || [])];
            const section = { ...(nextCustom[sectionIndex] || {}) };
            const items = Array.isArray(section.items) ? [...section.items] : [];
            const item = { ...(items[itemIndex] || {}) };
            (item as any)[field] = value;
            items[itemIndex] = item;
            section.items = items;
            nextCustom[sectionIndex] = section;
            const next = { ...prev, custom_sections: nextCustom };
            onContentChange?.(next);
            return next;
        });
    }, [onContentChange]);

    const updateCustomBody = useCallback((sectionIndex: number, value: string) => {
        setEditedData((prev) => {
            const nextCustom = [...(prev.custom_sections || [])];
            const section = { ...(nextCustom[sectionIndex] || {}) };
            section.body = value;
            nextCustom[sectionIndex] = section;
            const next = { ...prev, custom_sections: nextCustom };
            onContentChange?.(next);
            return next;
        });
    }, [onContentChange]);

    const addSection = useCallback(() => {
        const insertCustomInOrder = (order: string[], key: string) => {
            if (order.includes(key)) return order;
            const eduAt = order.indexOf('education');
            if (eduAt >= 0) return [...order.slice(0, eduAt), key, ...order.slice(eduAt)];
            return [...order, key];
        };

        setEditedData((prev) => {
            const next: ExecutiveData = { ...(prev || {}) };
            const cur = Array.isArray(next.custom_sections) ? next.custom_sections : [];
            const customKey = `custom_${cur.length}`;

            next.custom_sections = [
                ...cur,
                {
                    heading: 'New Section',
                    items: [
                        {
                            title: 'Header',
                            content: '- First bullet point\n- Second bullet point',
                        },
                    ],
                },
            ];

            if (editMode && onSectionOrderChange) {
                const nextOrder = insertCustomInOrder(sectionOrder || [], customKey);
                onSectionOrderChange(nextOrder);
            }

            onContentChange?.(next);
            return next;
        });
    }, [editMode, onContentChange, onSectionOrderChange, sectionOrder]);

    // Drag and drop sensors
    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const [activeKey, setActiveKey] = useState<string | null>(null);
    const [manualTrashHover, setManualTrashHover] = useState(false);
    const lastPointerRef = useRef<{ x: number; y: number } | null>(null);
    const trashElRef = useRef<HTMLDivElement | null>(null);
    const undoTimerRef = useRef<number | null>(null);
    const [canUseDom, setCanUseDom] = useState(false);
    const [undoState, setUndoState] = useState<null | { prevOrder: string[]; prevHidden: string[] }>(null);

    useEffect(() => {
        setCanUseDom(true);
        return () => {
            if (undoTimerRef.current) {
                window.clearTimeout(undoTimerRef.current);
                undoTimerRef.current = null;
            }
        };
    }, []);

    const allRows = useMemo(() => {
        const formatLabel = (heading: string) => {
            const words = String(heading || "").trim().toUpperCase().split(/\s+/).filter(Boolean);
            if (words.length <= 1) return words.join("");
            return `${words[0]}\n${words.slice(1).join(" ")}`;
        };

        const baseRows: any[] = [];

        if (summary || showEmpty) {
            baseRows.push({
                key: "summary",
                headingFallback: "Professional Summary",
                label: formatLabel(getHeading('summary', 'Professional Summary')),
                content: (
                    <div className="text-[11px] text-slate-600 leading-relaxed">
                        {editMode ? (
                            <EditableText
                                value={summary}
                                placeholder="Summary goes here."
                                onChange={(v) => updateField('summary', v)}
                                editMode={editMode}
                                className="text-[11px] leading-relaxed text-slate-600"
                                as="div"
                                multiline={true}
                            />
                        ) : (
                            <RenderMaybeBullets text={summary} className="text-[11px] leading-relaxed text-slate-600" />
                        )}
                    </div>
                ),
            });
        }

        if (skills.length > 0 || showEmpty) {
            baseRows.push({
                key: "skills",
                headingFallback: "Skills",
                label: formatLabel(getHeading('skills', 'Skills')),
                content: (
                    <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-[11px] text-slate-700">
                        {skills.length > 0 ? (
                            skills.slice(0, 12).map((s, idx) => (
                                <div key={idx} className="flex items-start gap-2">
                                    <span className="mt-[5px] w-1.5 h-1.5 rounded-full bg-slate-400" />
                                    {editMode ? (
                                        <EditableText
                                            value={String(s ?? '')}
                                            onChange={(v) => updateSkill(idx, v)}
                                            editMode={editMode}
                                            className="inline text-[11px] text-slate-700"
                                            as="span"
                                            liveUpdate
                                            layoutSafe
                                        />
                                    ) : (
                                        <span>{s}</span>
                                    )}
                                </div>
                            ))
                        ) : (
                            <span className="text-slate-400">Skills go here.</span>
                        )}
                    </div>
                ),
            });
        }

        if (languages.length > 0 || showEmpty) {
            baseRows.push({
                key: 'languages',
                headingFallback: 'Languages',
                label: formatLabel(getHeading('languages', 'Languages')),
                content: (
                    <div className="text-[11px] text-slate-700">
                        {languages.length > 0 ? (
                            <div className="flex flex-wrap gap-x-4 gap-y-1">
                                {languages.map((l, idx) => (
                                    editMode ? (
                                        <EditableText
                                            key={idx}
                                            value={String(l)}
                                            onChange={(v) => updateLanguageItem(idx, v)}
                                            editMode={editMode}
                                            className="inline text-[11px] text-slate-700"
                                            as="span"
                                            liveUpdate
                                            layoutSafe
                                        />
                                    ) : (
                                        <span key={idx}>{String(l)}</span>
                                    )
                                ))}
                            </div>
                        ) : (
                            <span className="text-slate-400">Languages go here.</span>
                        )}
                    </div>
                ),
            });
        }

        if (certifications.length > 0 || showEmpty) {
            baseRows.push({
                key: 'certifications',
                headingFallback: 'Certifications',
                label: formatLabel(getHeading('certifications', 'Certifications')),
                content: (
                    <div className="space-y-2 text-[11px] text-slate-700">
                        {certifications.length > 0 ? (
                            certifications.map((c, idx) => (
                                <div key={idx}>
                                    <div className="font-semibold text-slate-800">
                                        {editMode ? (
                                            <EditableText
                                                value={String((c as any)?.name || '')}
                                                placeholder="Certification"
                                                onChange={(v) => updateCertificationField(idx, 'name', v)}
                                                editMode={editMode}
                                                className="inline text-[11px] font-semibold text-slate-800"
                                                as="span"
                                                liveUpdate
                                                layoutSafe
                                            />
                                        ) : (
                                            (c as any)?.name
                                        )}
                                    </div>
                                    <div className="text-slate-500">
                                        {editMode ? (
                                            <>
                                                <EditableText value={String((c as any)?.issuer || '')} placeholder="Issuer" onChange={(v) => updateCertificationField(idx, 'issuer', v)} editMode={editMode} className="inline text-[11px] text-slate-500" as="span" liveUpdate layoutSafe />
                                                {(String((c as any)?.issuer || '').trim() && String((c as any)?.year || '').trim()) ? <span> • </span> : null}
                                                <EditableText value={String((c as any)?.year || '')} placeholder="Year" onChange={(v) => updateCertificationField(idx, 'year', v)} editMode={editMode} className="inline text-[11px] text-slate-500" as="span" liveUpdate layoutSafe />
                                            </>
                                        ) : (
                                            [String((c as any)?.issuer || '').trim(), String((c as any)?.year || '').trim()].filter(Boolean).join(' • ')
                                        )}
                                    </div>
                                </div>
                            ))
                        ) : (
                            <span className="text-slate-400">Certifications go here.</span>
                        )}
                    </div>
                ),
            });
        }

        if (experience.length > 0) {
            baseRows.push({
                key: "work",
                headingFallback: "Work History",
                label: formatLabel(getHeading('work', 'Work History')),
                content: (
                    <div className="space-y-6">
                        {experience.length > 0 ? (
                            experience.slice(0, 4).map((exp: any, idx: number) => {
                                const title = exp.title || exp.position || "Role";
                                const company = exp.company || exp.organization || "";
                                const dates = exp.duration || exp.dates || [exp.start, exp.end].filter(Boolean).join(" - ");
                                const city = exp.location || exp.city || "";
                                return (
                                    <div key={idx}>
                                        <div className="flex items-baseline justify-between gap-3">
                                            <EditableText
                                                value={String(title)}
                                                onChange={(v) => updateExperience(idx, 'title', v)}
                                                editMode={editMode}
                                                className="text-[11px] font-bold text-slate-800 uppercase tracking-[0.14em]"
                                                as="div"
                                            />
                                            <EditableText
                                                value={dates ? String(dates) : ""}
                                                placeholder="Dates"
                                                onChange={(v) => updateExperience(idx, 'duration', v)}
                                                editMode={editMode}
                                                className="text-[11px] text-slate-500"
                                                as="div"
                                            />
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-600">
                                            <EditableText
                                                value={company ? String(company) : ""}
                                                placeholder="Company"
                                                onChange={(v) => updateExperience(idx, 'company', v)}
                                                editMode={editMode}
                                                className="inline text-[11px] text-slate-600"
                                                as="span"
                                            />
                                            {editMode ? ", " : ((company && city) ? ", " : "")}
                                            <EditableText
                                                value={city ? String(city) : ""}
                                                placeholder="Location"
                                                onChange={(v) => updateExperience(idx, 'location', v)}
                                                editMode={editMode}
                                                className="inline text-[11px] text-slate-600"
                                                as="span"
                                            />
                                        </div>
                                        {exp.description ? (
                                            <div className="mt-2">
                                                {editMode ? (
                                                    <EditableText
                                                        value={String(exp.description)}
                                                        placeholder="Add bullets or a short description"
                                                        onChange={(v) => updateExperience(idx, 'description', v)}
                                                        editMode={editMode}
                                                        className="text-[11px] leading-relaxed text-slate-600"
                                                        as="div"
                                                        multiline={true}
                                                    />
                                                ) : (
                                                    <RenderMaybeBullets
                                                        text={String(exp.description)}
                                                        forceBullets
                                                        className="text-[11px] leading-relaxed text-slate-600"
                                                    />
                                                )}
                                            </div>
                                        ) : null}
                                    </div>
                                );
                            })
                        ) : (
                            <span className="text-slate-400 text-[11px]">Work history goes here.</span>
                        )}
                    </div>
                ),
            });
        }

        // Key Projects: render only when there are projects (even in edit mode)
        if (projects.length > 0) {
            baseRows.push({
                key: "projects",
                headingFallback: "Key Projects",
                label: formatLabel(getHeading('projects', 'Key Projects')),
                content: (
                    <div className="space-y-4">
                        {projects.length > 0 ? (
                            projects.slice(0, 4).map((proj: any, idx: number) => {
                                const title = String((proj as any)?.title || (proj as any)?.name || "Project");
                                const link = String((proj as any)?.link || (proj as any)?.url || "").trim();
                                const technologies = String((proj as any)?.technologies || (proj as any)?.tech || "").trim();
                                const description = String((proj as any)?.description || "");

                                return (
                                    <div key={idx}>
                                        <div className="flex items-baseline justify-between gap-3">
                                            <EditableText
                                                value={title}
                                                onChange={(v) => updateProject(idx, 'title', v)}
                                                editMode={editMode}
                                                className="text-[11px] font-bold text-slate-800 uppercase tracking-[0.14em]"
                                                as="div"
                                            />
                                            {link ? (
                                                <a
                                                    href={link}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="text-[11px] text-slate-500 hover:text-slate-700 underline underline-offset-2"
                                                >
                                                    Link
                                                </a>
                                            ) : null}
                                        </div>
                                        {technologies ? (
                                            <EditableText
                                                value={technologies}
                                                onChange={(v) => updateProject(idx, 'technologies', v)}
                                                editMode={editMode}
                                                className="mt-1 text-[11px] text-slate-500"
                                                as="div"
                                            />
                                        ) : null}
                                        {description ? (
                                            <div className="mt-2">
                                                {editMode ? (
                                                    <EditableText
                                                        value={description}
                                                        onChange={(v) => updateProject(idx, 'description', v)}
                                                        editMode={editMode}
                                                        className="text-[11px] leading-relaxed text-slate-600"
                                                        as="div"
                                                        multiline={true}
                                                    />
                                                ) : (
                                                    <RenderMaybeBullets
                                                        text={description}
                                                        forceBullets
                                                        className="text-[11px] leading-relaxed text-slate-600"
                                                    />
                                                )}
                                            </div>
                                        ) : null}
                                    </div>
                                );
                            })
                        ) : (
                            <span className="text-slate-400 text-[11px]">Projects go here.</span>
                        )}
                    </div>
                ),
            });
        }

        if (education.length > 0) {
            baseRows.push({
                key: "education",
                headingFallback: "Education",
                label: formatLabel(getHeading('education', 'Education')),
                content: (
                    <div className="space-y-3">
                        {education.length > 0 ? (
                            education.slice(0, 3).map((edu: any, idx: number) => (
                                <div key={idx} className="flex items-baseline justify-between gap-3">
                                    <div>
                                        <EditableText
                                            value={String(edu.degree || edu.title || "Degree")}
                                            onChange={(v) => updateEducation(idx, 'degree', v)}
                                            editMode={editMode}
                                            className="text-[11px] font-bold text-slate-800"
                                            as="div"
                                        />
                                        <EditableText
                                            value={String(edu.institution || edu.school || "")}
                                            onChange={(v) => updateEducation(idx, 'institution', v)}
                                            editMode={editMode}
                                            className="text-[11px] text-slate-600"
                                            as="div"
                                        />
                                        {String(edu?.gpa ?? '').trim() ? (
                                            <div className="text-[11px] text-slate-500">
                                                GPA: <EditableText
                                                    value={String(edu?.gpa ?? '')}
                                                    onChange={(v) => updateEducation(idx, 'gpa', v)}
                                                    editMode={editMode}
                                                    className="inline"
                                                    as="span"
                                                />
                                            </div>
                                        ) : null}
                                    </div>
                                    <EditableText
                                        value={String(edu.year || edu.dates || edu.graduationDate || "")}
                                        onChange={(v) => updateEducation(idx, 'year', v)}
                                        editMode={editMode}
                                        className="text-[11px] text-slate-500"
                                        as="div"
                                    />
                                </div>
                            ))
                        ) : (
                            <span className="text-slate-400 text-[11px]">Education goes here.</span>
                        )}
                    </div>
                ),
            });
        }

        const customRows = (customSections || [])
            .map((sec: any, idx: number) => {
                const heading = String(sec?.heading || sec?.title || sec?.label || "Additional").trim();
                const items = Array.isArray(sec?.items) ? sec.items : [];
                const rawBody = sec?.content ?? sec?.text ?? sec?.body ?? "";
                const hasBody = String(rawBody ?? '').trim().length > 0;
                const hasItems = items.length > 0;
                const hasContent = hasItems || hasBody;
                if (!hasContent) return null;

                return {
                    key: `custom_${idx}`,
                    customIndex: idx,
                    headingRaw: heading,
                    label: formatLabel(heading),
                    content: (
                        <div className="text-[11px] text-slate-600">
                            <CustomSectionsRenderer
                                customSections={[sec]}
                                editMode={editMode}
                                showSectionHeadings={false}
                                itemTitleClassName="text-[11px] font-semibold text-slate-800"
                                itemMetaClassName="text-[11px] text-slate-500"
                                itemBodyClassName="text-[11px] leading-relaxed text-slate-600"
                                onHeadingChange={(sIdx, v) => updateCustomHeading(idx + sIdx, v)}
                                onItemChange={(sIdx, iIdx, field, v) => updateCustomItem(idx + sIdx, iIdx, field as any, v)}
                                onBodyChange={(sIdx, v) => updateCustomBody(idx + sIdx, v)}
                            />
                        </div>
                    ),
                };
            })
            .filter(Boolean) as any[];

        // Insert custom rows before education for better flow.
        const eduIndex = baseRows.findIndex((r) => r.key === "education");
        if (eduIndex >= 0 && customRows.length > 0) {
            const next = [...baseRows];
            next.splice(eduIndex, 0, ...customRows);
            return next;
        }
        return [...baseRows, ...customRows];
    }, [summary, showEmpty, skills, languages, certifications, experience, projects, education, customSections, editMode, updateField, updateExperience, updateEducation, updateProject, updateSkill, getHeading, updateCustomHeading, updateCustomItem, updateCustomBody]);

    // Initialize section order if empty
    useEffect(() => {
        if (editMode && sectionOrder.length === 0 && allRows.length > 0 && onSectionOrderChange) {
            onSectionOrderChange(allRows.filter((r) => !hiddenSet.has(r.key)).map(r => r.key));
        }
    }, [editMode, sectionOrder, allRows, onSectionOrderChange, hiddenSet]);

    // Keep order in sync with visible rows (but never re-add hidden rows)
    useEffect(() => {
        if (!editMode) return;
        if (!onSectionOrderChange) return;
        if (sectionOrder.length === 0) return;

        const visibleKeys = allRows.filter((r) => !hiddenSet.has(r.key)).map((r) => r.key);
        const missing = visibleKeys.filter((k) => !sectionOrder.includes(k));
        if (missing.length === 0) return;
        onSectionOrderChange([...sectionOrder, ...missing]);
    }, [editMode, onSectionOrderChange, sectionOrder, allRows, hiddenSet]);

    // Ordered rows for rendering
    const rows = useMemo(() => {
        const visibleAll = allRows.filter((r: any) => !hiddenSet.has(String(r.key)));
        if (!editMode || sectionOrder.length === 0) {
            return visibleAll;
        }
        const ordered = sectionOrder
            .map(key => visibleAll.find((r: any) => r.key === key))
            .filter(Boolean) as Array<{ key: string; label: string; content: React.ReactNode; }>;

        // Add any new rows that aren't in the order yet
        visibleAll.forEach((row: any) => {
            if (!sectionOrder.includes(row.key)) {
                ordered.push(row);
            }
        });

        return ordered;
    }, [editMode, sectionOrder, allRows, hiddenSet]);

    const showUndo = useCallback((prevOrder: string[], prevHidden: string[]) => {
        setUndoState({ prevOrder, prevHidden });
        if (undoTimerRef.current) window.clearTimeout(undoTimerRef.current);
        undoTimerRef.current = window.setTimeout(() => {
            setUndoState(null);
            undoTimerRef.current = null;
        }, 6000);
    }, []);

    const isPointerInTrash = useCallback(() => {
        const p = lastPointerRef.current;
        const el = trashElRef.current;
        if (!p || !el) return false;
        const rect = el.getBoundingClientRect();
        return p.x >= rect.left && p.x <= rect.right && p.y >= rect.top && p.y <= rect.bottom;
    }, []);

    const onPointerMove = useCallback((e: PointerEvent) => {
        lastPointerRef.current = { x: e.clientX, y: e.clientY };
        setManualTrashHover(isPointerInTrash());
    }, [isPointerInTrash]);

    const attachPointerTracking = useCallback(() => {
        window.addEventListener('pointermove', onPointerMove, { passive: true });
    }, [onPointerMove]);

    const detachPointerTracking = useCallback(() => {
        window.removeEventListener('pointermove', onPointerMove);
        setManualTrashHover(false);
        lastPointerRef.current = null;
    }, [onPointerMove]);

    const removeSectionKey = useCallback((key: string) => {
        if (!onSectionOrderChange) return;

        const prevOrder = [...sectionOrder];
        const prevHidden = [...safeHidden];

        const nextOrder = sectionOrder.filter((k) => k !== key);
        const nextHidden = Array.from(new Set([...safeHidden, String(key)]));

        onSectionOrderChange(nextOrder);
        onHiddenSectionKeysChange?.(nextHidden);
        showUndo(prevOrder, prevHidden);
    }, [onHiddenSectionKeysChange, onSectionOrderChange, safeHidden, sectionOrder, showUndo]);

    const handleDragStart = useCallback((event: DragStartEvent) => {
        setActiveKey(String(event.active.id));
        attachPointerTracking();
    }, [attachPointerTracking]);

    const handleDragCancel = useCallback((_event: DragCancelEvent) => {
        setActiveKey(null);
        detachPointerTracking();
    }, [detachPointerTracking]);

    const handleDragEnd = useCallback((event: DragEndEvent) => {
        const { active, over } = event;
        setActiveKey(null);
        const activeId = String(active.id);

        const overId = over ? String(over.id) : '';
        const hitTrash =
            overId === TRASH_DROP_ID ||
            (Array.isArray((event as any).collisions) && (event as any).collisions.some((c: any) => String(c?.id) === TRASH_DROP_ID));

        const manualHit = isPointerInTrash();
        detachPointerTracking();

        if (hitTrash || manualHit) {
            removeSectionKey(activeId);
            return;
        }
        if (!over) return;
        if (activeId === overId) return;
        if (!onSectionOrderChange) return;

        const visibleKeys = rows.map((r: any) => String(r.key));
        const oldIndex = visibleKeys.indexOf(activeId);
        const newIndex = visibleKeys.indexOf(overId);
        if (oldIndex < 0 || newIndex < 0) return;

        onSectionOrderChange(arrayMove(visibleKeys, oldIndex, newIndex));
    }, [detachPointerTracking, isPointerInTrash, onSectionOrderChange, removeSectionKey, rows]);

    const handleUndo = useCallback(() => {
        if (!undoState) return;
        onSectionOrderChange?.(undoState.prevOrder);
        onHiddenSectionKeysChange?.(undoState.prevHidden);
        setUndoState(null);
        if (undoTimerRef.current) {
            window.clearTimeout(undoTimerRef.current);
            undoTimerRef.current = null;
        }
    }, [onHiddenSectionKeysChange, onSectionOrderChange, undoState]);

    const { isOver, setNodeRef } = useDroppable({ id: TRASH_DROP_ID });
    const setTrashNodeRef = useCallback(
        (node: HTMLDivElement | null) => {
            trashElRef.current = node;
            setNodeRef(node);
        },
        [setNodeRef]
    );

    const collisionDetectionStrategy = useCallback(
        (args: any) => {
            const trashContainers = args.droppableContainers?.filter((c: any) => String(c?.id) === TRASH_DROP_ID) || [];
            if (trashContainers.length > 0) {
                const trashHits = pointerWithin({ ...args, droppableContainers: trashContainers });
                if (trashHits && trashHits.length > 0) return trashHits;

                const trashIntersect = rectIntersection({ ...args, droppableContainers: trashContainers });
                if (trashIntersect && trashIntersect.length > 0) return trashIntersect;
            }
            return closestCenter(args);
        },
        []
    );

    return (
        <div className="bg-white rounded-lg shadow-lg ring-1 ring-black/5 overflow-hidden max-w-4xl mx-auto font-sans">
            <div className={`px-10 py-8 ${editMode ? 'pl-16' : ''}`}>
                {editMode ? (
                    <div
                        className="mb-4 flex flex-wrap items-center gap-2 print:hidden"
                        data-html2canvas-ignore="true"
                    >
                        <AddSectionButton onClick={addSection} />
                    </div>
                ) : null}
                {/* Header */}
                <div className="grid grid-cols-[135px_22px_1fr] gap-x-1 items-start">
                    <div />
                    <div />
                    <div className="flex items-start gap-4 min-w-0">
                        <div className="w-10 h-10 rounded-full border-2 border-sky-500/60 text-slate-700 flex items-center justify-center font-semibold text-sm">
                            {initials}
                        </div>
                        <div className="min-w-0">
                            <EditableText
                                value={name}
                                onChange={(v) => updateField('name', v)}
                                editMode={editMode}
                                className="text-3xl font-light text-sky-600 leading-tight"
                                as="div"
                            />
                            <div className="mt-1 text-xs text-slate-500 flex flex-wrap items-center gap-x-2 gap-y-1">
                                {editMode ? (
                                    <>
                                        <EditableText
                                            value={phone}
                                            onChange={(v) => updateField('phone', v)}
                                            editMode={editMode}
                                            className="inline-block min-w-[8ch]"
                                            as="span"
                                            liveUpdate
                                            layoutSafe
                                        />
                                        <span className="text-slate-300">|</span>
                                        <span className="inline">E:&nbsp;</span>
                                        <EditableText
                                            value={email}
                                            onChange={(v) => updateField('email', v)}
                                            editMode={editMode}
                                            className="inline-block min-w-[12ch]"
                                            as="span"
                                            liveUpdate
                                            layoutSafe
                                        />
                                        <span className="text-slate-300">|</span>
                                        <EditableText
                                            value={location}
                                            onChange={(v) => updateField('location', v)}
                                            editMode={editMode}
                                            className="inline-block min-w-[10ch]"
                                            as="span"
                                            liveUpdate
                                            layoutSafe
                                        />
                                    </>
                                ) : (
                                    <>
                                        {phone && <span>{phone}</span>}
                                        {phone && email && <span className="text-slate-300">|</span>}
                                        {email && <span>E: {email}</span>}
                                        {(phone || email) && location && <span className="text-slate-300">|</span>}
                                        {location && <span>{location}</span>}
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Body */}
                <div className="mt-8">
                    <div className="relative">
                        {/* Continuous timeline line (centered in the 22px middle column) */}
                        <div
                            className="absolute top-0 bottom-0 w-px bg-slate-200 z-0 pointer-events-none"
                            style={{ left: "calc(135px + 4px + 11px)" }}
                        />

                        {editMode ? (
                            <DndContext
                                sensors={sensors}
                                collisionDetection={collisionDetectionStrategy}
                                measuring={{
                                    droppable: {
                                        strategy: MeasuringStrategy.Always,
                                    },
                                }}
                                onDragStart={handleDragStart}
                                onDragCancel={handleDragCancel}
                                onDragEnd={handleDragEnd}
                            >
                                <SortableContext
                                    items={rows.map(r => r.key)}
                                    strategy={verticalListSortingStrategy}
                                >
                                    <div className="space-y-10">
                                        {rows.map((row) => (
                                            <EditableSection key={row.key} id={row.key} editMode={editMode} sectionTitle={row.label.replace('\n', ' ')}>
                                                <div className="grid grid-cols-[135px_22px_1fr] gap-x-1">
                                                    <div className="pt-1 text-[11px] font-bold tracking-[0.18em] text-sky-700 whitespace-pre-line">
                                                        {typeof (row as any).customIndex === 'number' ? (
                                                            <EditableText
                                                                value={String((row as any).headingRaw || '')}
                                                                onChange={(v) => updateCustomHeading((row as any).customIndex, v)}
                                                                editMode={editMode}
                                                                className="text-[11px] font-bold tracking-[0.18em] text-sky-700 uppercase"
                                                                as="div"
                                                            />
                                                        ) : (
                                                            <EditableText
                                                                value={getHeading(String(row.key), String((row as any).headingFallback || row.label.replace('\n', ' ')))}
                                                                onChange={(v) => updateSectionHeading(String(row.key), v)}
                                                                editMode={editMode}
                                                                className="text-[11px] font-bold tracking-[0.18em] text-sky-700 uppercase"
                                                                as="div"
                                                            />
                                                        )}
                                                    </div>
                                                    <div className="pt-2 flex justify-center">
                                                        <span className="relative z-10 w-2.5 h-2.5 rounded-full bg-white border-2 border-slate-300" />
                                                    </div>
                                                    <div>{row.content}</div>
                                                </div>
                                            </EditableSection>
                                        ))}
                                    </div>
                                </SortableContext>

                                {/* Trash drop-zone rail (portal to body; only interactive while dragging) */}
                                {canUseDom ? createPortal(
                                    <div
                                        ref={setTrashNodeRef}
                                        style={{
                                            opacity: activeKey ? 1 : 0,
                                            pointerEvents: activeKey ? 'auto' : 'none',
                                        }}
                                        className={
                                            'fixed right-0 top-0 bottom-0 z-[9998] w-[80px] md:w-[160px] rounded-l-2xl border-2 border-dashed px-2 py-4 flex items-stretch justify-center transition-opacity border-red-400 bg-red-50 text-red-700 ' +
                                            ((isOver || manualTrashHover)
                                                ? 'border-red-600 bg-red-100 text-red-800'
                                                : '')
                                        }
                                        aria-label="Drop here to remove section"
                                    >
                                        <div className="w-full h-full flex flex-col items-center justify-between">
                                            <RailLabel text="Drop to delete" />
                                            <RailLabel text="Drop to delete" />
                                        </div>
                                    </div>,
                                    document.body
                                ) : null}
                            </DndContext>
                        ) : (
                            <div className="space-y-10">
                                {rows.map((row) => (
                                    <div key={row.key} className="grid grid-cols-[135px_22px_1fr] gap-x-1">
                                        <div className="pt-1 text-[11px] font-bold tracking-[0.18em] text-sky-700 whitespace-pre-line">
                                            {row.label}
                                        </div>
                                        <div className="pt-2 flex justify-center">
                                            <span className="relative z-10 w-2.5 h-2.5 rounded-full bg-white border-2 border-slate-300" />
                                        </div>
                                        <div>{row.content}</div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {undoState ? (
                    <div className="fixed bottom-4 left-4 z-[9999] rounded-xl border border-gray-200 bg-white shadow-lg px-4 py-3 flex items-center gap-3">
                        <div className="text-sm text-gray-800">Section removed.</div>
                        <button
                            type="button"
                            onClick={handleUndo}
                            className="text-sm font-semibold text-indigo-700 hover:text-indigo-800"
                        >
                            Undo
                        </button>
                    </div>
                ) : null}
            </div>
        </div>
    );
}

function RailLabel({ text }: { text: string }) {
    return (
        <div
            className="font-black uppercase tracking-[0.45em] text-sm leading-none select-none opacity-95"
            style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
        >
            {text}
        </div>
    );
}

function getInitials(fullName: string): string {
    const cleaned = String(fullName || "").trim().replace(/\s+/g, " ");
    if (!cleaned) return "JD";
    const parts = cleaned.split(" ").filter(Boolean);
    const first = parts[0]?.[0] || "J";
    const last = (parts.length > 1 ? parts[parts.length - 1]?.[0] : parts[0]?.[1]) || "D";
    return `${String(first).toUpperCase()}${String(last).toUpperCase()}`;
}

function normalizeList(value: any): string[] {
    if (Array.isArray(value)) return value.map((v) => String(v)).map((s) => s.trim()).filter(Boolean);
    if (typeof value === 'string') {
        return value
            .split(/[,•]|\\n/g)
            .map((s) => s.trim())
            .filter(Boolean);
    }
    return [];
}

function normalizeLanguages(value: any): Array<{ name: string; level: string }> {
    if (!value) return [];
    if (Array.isArray(value)) {
        return value
            .map((l) => {
                if (typeof l === 'string') return { name: l, level: 'Proficient' };
                const name = (l as any)?.name || (l as any)?.language || (l as any)?.label || '';
                const level = (l as any)?.level || (l as any)?.proficiency || (l as any)?.rating || '';
                return { name: String(name), level: String(level || 'Proficient') };
            })
            .map((x) => ({ name: String(x.name || '').trim(), level: String(x.level || '').trim() }))
            .filter((x) => x.name);
    }
    if (typeof value === 'string') {
        return normalizeList(value).map((n) => ({ name: n, level: 'Proficient' }));
    }
    return [];
}

function normalizeCertifications(value: any): Array<{ name: string; issuer: string; year: string }> {
    if (!value) return [];
    if (Array.isArray(value)) {
        return value
            .map((c) => {
                if (typeof c === 'string') return { name: c, issuer: '', year: '' };
                const name = (c as any)?.name || (c as any)?.title || (c as any)?.label || '';
                const issuer = (c as any)?.issuer || (c as any)?.organization || (c as any)?.provider || '';
                const year = (c as any)?.year || (c as any)?.date || (c as any)?.issued || '';
                return { name: String(name), issuer: String(issuer), year: String(year) };
            })
            .map((x) => ({
                name: String(x.name || '').trim(),
                issuer: String(x.issuer || '').trim(),
                year: String(x.year || '').trim(),
            }))
            .filter((x) => x.name);
    }
    if (typeof value === 'string') {
        return normalizeList(value).map((n) => ({ name: n, issuer: '', year: '' }));
    }
    return [];
}


