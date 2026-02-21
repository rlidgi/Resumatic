import React, { useCallback, useEffect, useMemo, useState } from "react";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import { EditableText } from "./EditableSection";
import AddSectionButton from "./AddSectionButton";
import SortableSectionList, { type SortableSectionRow } from "./SortableSectionList";

export default function BoldProfessionalTemplate({
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
        onContentChange?.(next);
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

    const updateProject = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev?.projects) ? [...prev.projects] : [];
            updated[index] = { ...(updated[index] || {}), [field]: value };
            const next = { ...(prev || {}), projects: updated };
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

    const updateCertification = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const certs = Array.isArray(prev?.certifications)
                ? [...prev.certifications]
                : normalizeCerts(prev?.certifications);
            const current = certs[index] || {};
            certs[index] = typeof current === 'string' ? { title: value } : { ...(current || {}), [field]: value };
            const next = { ...(prev || {}), certifications: certs };
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
    const { first, last } = splitName(name);
    const initials = getInitials(name);

    const contactParts = [data.location, data.phone, data.email].filter(Boolean).map(String);

    const skills: string[] = Array.isArray(data.skills) ? data.skills.map(String) : normalizeList(data.skills);
    const ratingsFromData: Record<string, number> = (data.skill_ratings && typeof data.skill_ratings === "object")
        ? data.skill_ratings
        : {};
    const [localRatings, setLocalRatings] = useState<Record<string, number>>(ratingsFromData);

    useEffect(() => {
        setLocalRatings(ratingsFromData);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [content]);

    const skillPairs = skills.map((s) => ({
        name: s,
        level: typeof localRatings[s] === "number" ? localRatings[s] : guessLevel(s),
    }));

    const experience = Array.isArray(data.experience) ? data.experience : [];
    const projects = Array.isArray(data.projects) ? data.projects : [];
    const education = Array.isArray(data.education) ? data.education : [];
    const certifications = Array.isArray(data.certifications) ? data.certifications : normalizeCerts(data.certifications);
    const customSections = Array.isArray(data.custom_sections) ? data.custom_sections : [];

    const bodyRows: SortableSectionRow[] = useMemo(() => {
        const rows: SortableSectionRow[] = [];

        if (editMode || data.summary) {
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
                                value={String(data.summary || '')}
                                onChange={(v) => updateField('summary', v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                as="div"
                                className="text-sm leading-relaxed text-black/80"
                                multiline
                            />
                        ) : (
                            <p className="text-sm leading-relaxed text-black/80">{String(data.summary)}</p>
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
                        <div className="space-y-5">
                            {experience.map((exp: any, idx: number) => (
                                <WorkItem key={idx} exp={exp} editMode={editMode} idx={idx} onUpdate={updateExperience} />
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
                                    <div className="flex items-baseline justify-between gap-4">
                                        {editMode ? (
                                            <EditableText
                                                value={String(proj.title || proj.name || 'Project')}
                                                onChange={(v) => updateProject(idx, 'title', v)}
                                                editMode={editMode}
                                                liveUpdate
                                                layoutSafe
                                                as="div"
                                                className="font-semibold text-sm text-black"
                                            />
                                        ) : (
                                            <div className="font-semibold text-sm text-black">{String(proj.title || proj.name || 'Project')}</div>
                                        )}
                                        {proj.link ? (
                                            <a
                                                href={String(proj.link)}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="text-sm text-black/70 whitespace-nowrap underline underline-offset-2 hover:text-black"
                                            >
                                                Link
                                            </a>
                                        ) : null}
                                    </div>
                                    {proj.technologies ? (
                                        editMode ? (
                                            <EditableText value={String(proj.technologies)} onChange={(v) => updateProject(idx, 'technologies', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-sm text-black/70" />
                                        ) : (
                                            <div className="text-sm text-black/70">{String(proj.technologies)}</div>
                                        )
                                    ) : null}
                                    {proj.description ? (
                                        <div className="mt-2">
                                            {editMode ? (
                                                <EditableText value={String(proj.description)} onChange={(v) => updateProject(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-sm leading-relaxed text-black/80" multiline />
                                            ) : (
                                                <RenderMaybeBullets
                                                    text={String(proj.description)}
                                                    forceBullets
                                                    className="text-sm leading-relaxed text-black/80"
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

        if (skillPairs.length > 0 || showEmpty) {
            rows.push({
                key: 'skills',
                title: getHeading('skills', 'Skills'),
                content: (
                    <Section
                        title={getHeading('skills', 'Skills')}
                        editMode={editMode}
                        onTitleChange={(v) => updateSectionHeading('skills', v)}
                    >
                        <div className="grid grid-cols-2 gap-x-10 gap-y-4">
                            {skillPairs.slice(0, 10).map((s, idx) => (
                                <SkillRow
                                    key={idx}
                                    name={s.name}
                                    level={s.level}
                                    editable={editMode}
                                    onSetCount={(count) => {
                                        const next = { ...(localRatings || {}) };
                                        next[s.name] = count; // store as 1..8
                                        setLocalRatings(next);
                                        setEditedData((prev: any) => {
                                            const updated = { ...(prev || {}), skill_ratings: next };
                                            emit(updated);
                                            return updated;
                                        });
                                    }}
                                />
                            ))}
                            {skillPairs.length === 0 ? (
                                <div className="col-span-2 text-sm text-black/60">Add skills to populate this section.</div>
                            ) : null}
                        </div>
                    </Section>
                ),
            });
        }

        if (certifications.length > 0) {
            rows.push({
                key: 'certifications',
                title: getHeading('certifications', 'Certifications'),
                content: (
                    <Section
                        title={getHeading('certifications', 'Certifications')}
                        editMode={editMode}
                        onTitleChange={(v) => updateSectionHeading('certifications', v)}
                    >
                        <ul className="list-disc pl-5 text-sm text-black/80 space-y-2">
                            {certifications.slice(0, 6).map((c: any, idx: number) => (
                                <li key={idx}>
                                    {editMode ? (
                                        <>
                                            <EditableText value={String(c.title || c.name || c).trim()} onChange={(v) => updateCertification(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                            <span className="text-black/70"> — </span>
                                            <EditableText value={String(c.issuer || '')} onChange={(v) => updateCertification(idx, 'issuer', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline text-black/70" />
                                        </>
                                    ) : (
                                        <>
                                            {String(c.title || c.name || c).trim()}
                                            {c.issuer ? <span className="text-black/70"> — {String(c.issuer)}</span> : null}
                                        </>
                                    )}
                                </li>
                            ))}
                        </ul>
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
                        <div className="space-y-3">
                            {education.map((edu: any, idx: number) => (
                                <EduItem key={idx} edu={edu} editMode={editMode} idx={idx} onUpdate={updateEducation} />
                            ))}
                        </div>
                    </Section>
                ),
            });
        }

        if (customSections.length > 0) {
            for (let idx = 0; idx < customSections.length; idx++) {
                const sec: any = customSections[idx];
                const heading = String(sec?.heading || sec?.title || sec?.label || 'Additional').trim();
                rows.push({
                    key: `custom_${idx}`,
                    title: heading,
                    content: (
                        <Section title={heading} editMode={editMode} onTitleChange={(v) => updateCustomHeading(idx, v)}>
                            <CustomSectionsRenderer
                                customSections={[sec]}
                                editMode={editMode}
                                onHeadingChange={(sIdx, v) => updateCustomHeading(idx + sIdx, v)}
                                onItemChange={(sIdx, iIdx, field, v) => updateCustomItem(idx + sIdx, iIdx, field, v)}
                                onBodyChange={(sIdx, v) => updateCustomBody(idx + sIdx, v)}
                                showSectionHeadings={false}
                                headingClassName="text-sm font-semibold text-black"
                                itemTitleClassName="text-sm font-semibold text-black"
                                itemMetaClassName="text-sm text-black/70"
                                itemBodyClassName="text-sm leading-relaxed text-black/80"
                            />
                        </Section>
                    ),
                });
            }
        }

        return rows;
    }, [
        certifications,
        customSections,
        data.summary,
        editMode,
        education,
        emit,
        experience,
        getHeading,
        localRatings,
        projects,
        showEmpty,
        skillPairs,
        updateCertification,
        updateCustomBody,
        updateCustomHeading,
        updateCustomItem,
        updateEducation,
        updateExperience,
        updateField,
        updateProject,
        updateSectionHeading,
    ]);

    return (
        <div className="bg-white rounded-lg shadow-lg ring-1 ring-black/5 overflow-hidden max-w-4xl mx-auto font-sans">
            {editMode ? (<AddSectionButton onClick={addSection} className="p-4 pb-0" />) : null}
            <div className="px-10 pt-9 pb-6">
                <div className="flex items-center gap-5">
                    <div className="w-14 h-14 border-2 border-black grid place-items-center font-extrabold tracking-wide text-xl leading-none">
                        {initials}
                    </div>
                    <div className="flex items-baseline gap-3 flex-wrap">
                        <div className="text-4xl font-extrabold tracking-tight text-black uppercase">
                            {editMode ? (
                                <EditableText
                                    value={first}
                                    onChange={(v) => updateField('name', `${v} ${last}`.trim())}
                                    editMode={editMode}
                                    liveUpdate
                                    layoutSafe
                                    as="span"
                                    className="inline"
                                />
                            ) : (
                                first
                            )}
                        </div>
                        <div className="text-4xl font-extrabold tracking-tight uppercase text-[#f36b1c]">
                            {editMode ? (
                                <EditableText
                                    value={last}
                                    onChange={(v) => updateField('name', `${first} ${v}`.trim())}
                                    editMode={editMode}
                                    liveUpdate
                                    layoutSafe
                                    as="span"
                                    className="inline"
                                />
                            ) : (
                                last
                            )}
                        </div>
                    </div>
                </div>

                {(editMode || contactParts.length > 0) && (
                    <div className="mt-6 bg-black text-white text-sm px-4 py-2 font-semibold">
                        {editMode ? (
                            <>
                                <EditableText value={String(data.location || '')} onChange={(v) => updateField('location', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                <span> | </span>
                                <EditableText value={String(data.phone || '')} onChange={(v) => updateField('phone', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                <span> | </span>
                                <EditableText value={String(data.email || '')} onChange={(v) => updateField('email', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                            </>
                        ) : (
                            contactParts.join(" | ")
                        )}
                    </div>
                )}
            </div>

            <div className={`px-10 pb-10 ${editMode ? 'pl-16' : ''}`}>
                <SortableSectionList
                    rows={bodyRows}
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

function Section({ title, children, editMode, onTitleChange }: { title: string; children: React.ReactNode; editMode?: boolean; onTitleChange?: (value: string) => void }) {
    return (
        <section className="mb-7 last:mb-0">
            <div className="flex items-end justify-between gap-4">
                <h2 className="text-lg font-bold text-black">
                    {editMode ? (
                        <EditableText
                            value={String(title || '')}
                            onChange={(v) => onTitleChange?.(v)}
                            editMode={!!editMode}
                            liveUpdate
                            layoutSafe
                            as="div"
                            className="text-lg font-bold text-black"
                        />
                    ) : (
                        title
                    )}
                </h2>
            </div>
            <div className="h-px bg-[#f36b1c] mt-2 mb-3" />
            {children}
        </section>
    );
}

function WorkItem({ exp, editMode, idx, onUpdate }: { exp: any; editMode: boolean; idx: number; onUpdate: (index: number, field: string, value: string) => void }) {
    const role = exp.title || exp.position || "Role";
    const dates = exp.duration || exp.dates || [exp.start, exp.end].filter(Boolean).join(" to ");
    const company = exp.company || exp.organization || "";
    const location = exp.location || exp.city || "";

    return (
        <div>
            <div className="flex items-baseline justify-between gap-4">
                {editMode ? (
                    <EditableText value={String(role)} onChange={(v) => onUpdate(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="font-semibold text-sm text-black" />
                ) : (
                    <div className="font-semibold text-sm text-black">{String(role)}</div>
                )}
                {editMode ? (
                    <EditableText value={String(dates || '')} placeholder="Dates" onChange={(v) => onUpdate(idx, 'duration', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-sm text-black/70 whitespace-nowrap" />
                ) : (
                    dates ? <div className="text-sm text-black/70 whitespace-nowrap">{String(dates)}</div> : null
                )}
            </div>
            {(editMode || company || location) && (
                <div className="text-sm text-black/80 font-semibold">
                    {editMode ? (
                        <>
                            <EditableText value={String(company)} placeholder="Company" onChange={(v) => onUpdate(idx, 'company', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                            <span className="font-semibold text-black/70"> – </span>
                            <EditableText value={String(location)} placeholder="Location" onChange={(v) => onUpdate(idx, 'location', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline font-semibold text-black/70" />
                        </>
                    ) : (
                        <>
                            {String(company)}
                            {location ? <span className="font-semibold text-black/70"> – {String(location)}</span> : null}
                        </>
                    )}
                </div>
            )}
            {exp.description ? (
                <div className="mt-2">
                    {editMode ? (
                        <EditableText value={String(exp.description)} placeholder="Add bullets or a short description" onChange={(v) => onUpdate(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-sm leading-relaxed text-black/80" multiline />
                    ) : (
                        <RenderMaybeBullets
                            text={exp.description}
                            forceBullets
                            className="text-sm leading-relaxed text-black/80"
                        />
                    )}
                </div>
            ) : null}
        </div>
    );
}

function SkillRow({
    name,
    level,
    editable,
    onSetCount,
}: {
    name: string;
    level: number;
    editable: boolean;
    onSetCount: (count: number) => void;
}) {
    // "level" is expected in [0..8] from saved ratings, or [0..1] from guessLevel fallback.
    const normalized = level > 1 ? (level / 8) : level;
    const count = Math.max(0, Math.min(8, Math.round(normalized * 8)));
    return (
        <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-black/85">{name}</div>
            <div className="flex items-center gap-1">
                {Array.from({ length: 8 }).map((_, idx) => (
                    <span
                        key={idx}
                        onClick={
                            editable
                                ? (e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    onSetCount(idx + 1);
                                }
                                : undefined
                        }
                        title={editable ? `Set ${name} level to ${idx + 1}/8` : undefined}
                        className={`w-2.5 h-2.5 ${idx < count ? "bg-[#f36b1c]" : "bg-[#f2b38b]"} ${editable ? "cursor-pointer ring-1 ring-black/10 hover:ring-black/40" : ""}`}
                    />
                ))}
            </div>
        </div>
    );
}

function EduItem({ edu, editMode, idx, onUpdate }: { edu: any; editMode: boolean; idx: number; onUpdate: (index: number, field: string, value: string) => void }) {
    const degree = edu.degree || edu.title || "";
    const field = edu.field || edu.focus || edu.major || "";
    const school = edu.institution || edu.school || "";
    const location = edu.location || edu.city || "";
    const date = edu.year || edu.dates || edu.graduationDate || "";

    return (
        <div className="flex items-baseline justify-between gap-4">
            <div className="text-sm text-black/85">
                {editMode ? (
                    <>
                        <EditableText value={String(degree || school || 'Education')} onChange={(v) => onUpdate(idx, 'degree', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline font-semibold" />
                        {field ? <span className="text-black/70">: </span> : null}
                        {field ? <EditableText value={String(field)} onChange={(v) => onUpdate(idx, 'field', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline text-black/70" /> : null}
                        {school && degree ? <span className="text-black/70"> — </span> : null}
                        {school && degree ? <EditableText value={String(school)} onChange={(v) => onUpdate(idx, 'institution', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline text-black/70" /> : null}
                        {location ? <span className="text-black/70"> • </span> : null}
                        {location ? <EditableText value={String(location)} onChange={(v) => onUpdate(idx, 'location', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline text-black/70" /> : null}
                    </>
                ) : (
                    <>
                        <span className="font-semibold">{String(degree || school || "Education")}</span>
                        {field ? <span className="text-black/70">: {String(field)}</span> : null}
                        {school && degree ? <span className="text-black/70"> — {String(school)}</span> : null}
                        {location ? <span className="text-black/70"> • {String(location)}</span> : null}
                    </>
                )}
            </div>
            {date ? (
                editMode ? (
                    <EditableText value={String(date)} onChange={(v) => onUpdate(idx, 'year', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-sm text-black/70 whitespace-nowrap" />
                ) : (
                    <div className="text-sm text-black/70 whitespace-nowrap">{String(date)}</div>
                )
            ) : null}
        </div>
    );
}

function splitName(full: string): { first: string; last: string } {
    const parts = String(full || "").trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return { first: "YOUR", last: "NAME" };
    if (parts.length === 1) return { first: parts[0].toUpperCase(), last: "" };
    return { first: parts[0].toUpperCase(), last: parts.slice(1).join(" ").toUpperCase() };
}

function getInitials(name: string): string {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return "YN";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function guessLevel(name: string): number {
    const s = (name || "").toLowerCase().trim();
    let acc = 0;
    for (let i = 0; i < s.length; i++) acc = (acc * 31 + s.charCodeAt(i)) >>> 0;
    return 0.45 + ((acc % 46) / 100); // [0.45..0.91]
}

function normalizeList(value: any): string[] {
    if (Array.isArray(value)) return value.map((v) => String(v)).filter(Boolean);
    if (typeof value === "string") {
        return value
            .split(/[,•]|\\n/g)
            .map((s) => s.trim())
            .filter(Boolean);
    }
    return [];
}

function normalizeCerts(value: any): any[] {
    if (Array.isArray(value)) return value;
    if (typeof value === "string") {
        return normalizeList(value).map((t) => ({ title: t }));
    }
    return [];
}


