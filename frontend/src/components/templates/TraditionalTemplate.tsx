import React, { useCallback, useEffect, useMemo, useState } from "react";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import { EditableText } from "./EditableSection";
import AddSectionButton from "./AddSectionButton";
import SortableSectionList, { type SortableSectionRow } from "./SortableSectionList";

export default function TraditionalTemplate({
    content,
    editMode = false,
    onContentChange,
    sectionOrder,
    onSectionOrderChange,
    hiddenSectionKeys,
    onHiddenSectionKeysChange,
}: {
    content: string;
    editMode?: boolean;
    onContentChange?: (changes: any) => void;
    sectionOrder?: string[];
    onSectionOrderChange?: (order: string[]) => void;
    hiddenSectionKeys?: string[];
    onHiddenSectionKeysChange?: (keys: string[]) => void;
}) {
    const sections: any = useMemo(() => parseResumeContent(content), [content]);
    const [editedData, setEditedData] = useState<any>(sections);

    useEffect(() => {
        setEditedData(sections);
    }, [sections]);

    const emit = useCallback((next: any) => {
        if (onContentChange) onContentChange(next);
    }, [onContentChange]);

    const updateField = useCallback((field: string, value: string) => {
        setEditedData((prev: any) => {
            const next = { ...(prev || {}), [field]: value };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateExperience = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev?.experience) ? [...prev.experience] : [];
            updated[index] = { ...(updated[index] || {}), [field]: value };
            const next = { ...(prev || {}), experience: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateEducation = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev?.education) ? [...prev.education] : [];
            updated[index] = { ...(updated[index] || {}), [field]: value };
            const next = { ...(prev || {}), education: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateProject = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev?.projects) ? [...prev.projects] : [];
            updated[index] = { ...(updated[index] || {}), [field]: value };
            const next = { ...(prev || {}), projects: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateSkill = useCallback((index: number, value: string) => {
        setEditedData((prev: any) => {
            const list = normalizeList(prev?.skills);
            const nextList = [...list];
            nextList[index] = value;
            const cleaned = nextList.map((s) => String(s || '').trim()).filter(Boolean);
            const next = { ...(prev || {}), skills: cleaned };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateCustomHeading = useCallback((sectionIndex: number, value: string) => {
        setEditedData((prev: any) => {
            const sectionsArr = Array.isArray(prev?.custom_sections) ? [...prev.custom_sections] : [];
            const current = sectionsArr[sectionIndex] || {};
            sectionsArr[sectionIndex] = { ...(current || {}), heading: value };
            const next = { ...(prev || {}), custom_sections: sectionsArr };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateCustomItem = useCallback((sectionIndex: number, itemIndex: number, field: any, value: string) => {
        setEditedData((prev: any) => {
            const sectionsArr = Array.isArray(prev?.custom_sections) ? [...prev.custom_sections] : [];
            const current = sectionsArr[sectionIndex] || {};
            const items = Array.isArray(current?.items) ? [...current.items] : [];
            const item = items[itemIndex] || {};
            items[itemIndex] = { ...(item || {}), [field]: value };
            sectionsArr[sectionIndex] = { ...(current || {}), items };
            const next = { ...(prev || {}), custom_sections: sectionsArr };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateCustomBody = useCallback((sectionIndex: number, value: string) => {
        setEditedData((prev: any) => {
            const sectionsArr = Array.isArray(prev?.custom_sections) ? [...prev.custom_sections] : [];
            const current = sectionsArr[sectionIndex] || {};
            sectionsArr[sectionIndex] = { ...(current || {}), content: value };
            const next = { ...(prev || {}), custom_sections: sectionsArr };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateSectionHeading = useCallback((key: string, heading: string) => {
        setEditedData((prev: any) => {
            const prevHeadings = (prev && typeof prev.section_headings === 'object' && prev.section_headings) ? prev.section_headings : {};
            const nextHeadings = { ...prevHeadings, [key]: heading };
            const next = { ...(prev || {}), section_headings: nextHeadings };
            emit(next);
            return next;
        });
    }, [emit]);

    const addSection = useCallback(() => {
        setEditedData((prev: any) => {
            const next = { ...(prev || {}) };
            const cur = Array.isArray(next.custom_sections) ? [...next.custom_sections] : [];
            next.custom_sections = [
                ...cur,
                {
                    heading: 'New Section',
                    items: [
                        {
                            title: 'Header',
                            content: '• Bullet 1\n• Bullet 2',
                        },
                    ],
                },
            ];
            emit(next);
            return next;
        });
    }, [emit]);

    const data = editedData || {};
    const showEmpty = !!(editMode && (data as any)?._show_empty_sections);

    const getHeading = useCallback((key: string, fallback: string) => {
        const h = data?.section_headings?.[key];
        return String((typeof h === 'string' && h.trim() !== '') ? h : fallback);
    }, [data]);

    const name = String(data.name || "Your Name").trim();
    const title = String(data.title || "").trim();
    const contactParts = [String(data.location || '').trim(), String(data.phone || '').trim(), String(data.email || '').trim()].filter(Boolean);

    const experience = Array.isArray(data.experience) ? data.experience : [];
    const education = Array.isArray(data.education) ? data.education : [];
    const projects = Array.isArray(data.projects) ? data.projects : [];
    const skills = normalizeList(data.skills);
    const customSections = Array.isArray(data.custom_sections) ? data.custom_sections : [];

    const rows: SortableSectionRow[] = [];

    if (data.summary || showEmpty) {
        rows.push({
            key: 'summary',
            title: getHeading('summary', 'Professional Summary'),
            content: (
                <Section
                    title={getHeading('summary', 'Professional Summary')}
                    editMode={editMode}
                    onTitleChange={(v) => updateSectionHeading('summary', v)}
                >
                    {editMode ? (
                        <EditableText
                            value={String(data.summary)}
                            onChange={(v) => updateField('summary', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className="text-[12px] leading-relaxed text-black/80"
                            as="div"
                            multiline
                        />
                    ) : (
                        <p className="text-[12px] leading-relaxed text-black/80">{String(data.summary)}</p>
                    )}
                </Section>
            ),
        });
    }

    if (experience.length > 0) {
        rows.push({
            key: 'experience',
            title: getHeading('experience', 'Work History'),
            content: (
                <Section
                    title={getHeading('experience', 'Work History')}
                    editMode={editMode}
                    onTitleChange={(v) => updateSectionHeading('experience', v)}
                >
                    <div className="space-y-6">
                        {experience.map((exp: any, idx: number) => (
                            <WorkRow key={idx} exp={exp} editMode={editMode} idx={idx} onUpdate={updateExperience} />
                        ))}
                    </div>
                </Section>
            ),
        });
    }

    if (projects.length > 0) {
        rows.push({
            key: 'projects',
            title: getHeading('projects', 'Projects'),
            content: (
                <Section
                    title={getHeading('projects', 'Projects')}
                    editMode={editMode}
                    onTitleChange={(v) => updateSectionHeading('projects', v)}
                >
                    <div className="space-y-5">
                        {projects.map((proj: any, idx: number) => (
                            <div key={idx}>
                                <div className="flex items-baseline justify-between gap-3">
                                    {editMode ? (
                                        <EditableText
                                            value={String(proj.title || proj.name || 'Project')}
                                            onChange={(v) => updateProject(idx, 'title', v)}
                                            editMode={editMode}
                                            liveUpdate
                                            layoutSafe
                                            className="text-[12px] font-bold text-black"
                                            as="div"
                                        />
                                    ) : (
                                        <div className="text-[12px] font-bold text-black">{String(proj.title || proj.name || 'Project')}</div>
                                    )}
                                    {proj.link ? (
                                        <a
                                            href={String(proj.link)}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="text-[12px] text-black/70 underline underline-offset-2 hover:text-black"
                                        >
                                            Link
                                        </a>
                                    ) : null}
                                </div>
                                {proj.technologies ? (
                                    editMode ? (
                                        <EditableText
                                            value={String(proj.technologies)}
                                            onChange={(v) => updateProject(idx, 'technologies', v)}
                                            editMode={editMode}
                                            liveUpdate
                                            layoutSafe
                                            className="mt-1 text-[12px] text-black/70"
                                            as="div"
                                        />
                                    ) : (
                                        <div className="mt-1 text-[12px] text-black/70">{String(proj.technologies)}</div>
                                    )
                                ) : null}
                                {proj.description ? (
                                    <div className="mt-2">
                                        {editMode ? (
                                            <EditableText
                                                value={String(proj.description)}
                                                onChange={(v) => updateProject(idx, 'description', v)}
                                                editMode={editMode}
                                                liveUpdate
                                                layoutSafe
                                                className="text-[12px] leading-relaxed text-black/80"
                                                as="div"
                                                multiline
                                            />
                                        ) : (
                                            <RenderMaybeBullets
                                                text={String(proj.description)}
                                                forceBullets
                                                className="text-[12px] leading-relaxed text-black/80"
                                            />
                                        )}
                                    </div>
                                ) : null}
                            </div>
                        ))}
                    </div>
                </Section>
            ),
        });
    }

    if (skills.length > 0 || showEmpty) {
        rows.push({
            key: 'skills',
            title: getHeading('skills', 'Skills'),
            content: (
                <Section
                    title={getHeading('skills', 'Skills')}
                    editMode={editMode}
                    onTitleChange={(v) => updateSectionHeading('skills', v)}
                >
                    <div className="grid grid-cols-2 gap-x-10 gap-y-2 text-[12px] text-black/80">
                        {skills.slice(0, 12).map((s, idx) => (
                            <div key={idx} className="flex items-start gap-2">
                                <span className="mt-[6px] w-1.5 h-1.5 rounded-full bg-black/70" />
                                {editMode ? (
                                    <EditableText
                                        value={s}
                                        onChange={(v) => updateSkill(idx, v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        className=""
                                        as="span"
                                    />
                                ) : (
                                    <span>{s}</span>
                                )}
                            </div>
                        ))}
                        {skills.length === 0 ? (
                            <div className="col-span-2 text-[12px] text-black/60">Add skills to populate this section.</div>
                        ) : null}
                    </div>
                </Section>
            ),
        });
    }

    if (education.length > 0) {
        rows.push({
            key: 'education',
            title: getHeading('education', 'Education'),
            content: (
                <Section
                    title={getHeading('education', 'Education')}
                    editMode={editMode}
                    onTitleChange={(v) => updateSectionHeading('education', v)}
                >
                    <div className="space-y-4">
                        {education.map((edu: any, idx: number) => (
                            <EduRow key={idx} edu={edu} editMode={editMode} idx={idx} onUpdate={updateEducation} />
                        ))}
                    </div>
                </Section>
            ),
        });
    }

    if (customSections.length > 0) {
        customSections.forEach((sec: any, idx: number) => {
            const heading = String(sec?.heading || sec?.title || sec?.label || 'Additional').trim();
            rows.push({
                key: `custom_${idx}`,
                title: heading,
                content: (
                    <Section key={idx} title={heading} editMode={editMode} onTitleChange={(v) => updateCustomHeading(idx, v)}>
                        <CustomSectionsRenderer
                            customSections={[sec]}
                            editMode={editMode}
                            onHeadingChange={(sIdx, v) => updateCustomHeading(idx + sIdx, v)}
                            onItemChange={(sIdx, iIdx, field, v) => updateCustomItem(idx + sIdx, iIdx, field, v)}
                            onBodyChange={(sIdx, v) => updateCustomBody(idx + sIdx, v)}
                            showSectionHeadings={false}
                            headingClassName="text-[12px] font-bold text-black"
                            itemTitleClassName="text-[12px] font-bold text-black"
                            itemMetaClassName="text-[12px] text-black/70"
                            itemBodyClassName="text-[12px] leading-relaxed text-black/80"
                        />
                    </Section>
                ),
            });
        });
    }

    return (
        <div className="bg-white rounded-lg shadow-lg ring-1 ring-black/5 overflow-hidden max-w-4xl mx-auto font-serif">
            <div className="px-10 pt-10 pb-7 text-center">
                <div className="text-2xl font-bold tracking-wide text-[#243c6b] uppercase">
                    {editMode ? (
                        <EditableText
                            value={name || "YOUR NAME"}
                            onChange={(v) => updateField('name', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className="text-2xl font-bold tracking-wide text-[#243c6b] uppercase"
                            as="div"
                        />
                    ) : (
                        name || "YOUR NAME"
                    )}
                </div>
                {title ? (
                    editMode ? (
                        <EditableText
                            value={title}
                            onChange={(v) => updateField('title', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className="mt-1 text-sm text-black/70"
                            as="div"
                        />
                    ) : (
                        <div className="mt-1 text-sm text-black/70">{title}</div>
                    )
                ) : null}
                {contactParts.length > 0 ? (
                    <div className="mt-2 text-[12px] text-black/80">
                        {editMode ? (
                            <>
                                <EditableText value={String(data.location || '')} onChange={(v) => updateField('location', v)} editMode={editMode} liveUpdate layoutSafe className="inline" as="span" />
                                {(String(data.location || '').trim() && String(data.phone || '').trim()) ? <span> - </span> : null}
                                <EditableText value={String(data.phone || '')} onChange={(v) => updateField('phone', v)} editMode={editMode} liveUpdate layoutSafe className="inline" as="span" />
                                {(String(data.phone || '').trim() && String(data.email || '').trim()) ? <span> - </span> : null}
                                <EditableText value={String(data.email || '')} onChange={(v) => updateField('email', v)} editMode={editMode} liveUpdate layoutSafe className="inline" as="span" />
                            </>
                        ) : (
                            contactParts.join(' - ')
                        )}
                    </div>
                ) : null}
            </div>

            <div className={`px-10 pb-10 ${editMode ? 'pl-16' : ''}`}>
                {editMode ? (<AddSectionButton onClick={addSection} className="mb-4" />) : null}
                <SortableSectionList
                    rows={rows}
                    editMode={!!editMode}
                    sectionOrder={sectionOrder}
                    onSectionOrderChange={onSectionOrderChange}
                    hiddenSectionKeys={hiddenSectionKeys}
                    onHiddenSectionKeysChange={onHiddenSectionKeysChange}
                />
            </div>
        </div>
    );
}

function Section({
    title,
    children,
    editMode,
    onTitleChange,
}: {
    title: string;
    children: React.ReactNode;
    editMode?: boolean;
    onTitleChange?: (value: string) => void;
}) {
    return (
        <section className="mb-7 last:mb-0">
            <div className="flex items-center gap-4">
                <h2 className="text-sm font-bold tracking-wide text-[#243c6b] uppercase whitespace-nowrap">
                    {editMode ? (
                        <EditableText
                            value={String(title || '')}
                            onChange={(v) => onTitleChange?.(v)}
                            editMode={!!editMode}
                            liveUpdate
                            layoutSafe
                            className="text-sm font-bold tracking-wide text-[#243c6b] uppercase whitespace-nowrap"
                            as="div"
                        />
                    ) : (
                        title
                    )}
                </h2>
                <div className="h-px flex-1 bg-[#243c6b]/60" />
            </div>
            <div className="mt-3">{children}</div>
        </section>
    );
}

function WorkRow({ exp, editMode, idx, onUpdate }: { exp: any; editMode: boolean; idx: number; onUpdate: (index: number, field: string, value: string) => void }) {
    const dates = exp.duration || exp.dates || [exp.start, exp.end].filter(Boolean).join(" to ");
    const role = exp.title || exp.position || "Role";
    const company = exp.company || exp.organization || "";
    const location = exp.location || exp.city || "";
    const companyLine = [company, location].filter(Boolean).join(" — ");

    return (
        <div className="grid grid-cols-12 gap-6">
            <div className="col-span-3 text-[12px] text-black/80 whitespace-nowrap">
                {editMode ? (
                    <EditableText
                        value={String(dates || '')}
                        placeholder="Dates"
                        onChange={(v) => onUpdate(idx, 'duration', v)}
                        editMode={editMode}
                        liveUpdate
                        layoutSafe
                        className="text-[12px] text-black/80 whitespace-nowrap"
                        as="div"
                    />
                ) : (
                    dates
                )}
            </div>
            <div className="col-span-9">
                {editMode ? (
                    <EditableText
                        value={String(role)}
                        onChange={(v) => onUpdate(idx, 'title', v)}
                        editMode={editMode}
                        liveUpdate
                        layoutSafe
                        className="text-[12px] font-bold text-black"
                        as="div"
                    />
                ) : (
                    <div className="text-[12px] font-bold text-black">{String(role)}</div>
                )}
                {editMode ? (
                    <div className="text-[12px] font-bold text-black/80">
                        <EditableText value={String(company)} placeholder="Company" onChange={(v) => onUpdate(idx, 'company', v)} editMode={editMode} liveUpdate layoutSafe className="inline" as="span" />
                        <span> — </span>
                        <EditableText value={String(location)} placeholder="Location" onChange={(v) => onUpdate(idx, 'location', v)} editMode={editMode} liveUpdate layoutSafe className="inline" as="span" />
                    </div>
                ) : (
                    companyLine ? <div className="text-[12px] font-bold text-black/80">{companyLine}</div> : null
                )}
                {exp.description ? (
                    <div className="mt-2">
                        {editMode ? (
                            <EditableText
                                value={String(exp.description)}
                                placeholder="Add bullets or a short description"
                                onChange={(v) => onUpdate(idx, 'description', v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                className="text-[12px] leading-relaxed text-black/80"
                                as="div"
                                multiline
                            />
                        ) : (
                            <RenderMaybeBullets
                                text={exp.description}
                                forceBullets
                                className="text-[12px] leading-relaxed text-black/80"
                            />
                        )}
                    </div>
                ) : null}
            </div>
        </div>
    );
}

function EduRow({ edu, editMode, idx, onUpdate }: { edu: any; editMode: boolean; idx: number; onUpdate: (index: number, field: string, value: string) => void }) {
    const degree = edu.degree || edu.title || "";
    const field = edu.field || edu.focus || edu.major || "";
    const school = edu.institution || edu.school || "";
    const location = edu.location || edu.city || "";
    const date = edu.year || edu.dates || edu.graduationDate || "";

    return (
        <div className="grid grid-cols-12 gap-6">
            <div className="col-span-3 text-[12px] text-black/80 whitespace-nowrap">
                {editMode ? (
                    <EditableText
                        value={String(date || '')}
                        onChange={(v) => onUpdate(idx, 'year', v)}
                        editMode={editMode}
                        liveUpdate
                        layoutSafe
                        className="text-[12px] text-black/80 whitespace-nowrap"
                        as="div"
                    />
                ) : (
                    date
                )}
            </div>
            <div className="col-span-9 text-[12px] text-black/85">
                <div className="font-bold">
                    {editMode ? (
                        <>
                            <EditableText value={String(degree || school || 'Education')} onChange={(v) => onUpdate(idx, 'degree', v)} editMode={editMode} liveUpdate layoutSafe className="inline" as="span" />
                            {field ? <span className="text-black/70"> — </span> : null}
                            {field ? <EditableText value={String(field)} onChange={(v) => onUpdate(idx, 'field', v)} editMode={editMode} liveUpdate layoutSafe className="inline text-black/70" as="span" /> : null}
                        </>
                    ) : (
                        <>
                            {String(degree || school || "Education")}
                            {field ? <span className="text-black/70"> — {String(field)}</span> : null}
                        </>
                    )}
                </div>
                {school && degree ? (
                    editMode ? (
                        <EditableText value={String(school)} onChange={(v) => onUpdate(idx, 'institution', v)} editMode={editMode} liveUpdate layoutSafe className="font-bold text-black/75" as="div" />
                    ) : (
                        <div className="font-bold text-black/75">{String(school)}</div>
                    )
                ) : null}
                {location ? (
                    editMode ? (
                        <EditableText value={String(location)} onChange={(v) => onUpdate(idx, 'location', v)} editMode={editMode} liveUpdate layoutSafe className="text-black/70" as="div" />
                    ) : (
                        <div className="text-black/70">{String(location)}</div>
                    )
                ) : null}
            </div>
        </div>
    );
}

function normalizeList(value: any): string[] {
    if (Array.isArray(value)) return value.map((v) => String(v)).map((s) => s.trim()).filter(Boolean);
    if (typeof value === "string") {
        return value
            .split(/[,•]|\\n/g)
            .map((s) => s.trim())
            .filter(Boolean);
    }
    return [];
}



