import React, { useEffect, useMemo, useState, useCallback } from "react";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent,
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { EditableSection, EditableText } from './EditableSection';
import AddSectionButton from "./AddSectionButton";

type TimelineBlueSectionHeadings = Record<string, string>;

type TimelineBlueData = {
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
    section_headings?: TimelineBlueSectionHeadings;
    [key: string]: any;
};

interface TimelineBlueTemplateProps {
    content: string;
    editMode?: boolean;
    sectionOrder?: string[];
    onSectionOrderChange?: (order: string[]) => void;
    onContentChange?: (changes: TimelineBlueData) => void;
}

/**
 * TimelineBlueTemplate
 * Recreates the uploaded "blue timeline" layout:
 * - Header row: initials badge + name + contact line
 * - Left column: section labels (PROFESSIONAL SUMMARY / SKILLS / WORK HISTORY / EDUCATION)
 * - Middle: vertical timeline line with dots
 * - Right: section contents
 */
export default function TimelineBlueTemplate({
    content,
    editMode = false,
    sectionOrder = [],
    onSectionOrderChange,
    onContentChange
}: TimelineBlueTemplateProps) {
    const sections = (parseResumeContent(content) || {}) as TimelineBlueData;

    // Local state for inline editing - store entire sections object
    const [editedData, setEditedData] = useState<TimelineBlueData>(sections);

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
    const experience = Array.isArray(editedData.experience) ? editedData.experience : [];
    const projects = Array.isArray(editedData.projects) ? editedData.projects : [];
    const education = Array.isArray(editedData.education) ? editedData.education : [];
    const customSections = Array.isArray(editedData.custom_sections) ? editedData.custom_sections : [];

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
            const next: TimelineBlueData = { ...(prev || {}) };
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

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;

        if (over && active.id !== over.id && onSectionOrderChange) {
            const oldIndex = sectionOrder.indexOf(String(active.id));
            const newIndex = sectionOrder.indexOf(String(over.id));
            onSectionOrderChange(arrayMove(sectionOrder, oldIndex, newIndex));
        }
    };

    const allRows = useMemo(() => {
        const formatLabel = (heading: string) => {
            const words = String(heading || "").trim().toUpperCase().split(/\s+/).filter(Boolean);
            if (words.length <= 1) return words.join("");
            return `${words[0]}\n${words.slice(1).join(" ")}`;
        };

        const baseRows: any[] = [];

        if (summary) {
            baseRows.push({
                key: "summary",
                headingFallback: "Professional Summary",
                label: formatLabel(getHeading('summary', 'Professional Summary')),
                content: (
                    <div className="text-[11px] text-slate-600 leading-relaxed">
                        {editMode ? (
                            <EditableText
                                value={summary || "Summary goes here."}
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

        if (skills.length > 0) {
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
                                                onChange={(v) => updateExperience(idx, 'duration', v)}
                                                editMode={editMode}
                                                className="text-[11px] text-slate-500"
                                                as="div"
                                            />
                                        </div>
                                        <div className="mt-1 text-[11px] text-slate-600">
                                            <EditableText
                                                value={company ? String(company) : ""}
                                                onChange={(v) => updateExperience(idx, 'company', v)}
                                                editMode={editMode}
                                                className="inline text-[11px] text-slate-600"
                                                as="span"
                                            />
                                            {(company && city) ? ", " : ""}
                                            <EditableText
                                                value={city ? String(city) : ""}
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
    }, [summary, skills, experience, projects, education, customSections, editMode, updateField, updateExperience, updateEducation, updateProject, updateSkill, getHeading, updateCustomHeading, updateCustomItem, updateCustomBody]);

    // Initialize section order if empty
    useEffect(() => {
        if (editMode && sectionOrder.length === 0 && allRows.length > 0 && onSectionOrderChange) {
            onSectionOrderChange(allRows.map(r => r.key));
        }
    }, [editMode, sectionOrder, allRows, onSectionOrderChange]);

    // Ordered rows for rendering
    const rows = useMemo(() => {
        if (!editMode || sectionOrder.length === 0) {
            return allRows;
        }
        const ordered = sectionOrder
            .map(key => allRows.find(r => r.key === key))
            .filter(Boolean) as Array<{ key: string; label: string; content: React.ReactNode; }>;

        // Add any new rows that aren't in the order yet
        allRows.forEach(row => {
            if (!sectionOrder.includes(row.key)) {
                ordered.push(row);
            }
        });

        return ordered;
    }, [editMode, sectionOrder, allRows]);

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
                        <div className="w-10 h-10 rounded-full border-2 text-slate-700 flex items-center justify-center font-semibold text-sm" style={{ borderColor: 'var(--tv-primary-dark)' }}>
                            {initials}
                        </div>
                        <div className="min-w-0">
                            <EditableText
                                value={name}
                                onChange={(v) => updateField('name', v)}
                                editMode={editMode}
                                className="text-3xl font-light leading-tight text-[color:var(--tv-primary)]"
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
                                collisionDetection={closestCenter}
                                onDragEnd={handleDragEnd}
                            >
                                <SortableContext
                                    items={sectionOrder.length > 0 ? sectionOrder : allRows.map(r => r.key)}
                                    strategy={verticalListSortingStrategy}
                                >
                                    <div className="space-y-10">
                                        {rows.map((row) => (
                                            <EditableSection key={row.key} id={row.key} editMode={editMode} sectionTitle={row.label.replace('\n', ' ')}>
                                                <div className="grid grid-cols-[135px_22px_1fr] gap-x-1">
                                                    <div className="pt-1 text-[11px] font-bold tracking-[0.18em] text-[color:var(--tv-primary-dark)] whitespace-pre-line">
                                                        {typeof (row as any).customIndex === 'number' ? (
                                                            <EditableText
                                                                value={String((row as any).headingRaw || '')}
                                                                onChange={(v) => updateCustomHeading((row as any).customIndex, v)}
                                                                editMode={editMode}
                                                                className="text-[11px] font-bold tracking-[0.18em] uppercase text-[color:var(--tv-primary-dark)]"
                                                                as="div"
                                                            />
                                                        ) : (
                                                            <EditableText
                                                                value={getHeading(String(row.key), String((row as any).headingFallback || row.label.replace('\n', ' ')))}
                                                                onChange={(v) => updateSectionHeading(String(row.key), v)}
                                                                editMode={editMode}
                                                                className="text-[11px] font-bold tracking-[0.18em] uppercase text-[color:var(--tv-primary-dark)]"
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
                            </DndContext>
                        ) : (
                            <div className="space-y-10">
                                {rows.map((row) => (
                                    <div key={row.key} className="grid grid-cols-[135px_22px_1fr] gap-x-1">
                                        <div className="pt-1 text-[11px] font-bold tracking-[0.18em] text-[color:var(--tv-primary-dark)] whitespace-pre-line">
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
            </div>
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


