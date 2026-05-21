import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Mail, Phone, MapPin } from "lucide-react";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import { EditableText } from "./EditableSection";
import AddSectionButton from "./AddSectionButton";
import SortableSectionList, { type SortableSectionRow } from "./SortableSectionList";

export default function ElegantTemplate({
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

    const updateField = useCallback((field: string, value: any) => {
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

    const updateLanguage = useCallback((index: number, value: string) => {
        setEditedData((prev: any) => {
            const list = normalizeList(prev?.languages);
            const nextList = [...list];
            nextList[index] = value;
            const cleaned = nextList.map((s) => String(s || '').trim()).filter(Boolean);
            const next = { ...(prev || {}), languages: cleaned };
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

    const getHeading = useCallback((key: string, fallback: string) => {
        const h = data?.section_headings?.[key];
        return String((typeof h === 'string' && h.trim() !== '') ? h : fallback);
    }, [data]);

    const skills = normalizeList(data.skills);
    const objective = data.summary || data.objective || data.profile || "";
    const accomplishments = extractAccomplishments(data);
    const languages = normalizeLanguages(data.languages);
    const projects = Array.isArray(data.projects) ? data.projects : [];
    const customSections = Array.isArray(data.custom_sections) ? data.custom_sections : [];

    const mainRows: SortableSectionRow[] = useMemo(() => {
        const rows: SortableSectionRow[] = [];

        if (objective) {
            rows.push({
                key: 'summary',
                title: getHeading('summary', 'RESUME OBJECTIVE'),
                content: (
                    <MainSection title={getHeading('summary', 'RESUME OBJECTIVE')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('summary', v)}>
                        {editMode ? (
                            <EditableText
                                value={String(objective)}
                                onChange={(v) => updateField('summary', v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                as="div"
                                className="text-[11px] leading-relaxed text-[#3b2a52]"
                                multiline
                            />
                        ) : (
                            <p className="text-[11px] leading-relaxed text-[#3b2a52]">{objective}</p>
                        )}
                    </MainSection>
                ),
            });
        }

        if (Array.isArray(data.experience) && data.experience.length > 0) {
            rows.push({
                key: 'experience',
                title: getHeading('experience', 'WORK EXPERIENCE'),
                content: (
                    <MainSection title={getHeading('experience', 'WORK EXPERIENCE')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('experience', v)}>
                        <div className="space-y-4">
                            {data.experience.map((exp: any, idx: number) => (
                                <div key={idx}>
                                    <div className="text-[12px] font-semibold">
                                        {editMode ? (
                                            <>
                                                <EditableText value={String(exp.company || exp.organization || '')} onChange={(v) => updateExperience(idx, 'company', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                <span> - </span>
                                                <EditableText value={String(exp.title || exp.position || 'Role')} onChange={(v) => updateExperience(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                            </>
                                        ) : (
                                            [exp.company || exp.organization, exp.title || exp.position || "Role"]
                                                .filter(Boolean)
                                                .join(" - ")
                                        )}
                                    </div>
                                    <div className="text-[10px] text-[#6c5a86]">
                                        {editMode ? (
                                            <>
                                                <EditableText value={String(exp.location || exp.city || '')} onChange={(v) => updateExperience(idx, 'location', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                <span> • </span>
                                                <EditableText value={String(exp.duration || exp.dates || [exp.start, exp.end].filter(Boolean).join(" - ") || '')} onChange={(v) => updateExperience(idx, 'duration', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                            </>
                                        ) : (
                                            [exp.location || exp.city, exp.duration || exp.dates || [exp.start, exp.end].filter(Boolean).join(" - ")]
                                                .filter(Boolean)
                                                .join(" • ")
                                        )}
                                    </div>
                                    {exp.description && (
                                        <div className="mt-2">
                                            {editMode ? (
                                                <EditableText value={String(exp.description)} onChange={(v) => updateExperience(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-[11px] leading-relaxed text-[#3b2a52]" multiline />
                                            ) : (
                                                <RenderMaybeBullets
                                                    text={exp.description}
                                                    forceBullets
                                                    className="text-[11px] leading-relaxed text-[#3b2a52]"
                                                />
                                            )}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </MainSection>
                ),
            });
        }

        if (projects.length > 0) {
            rows.push({
                key: 'projects',
                title: getHeading('projects', 'PROJECTS'),
                content: (
                    <MainSection title={getHeading('projects', 'PROJECTS')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('projects', v)}>
                        <div className="space-y-4">
                            {projects.map((proj: any, idx: number) => (
                                <div key={idx}>
                                    <div className="text-[12px] font-semibold flex items-baseline justify-between gap-4">
                                        {editMode ? (
                                            <EditableText value={String(proj.title || proj.name || 'Project')} onChange={(v) => updateProject(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                        ) : (
                                            <span>{String(proj.title || proj.name || 'Project')}</span>
                                        )}
                                        {proj.link ? (
                                            <a
                                                href={String(proj.link)}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="text-[10px] text-[#6c5a86] underline underline-offset-2 hover:text-[#3b2a52] whitespace-nowrap"
                                            >
                                                Link
                                            </a>
                                        ) : null}
                                    </div>
                                    {proj.technologies ? (
                                        editMode ? (
                                            <EditableText value={String(proj.technologies)} onChange={(v) => updateProject(idx, 'technologies', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-[10px] text-[#6c5a86]" />
                                        ) : (
                                            <div className="text-[10px] text-[#6c5a86]">{String(proj.technologies)}</div>
                                        )
                                    ) : null}
                                    {(editMode || proj.description) ? (
                                        <div className="mt-2">
                                            {editMode ? (
                                                <EditableText value={String(proj.description)} onChange={(v) => updateProject(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-[11px] leading-relaxed text-[#3b2a52]" multiline />
                                            ) : (
                                                <RenderMaybeBullets
                                                    text={String(proj.description)}
                                                    forceBullets
                                                    className="text-[11px] leading-relaxed text-[#3b2a52]"
                                                />
                                            )}
                                        </div>
                                    ) : null}
                                </div>
                            ))}
                        </div>
                    </MainSection>
                ),
            });
        }

        if (accomplishments.length > 0) {
            rows.push({
                key: 'accomplishments',
                title: getHeading('accomplishments', 'ACCOMPLISHMENTS'),
                content: (
                    <MainSection title={getHeading('accomplishments', 'ACCOMPLISHMENTS')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('accomplishments', v)}>
                        {editMode ? (
                            <EditableText
                                value={accomplishments.join("\n")}
                                onChange={(v) => updateField('accomplishments', normalizeList(v))}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                as="div"
                                className="text-[11px] leading-relaxed text-[#3b2a52]"
                                multiline
                            />
                        ) : (
                            <RenderMaybeBullets
                                text={accomplishments.join("\n")}
                                forceBullets
                                className="text-[11px] leading-relaxed text-[#3b2a52]"
                            />
                        )}
                    </MainSection>
                ),
            });
        }

        if (languages.length > 0) {
            rows.push({
                key: 'languages',
                title: getHeading('languages', 'LANGUAGES'),
                content: (
                    <MainSection title={getHeading('languages', 'LANGUAGES')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('languages', v)}>
                        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-[11px]">
                            {languages.map((lang, idx) => (
                                <div key={idx} className="flex items-center justify-between gap-3">
                                    {editMode ? (
                                        <EditableText value={String(lang.name)} onChange={(v) => updateLanguage(idx, v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline text-[#3b2a52]" />
                                    ) : (
                                        <span className="text-[#3b2a52]">{lang.name}</span>
                                    )}
                                    <LanguageDots filled={lang.dots} />
                                </div>
                            ))}
                        </div>
                    </MainSection>
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
                        <MainSection title={heading} editMode={editMode} onTitleChange={(v) => updateCustomHeading(idx, v)}>
                            <CustomSectionsRenderer
                                customSections={[sec]}
                                editMode={editMode}
                                onHeadingChange={(sIdx, v) => updateCustomHeading(idx + sIdx, v)}
                                onItemChange={(sIdx, iIdx, field, v) => updateCustomItem(idx + sIdx, iIdx, field, v)}
                                onBodyChange={(sIdx, v) => updateCustomBody(idx + sIdx, v)}
                                showSectionHeadings={false}
                                headingClassName="text-[12px] font-semibold text-[#3b2a52]"
                                itemTitleClassName="text-[12px] font-semibold text-[#3b2a52]"
                                itemMetaClassName="text-[10px] text-[#6c5a86]"
                                itemBodyClassName="text-[11px] leading-relaxed text-[#3b2a52]"
                            />
                        </MainSection>
                    ),
                });
            }
        }

        return rows;
    }, [
        accomplishments,
        customSections,
        data.experience,
        editMode,
        getHeading,
        languages,
        objective,
        projects,
        updateCustomBody,
        updateCustomHeading,
        updateCustomItem,
        updateExperience,
        updateField,
        updateLanguage,
        updateProject,
        updateSectionHeading,
    ]);

    const initials = formatInitials(getInitials(data.name || "Your Name"));

    return (
        <div className="bg-[#f6f1fb] rounded-lg shadow-lg ring-1 ring-black/5 overflow-hidden max-w-5xl mx-auto font-serif">
            {editMode ? (<AddSectionButton onClick={addSection} className="p-4 pb-0" />) : null}
            <div className="grid grid-cols-12">
                {/* LEFT SIDEBAR */}
                <aside className="col-span-4 bg-[#b8a4dc] text-[#2a1e3d] px-6 py-7">
                    <div className="flex items-center gap-3 mb-6">
                        <div
                            className="w-[62px] h-[62px] bg-[#7a5bb0] shadow-sm grid place-items-center"
                            style={{
                                clipPath: "polygon(25% 4%, 75% 4%, 100% 50%, 75% 96%, 25% 96%, 0% 50%)",
                            }}
                        >
                            <div
                                className="w-[52px] h-[52px] bg-[#6b4c9a] text-white grid place-items-center"
                                style={{
                                    clipPath: "polygon(25% 4%, 75% 4%, 100% 50%, 75% 96%, 25% 96%, 0% 50%)",
                                    fontFamily:
                                        '"Brush Script MT","Apple Chancery","Lucida Handwriting","Segoe Script",cursive',
                                    fontWeight: 400,
                                    letterSpacing: "0.02em",
                                    fontSize: "18px",
                                }}
                            >
                                {initials}
                            </div>
                        </div>
                    </div>

                    <div className="mb-6">
                        <div className="text-xl font-semibold uppercase tracking-[0.16em] text-white">
                            {editMode ? (
                                <EditableText
                                    value={String(data.name || 'Your Name')}
                                    onChange={(v) => updateField('name', v)}
                                    editMode={editMode}
                                    liveUpdate
                                    layoutSafe
                                    as="div"
                                    className="text-xl font-semibold uppercase tracking-[0.16em] text-white"
                                />
                            ) : (
                                data.name || "Your Name"
                            )}
                        </div>
                    </div>

                    {(editMode || data.email || data.phone || data.location) && (
                        <div className="space-y-2 text-[11px] text-white/90">
                            {(editMode || data.email) && (
                                <SideContactRow icon={<Mail className="w-3.5 h-3.5" />} value={String(data.email || '')} editMode={editMode} onChange={(v) => updateField('email', v)} />
                            )}
                            {(editMode || data.phone) && (
                                <SideContactRow icon={<Phone className="w-3.5 h-3.5" />} value={String(data.phone || '')} editMode={editMode} onChange={(v) => updateField('phone', v)} />
                            )}
                            {(editMode || data.location) && (
                                <SideContactRow icon={<MapPin className="w-3.5 h-3.5" />} value={String(data.location || '')} editMode={editMode} onChange={(v) => updateField('location', v)} />
                            )}
                        </div>
                    )}

                    {Array.isArray(data.education) && data.education.length > 0 && (
                        <SideSection title={getHeading('education', 'EDUCATION')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('education', v)}>
                            <div className="space-y-3">
                                {data.education.map((edu: any, idx: number) => {
                                    const school = edu.institution || edu.school || edu.organization || "";
                                    const degree = edu.degree || edu.title || "";
                                    const field = edu.field || edu.focus || "";
                                    const dates = edu.year || edu.dates || edu.graduationDate || "";
                                    const location = edu.location || edu.city || "";
                                    return (
                                        <div key={idx} className="text-[11px] text-white/90">
                                            {editMode ? (
                                                <EditableText value={String(school)} onChange={(v) => updateEducation(idx, 'institution', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="font-semibold text-white" />
                                            ) : (
                                                <div className="font-semibold text-white">{school}</div>
                                            )}
                                            {(location || dates) && (
                                                <div className="text-white/80">{[location, dates].filter(Boolean).join(" • ")}</div>
                                            )}
                                            <div className="text-white/90 italic">
                                                {editMode ? (
                                                    <>
                                                        <EditableText value={String(degree)} onChange={(v) => updateEducation(idx, 'degree', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                        {field ? <span> </span> : null}
                                                        <EditableText value={String(field)} onChange={(v) => updateEducation(idx, 'field', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                    </>
                                                ) : (
                                                    [degree, field].filter(Boolean).join(" ")
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </SideSection>
                    )}

                    {skills.length > 0 && (
                        <SideSection title={getHeading('skills', 'SKILLS')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('skills', v)}>
                            <div className="space-y-2">
                                {skills.map((skill, idx) => (
                                    <div key={idx} className="flex items-center gap-2 text-[11px] text-white/90">
                                        <span className="w-1.5 h-1.5 rounded-full bg-white/80" />
                                        {editMode ? (
                                            <EditableText value={skill} onChange={(v) => updateSkill(idx, v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                        ) : (
                                            <span>{skill}</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </SideSection>
                    )}
                </aside>

                {/* RIGHT CONTENT */}
                <section className={`col-span-8 bg-[#f6f1fb] px-7 py-7 text-[#3b2a52] ${editMode ? 'pl-16' : ''}`}>
                    <SortableSectionList
                        rows={mainRows}
                        editMode={!!editMode}
                        sectionOrder={sectionOrder}
                        onSectionOrderChange={onSectionOrderChange}
                        hiddenSectionKeys={hiddenSectionKeys}
                        onHiddenSectionKeysChange={onHiddenSectionKeysChange}
                    />
                </section>
            </div>
        </div>
    );
}

function SideSection({ title, children, editMode, onTitleChange }: { title: string; children: React.ReactNode; editMode?: boolean; onTitleChange?: (value: string) => void }) {
    return (
        <section className="mt-6">
            <h3 className="text-[11px] font-semibold tracking-[0.2em] uppercase text-white">
                {editMode ? (
                    <EditableText
                        value={String(title || '')}
                        onChange={(v) => onTitleChange?.(v)}
                        editMode={!!editMode}
                        liveUpdate
                        layoutSafe
                        as="div"
                        className="text-[11px] font-semibold tracking-[0.2em] uppercase text-white"
                    />
                ) : (
                    title
                )}
            </h3>
            <div className="h-px bg-white/40 my-3" />
            {children}
        </section>
    );
}

function SideContactRow({ icon, value, editMode, onChange }: { icon: React.ReactNode; value: string; editMode?: boolean; onChange?: (value: string) => void }) {
    return (
        <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-white/85 text-[#6b4c9a] grid place-items-center">
                <span className="scale-90">{icon}</span>
            </span>
            {editMode ? (
                <EditableText value={String(value || '')} onChange={(v) => onChange && onChange(v)} editMode={!!editMode} liveUpdate layoutSafe as="span" className="break-words inline" />
            ) : (
                <span className="break-words">{value}</span>
            )}
        </div>
    );
}

function MainSection({ title, children, editMode, onTitleChange }: { title: string; children: React.ReactNode; editMode?: boolean; onTitleChange?: (value: string) => void }) {
    return (
        <section className="mb-5 last:mb-0">
            <h2 className="text-[11px] font-semibold tracking-[0.22em] uppercase text-[#3b2a52]">
                {editMode ? (
                    <EditableText
                        value={String(title || '')}
                        onChange={(v) => onTitleChange?.(v)}
                        editMode={!!editMode}
                        liveUpdate
                        layoutSafe
                        as="div"
                        className="text-[11px] font-semibold tracking-[0.22em] uppercase text-[#3b2a52]"
                    />
                ) : (
                    title
                )}
            </h2>
            <div className="h-px bg-[#d7c9ec] my-3" />
            {children}
        </section>
    );
}

function LanguageDots({ filled }: { filled: number }) {
    const dots = Array.from({ length: 5 }).map((_, idx) => idx < filled);
    return (
        <div className="flex items-center gap-1">
            {dots.map((isFilled, idx) => (
                <span
                    key={idx}
                    className={`w-2 h-2 rounded-full ${isFilled ? "bg-[#6b4c9a]" : "bg-[#d8caec]"}`}
                />
            ))}
        </div>
    );
}

function normalizeList(value: any): string[] {
    if (Array.isArray(value)) {
        return value
            .map((item) => {
                if (typeof item === "string") return item;
                if (item && typeof item === "object") {
                    return item.name || item.label || item.skill || item.title || "";
                }
                return String(item || "");
            })
            .map((item) => String(item).trim())
            .filter(Boolean);
    }
    if (typeof value === "string") {
        return value
            .split(/[,•]|\\n/g)
            .map((item) => item.trim())
            .filter(Boolean);
    }
    return [];
}

function extractAccomplishments(sections: any): string[] {
    const direct = normalizeList(sections.accomplishments);
    if (direct.length > 0) return direct;
    const achievements = normalizeList(sections.achievements);
    if (achievements.length > 0) return achievements;
    const awards = normalizeList(sections.awards);
    if (awards.length > 0) return awards;

    const custom = Array.isArray(sections.custom_sections) ? sections.custom_sections : [];
    const match = custom.find((sec: any) => {
        const label = String(sec.title || sec.label || "").toLowerCase();
        return /accomplish|achievement|award|honor/.test(label);
    });
    if (!match) return [];
    return normalizeList(match.items || match.content || match.text || match.body || "");
}

function normalizeLanguages(value: any): { name: string; dots: number }[] {
    if (!Array.isArray(value)) {
        if (typeof value === "string") {
            return normalizeList(value).map((name) => ({ name, dots: 3 }));
        }
        return [];
    }
    return value
        .map((lang) => {
            if (typeof lang === "string") return { name: lang, dots: 3 };
            const name = lang.name || lang.language || lang.label || "";
            const level = lang.level ?? lang.proficiency ?? lang.rating ?? lang.score;
            return { name: String(name), dots: levelToDots(level) };
        })
        .filter((lang) => lang.name);
}

function levelToDots(level: any): number {
    if (typeof level === "number") {
        if (level <= 5) return Math.max(1, Math.min(5, Math.round(level)));
        if (level <= 10) return Math.max(1, Math.min(5, Math.round(level / 2)));
        if (level <= 100) return Math.max(1, Math.min(5, Math.round(level / 20)));
    }
    if (typeof level === "string") {
        const s = level.toLowerCase();
        if (s.includes("native")) return 5;
        if (s.includes("fluent")) return 5;
        if (s.includes("advanced")) return 4;
        if (s.includes("intermediate")) return 3;
        if (s.includes("basic") || s.includes("beginner")) return 2;
    }
    return 3;
}

function getInitials(name: string): string {
    const parts = String(name || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean);
    if (parts.length === 0) return "YN";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function formatInitials(initials: string): string {
    const clean = (initials || "").replace(/[^A-Z]/gi, "").slice(0, 2).toUpperCase();
    if (clean.length <= 1) return clean;
    return `${clean[0]}/${clean[1]}`;
}


