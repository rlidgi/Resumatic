import React, { useCallback, useEffect, useMemo, useState } from "react";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import { AiAssistEditableText, EditableText } from "./EditableSection";
import SortableSectionList, { type SortableSectionRow } from "./SortableSectionList";

export default function StylishTemplate({
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

    const updateEducation = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev?.education) ? [...prev.education] : [];
            updated[index] = { ...(updated[index] || {}), [field]: value };
            const next = { ...(prev || {}), education: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateSkill = useCallback((index: number, field: 'name' | 'level', value: string) => {
        setEditedData((prev: any) => {
            const skills = normalizeSkillsWithLevel(prev?.skills);
            const nextArr = [...skills];
            nextArr[index] = { ...(nextArr[index] || { name: '', level: 'Proficient' }), [field]: value };
            const cleaned = nextArr.filter((s) => String(s?.name || '').trim());
            const next = { ...(prev || {}), skills: cleaned };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateLanguage = useCallback((index: number, field: 'name' | 'level', value: string) => {
        setEditedData((prev: any) => {
            const languages = normalizeLanguages(prev?.languages);
            const nextArr = [...languages];
            nextArr[index] = { ...(nextArr[index] || { name: '', level: 'Proficient' }), [field]: value };
            const cleaned = nextArr.filter((l) => String(l?.name || '').trim());
            const next = { ...(prev || {}), languages: cleaned };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateSectionHeading = useCallback((key: string, heading: string) => {
        setEditedData((prev: any) => {
            const prevHeadings = (prev?.section_headings && typeof prev.section_headings === 'object') ? prev.section_headings : {};
            const nextHeadings = { ...prevHeadings, [key]: heading };
            const next = { ...(prev || {}), section_headings: nextHeadings };
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

    const removeExperienceItem = useCallback((index: number) => {
        setEditedData((prev: any) => {
            const current = Array.isArray(prev?.experience) ? prev.experience : [];
            const updated = current.filter((_: any, i: number) => i !== index);
            const next = { ...(prev || {}), experience: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const removeEducationItem = useCallback((index: number) => {
        setEditedData((prev: any) => {
            const current = Array.isArray(prev?.education) ? prev.education : [];
            const updated = current.filter((_: any, i: number) => i !== index);
            const next = { ...(prev || {}), education: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const removeProjectItem = useCallback((index: number) => {
        setEditedData((prev: any) => {
            const current = Array.isArray(prev?.projects) ? prev.projects : [];
            const updated = current.filter((_: any, i: number) => i !== index);
            const next = { ...(prev || {}), projects: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const removeCertificationItem = useCallback((index: number) => {
        setEditedData((prev: any) => {
            const current = normalizeCertifications(prev?.certifications);
            const updated = current.filter((_: any, i: number) => i !== index);
            const cleaned = updated.filter((c) => {
                if (typeof c === 'string') return String(c || '').trim();
                return String((c as any)?.name || (c as any)?.title || '').trim();
            });
            const next = { ...(prev || {}), certifications: cleaned };
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

    const updateCustomItem = useCallback((sectionIndex: number, itemIndex: number, field: string, value: string) => {
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

    const addSection = useCallback(() => {
        const insertCustomInOrder = (order: string[], key: string) => {
            if (order.includes(key)) return order;
            const educationIndex = order.indexOf('education');
            if (educationIndex >= 0) return [...order.slice(0, educationIndex), key, ...order.slice(educationIndex)];
            return [...order, key];
        };

        setEditedData((prev: any) => {
            const next = { ...(prev || {}) };
            const current = Array.isArray(next.custom_sections) ? [...next.custom_sections] : [];
            const customKey = `custom_${current.length}`;

            next.custom_sections = [
                ...current,
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
                onSectionOrderChange(insertCustomInOrder(sectionOrder || [], customKey));
            }

            emit(next);
            return next;
        });
    }, [editMode, emit, onSectionOrderChange, sectionOrder]);

    const data = editedData || {};
    const showEmpty = !!(editMode && (data as any)?._show_empty_sections);

    const getHeading = useCallback((key: string, fallback: string) => {
        const h = data?.section_headings?.[key];
        return String((typeof h === 'string' && h.trim() !== '') ? h : fallback);
    }, [data]);

    const skills = normalizeSkillsWithLevel(data.skills);
    const languages = normalizeLanguages(data.languages);
    const experience = Array.isArray(data.experience) ? data.experience : [];
    const education = Array.isArray(data.education) ? data.education : [];
    const projects = Array.isArray(data.projects) ? data.projects : [];
    const certifications = normalizeCertifications(data.certifications);
    const customSections = Array.isArray(data.custom_sections) ? data.custom_sections : [];

    const mainRows: SortableSectionRow[] = useMemo(() => {
        const rows: SortableSectionRow[] = [];

        if (data.summary || showEmpty) {
            rows.push({
                key: 'summary',
                content: (
                    <SectionBlock title={getHeading('summary', 'PROFILE')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('summary', v)}>
                        {editMode ? (
                            <AiAssistEditableText
                                value={String(data.summary || '')}
                                onChange={(v) => updateField('summary', v)}
                                editMode={editMode}
                                aiField="summary"
                                aiMeta={{ template: 'stylish', section: 'summary' }}
                                liveUpdate
                                layoutSafe
                                wrapperClassName="pt-6"
                                className="text-xs leading-relaxed text-black text-justify"
                                as="div"
                                multiline
                            />
                        ) : (
                            <p className="text-xs leading-relaxed text-black text-justify">
                                {String(data.summary || '')}
                            </p>
                        )}
                    </SectionBlock>
                ),
            });
        }

        if (experience.length > 0 || showEmpty) {
            rows.push({
                key: 'experience',
                content: (
                    <SectionBlock title={getHeading('experience', 'EMPLOYMENT HISTORY')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('experience', v)}>
                        <div className="space-y-5">
                            {experience.map((exp: any, idx: number) => (
                                <div key={idx} className="relative group">
                                    {editMode ? (
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                removeExperienceItem(idx);
                                            }}
                                            className="absolute right-0 -top-2 z-20 px-2 py-1 rounded bg-white border border-red-200 text-[11px] font-semibold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                            aria-label="Remove experience entry"
                                            title="Remove entry"
                                        >
                                            Remove
                                        </button>
                                    ) : null}
                                    <ExperienceEntry exp={exp} editMode={editMode} idx={idx} onUpdate={updateExperience} />
                                </div>
                            ))}
                            {experience.length === 0 && (
                                <div className="text-xs text-slate-500">Add experience to populate this section.</div>
                            )}
                        </div>
                    </SectionBlock>
                ),
            });
        }

        if (education.length > 0 || showEmpty) {
            rows.push({
                key: 'education',
                content: (
                    <SectionBlock title={getHeading('education', 'EDUCATION')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('education', v)}>
                        <div className="space-y-4">
                            {education.map((edu: any, idx: number) => (
                                <div key={idx} className="relative group">
                                    {editMode ? (
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                removeEducationItem(idx);
                                            }}
                                            className="absolute right-0 -top-2 z-20 px-2 py-1 rounded bg-white border border-red-200 text-[11px] font-semibold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                            aria-label="Remove education entry"
                                            title="Remove entry"
                                        >
                                            Remove
                                        </button>
                                    ) : null}
                                    <EducationEntry edu={edu} editMode={editMode} idx={idx} onUpdate={updateEducation} />
                                </div>
                            ))}
                            {education.length === 0 && (
                                <div className="text-xs text-slate-500">Add education to populate this section.</div>
                            )}
                        </div>
                    </SectionBlock>
                ),
            });
        }

        if (projects.length > 0 || showEmpty) {
            rows.push({
                key: 'projects',
                content: (
                    <SectionBlock title={getHeading('projects', 'PROJECTS')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('projects', v)}>
                        <div className="space-y-5">
                            {projects.map((proj: any, idx: number) => (
                                <div key={idx} className="relative group">
                                    {editMode ? (
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                removeProjectItem(idx);
                                            }}
                                            className="absolute right-0 -top-2 z-20 px-2 py-1 rounded bg-white border border-red-200 text-[11px] font-semibold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                            aria-label="Remove project entry"
                                            title="Remove entry"
                                        >
                                            Remove
                                        </button>
                                    ) : null}
                                    <ProjectEntry proj={proj} editMode={editMode} idx={idx} onUpdate={updateProject} />
                                </div>
                            ))}
                            {projects.length === 0 && (
                                <div className="text-xs text-slate-500">Add projects to populate this section.</div>
                            )}
                        </div>
                    </SectionBlock>
                ),
            });
        }

        if (certifications.length > 0 || showEmpty) {
            rows.push({
                key: 'certifications',
                content: (
                    <SectionBlock title={getHeading('certifications', 'CERTIFICATIONS')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('certifications', v)}>
                        <div className="space-y-2">
                            {certifications.map((c: any, idx: number) => {
                                if (typeof c === 'string') {
                                    return (
                                        <div key={idx} className="relative group text-xs text-black">
                                            {editMode ? (
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.preventDefault();
                                                        e.stopPropagation();
                                                        removeCertificationItem(idx);
                                                    }}
                                                    className="absolute right-0 -top-2 z-20 px-2 py-1 rounded bg-white border border-red-200 text-[11px] font-semibold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                                    aria-label="Remove certification entry"
                                                    title="Remove entry"
                                                >
                                                    Remove
                                                </button>
                                            ) : null}
                                            • {c}
                                        </div>
                                    );
                                }

                                const name = String(c?.name || c?.title || c?.certification || '').trim();
                                const issuer = String(c?.issuer || c?.authority || c?.organization || '').trim();
                                const year = String(c?.year || c?.date || '').trim();

                                return (
                                    <div key={idx} className="relative group text-xs text-black">
                                        {editMode ? (
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    removeCertificationItem(idx);
                                                }}
                                                className="absolute right-0 -top-2 z-20 px-2 py-1 rounded bg-white border border-red-200 text-[11px] font-semibold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                                aria-label="Remove certification entry"
                                                title="Remove entry"
                                            >
                                                Remove
                                            </button>
                                        ) : null}
                                        <span className="font-bold">{name || 'Certification'}</span>
                                        {issuer ? <span className="text-slate-600"> — {issuer}</span> : null}
                                        {year ? <span className="text-slate-500"> ({year})</span> : null}
                                    </div>
                                );
                            })}
                            {certifications.length === 0 && (
                                <div className="text-xs text-slate-500">Add certifications to populate this section.</div>
                            )}
                        </div>
                    </SectionBlock>
                ),
            });
        }

        if (customSections.length > 0) {
            for (let idx = 0; idx < customSections.length; idx++) {
                const sec: any = customSections[idx];
                const heading = String(sec?.heading || sec?.title || sec?.label || 'Additional').trim();
                rows.push({
                    key: `custom_${idx}`,
                    content: (
                        <SectionBlock
                            key={idx}
                            title={heading}
                            editMode={editMode}
                            onTitleChange={(v) => updateCustomHeading(idx, v)}
                        >
                            <CustomSectionsRenderer
                                customSections={[sec]}
                                editMode={editMode}
                                onHeadingChange={(sIdx, v) => updateCustomHeading(idx + sIdx, v)}
                                onItemChange={(sIdx, iIdx, field, v) => updateCustomItem(idx + sIdx, iIdx, field, v)}
                                onBodyChange={(sIdx, v) => updateCustomBody(idx + sIdx, v)}
                                showSectionHeadings={false}
                                headingClassName="text-xs font-bold text-black"
                                itemTitleClassName="text-xs font-bold text-black"
                                itemMetaClassName="text-xs text-slate-500"
                                itemBodyClassName="text-xs leading-relaxed text-black"
                            />
                        </SectionBlock>
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
        experience,
        getHeading,
        projects,
        showEmpty,
        updateCustomBody,
        updateCustomHeading,
        updateCustomItem,
        updateEducation,
        updateExperience,
        updateField,
        updateProject,
        updateSectionHeading,
        removeCertificationItem,
        removeEducationItem,
        removeExperienceItem,
        removeProjectItem,
    ]);

    const fullName = String(data.name || 'Your Name').trim();
    const professionalTitle = String(data.title || '').trim();
    const nameParts = fullName.split(/\s+/).filter(Boolean);
    const firstName = nameParts[0] || '';
    const lastName = nameParts.slice(1).join(' ');

    return (
        <div data-template="clean" className="bg-white rounded-lg shadow-lg overflow-hidden max-w-5xl mx-auto font-sans text-black">
            <div className="grid grid-cols-12 min-h-[600px]">
                {/* LEFT COLUMN - ~1/3 */}
                <aside className="col-span-4 p-6 border-r" style={{ backgroundColor: 'var(--tv-secondary)', borderColor: 'var(--tv-primary-dark)' }}>
                    <div
                        className="-mx-6 -mt-6 mb-6 px-6 pt-6 pb-5 border-b"
                        style={{ backgroundColor: 'var(--tv-secondary-dark)', borderColor: 'var(--tv-primary-dark)' }}
                    >
                        <h1 className="text-xl font-bold uppercase tracking-tight text-black leading-tight">
                            {editMode ? (
                                <>
                                    <EditableText
                                        value={firstName}
                                        placeholder="First"
                                        onChange={(v) => updateField('name', [v, lastName].filter(Boolean).join(' '))}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        className="text-black"
                                        as="span"
                                    />
                                    {lastName ? <span> </span> : null}
                                    <EditableText
                                        value={lastName}
                                        placeholder="Last"
                                        onChange={(v) => updateField('name', [firstName, v].filter(Boolean).join(' '))}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        className="text-black/50"
                                        as="span"
                                    />
                                </>
                            ) : (
                                <>
                                    <span className="text-black">{(firstName || 'Your').toUpperCase()}</span>
                                    {lastName ? <span className="text-black/50"> {(lastName || '').toUpperCase()}</span> : null}
                                </>
                            )}
                        </h1>
                        {(editMode || professionalTitle) ? (
                            <div className="mt-1 text-sm font-normal text-black">
                                {editMode ? (
                                    <EditableText
                                        value={String(data.title || '')}
                                        placeholder="Professional Title"
                                        onChange={(v) => updateField('title', v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        className="text-sm font-normal text-black"
                                        as="div"
                                    />
                                ) : (
                                    professionalTitle
                                )}
                            </div>
                        ) : null}
                    </div>

                    {(data.address || data.location || data.phone || data.email || showEmpty) && (
                        <SectionBlock title={getHeading('info', 'INFO')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('info', v)}>
                            {(data.address || data.location) ? (
                                <InfoRow label="ADDRESS" value={String(data.address || data.location || '')} editMode={editMode} onChange={(v) => updateField('location', v)} />
                            ) : showEmpty ? (
                                <InfoRow label="ADDRESS" value="" editMode={editMode} onChange={(v) => updateField('location', v)} />
                            ) : null}
                            {data.phone ? (
                                <InfoRow label="PHONE" value={data.phone} editMode={editMode} onChange={(v) => updateField('phone', v)} />
                            ) : showEmpty ? (
                                <InfoRow label="PHONE" value="" editMode={editMode} onChange={(v) => updateField('phone', v)} />
                            ) : null}
                            {data.email ? (
                                <InfoRow label="EMAIL" value={data.email} editMode={editMode} onChange={(v) => updateField('email', v)} />
                            ) : showEmpty ? (
                                <InfoRow label="EMAIL" value="" editMode={editMode} onChange={(v) => updateField('email', v)} />
                            ) : null}
                        </SectionBlock>
                    )}

                    {(skills.length > 0 || showEmpty) && (
                        <SectionBlock title={getHeading('skills', 'SKILLS')} panelTone="secondary-dark" editMode={editMode} onTitleChange={(v) => updateSectionHeading('skills', v)}>
                            <div className="space-y-3">
                                {skills.slice(0, 10).map((skill, idx) => (
                                    <SkillBarRow key={idx} skill={skill} editMode={editMode} idx={idx} onUpdate={updateSkill} />
                                ))}
                                {skills.length === 0 && (
                                    <div className="text-xs text-slate-500">Add skills to populate this section.</div>
                                )}
                            </div>
                        </SectionBlock>
                    )}

                    {(languages.length > 0 || showEmpty) && (
                        <SectionBlock title={getHeading('languages', 'LANGUAGES')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('languages', v)}>
                            <div className="space-y-3">
                                {languages.slice(0, 5).map((lang, idx) => (
                                    <LanguageBarRow key={idx} lang={lang} editMode={editMode} idx={idx} onUpdate={updateLanguage} />
                                ))}
                                {languages.length === 0 && (
                                    <div className="text-xs text-slate-500">Add languages to populate this section.</div>
                                )}
                            </div>
                        </SectionBlock>
                    )}
                </aside>

                {/* RIGHT COLUMN - ~2/3 */}
                <main className={`col-span-8 p-6 ${editMode ? 'pl-10' : ''}`}>
                    <SortableSectionList
                        rows={mainRows}
                        editMode={!!editMode}
                        sectionOrder={sectionOrder}
                        onSectionOrderChange={onSectionOrderChange}
                        hiddenSectionKeys={hiddenSectionKeys}
                        onHiddenSectionKeysChange={onHiddenSectionKeysChange}
                    />
                </main>
            </div>
        </div>
    );
}

function SectionBlock({
    title,
    children,
    panelTone = 'none',
    editMode,
    onTitleChange,
}: {
    title: string;
    children: React.ReactNode;
    panelTone?: 'none' | 'secondary' | 'secondary-dark';
    editMode?: boolean;
    onTitleChange?: (v: string) => void;
}) {
    return (
        <section className="mb-6 last:mb-0">
            <h2 className="text-xs font-bold uppercase tracking-wide" style={{ color: 'var(--tv-primary)' }}>
                {editMode ? (
                    <EditableText value={title} onChange={(v) => onTitleChange?.(v)} editMode={editMode} liveUpdate layoutSafe className="text-xs font-bold uppercase" style={{ color: 'var(--tv-primary)' }} as="div" />
                ) : (
                    title
                )}
            </h2>
            <div className="h-px mt-1 mb-3 w-12" style={{ backgroundColor: 'var(--tv-primary-dark)' }} />
            {panelTone === 'none' ? (
                children
            ) : (
                <div
                    className="rounded-md p-3"
                    style={{
                        backgroundColor: panelTone === 'secondary-dark' ? 'var(--tv-secondary-dark)' : 'var(--tv-secondary)',
                    }}
                >
                    {children}
                </div>
            )}
        </section>
    );
}

function InfoRow({ label, value, editMode, onChange }: { label: string; value: string; editMode?: boolean; onChange?: (v: string) => void }) {
    return (
        <div className="mb-2">
            <span className="text-xs font-bold text-black block">{label}</span>
            {editMode ? (
                <EditableText value={value} onChange={(v) => onChange?.(v)} editMode={editMode} liveUpdate layoutSafe className="text-xs text-black mt-0.5" as="div" />
            ) : (
                <span className="text-xs text-black block mt-0.5">{value || '—'}</span>
            )}
        </div>
    );
}

function levelToPercent(level: string): number {
    const s = String(level || "").toLowerCase();
    if (s.includes("native") || s.includes("fluent")) return 100;
    if (s.includes("advanced") || s.includes("proficient")) return 90;
    if (s.includes("intermediate")) return 75;
    if (s.includes("basic") || s.includes("beginner")) return 50;
    return 80;
}

function percentStepToLevel(step: number): string {
    if (step >= 4) return "Fluent";
    if (step === 3) return "Proficient";
    if (step === 2) return "Intermediate";
    return "Beginner";
}

function getLevelFromBarClick(event: React.MouseEvent<HTMLButtonElement>): string {
    const rect = event.currentTarget.getBoundingClientRect();
    const relativeX = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
    const ratio = rect.width > 0 ? (relativeX / rect.width) : 0;
    const step = Math.max(1, Math.min(4, Math.ceil(ratio * 4)));
    return percentStepToLevel(step);
}

function EditableGaugeBar({
    value,
    label,
    editMode,
    onChange,
}: {
    value: string;
    label: string;
    editMode: boolean;
    onChange: (value: string) => void;
}) {
    const pct = levelToPercent(value);

    if (!editMode) {
        return (
            <div className="flex-1 min-w-[60px] h-1.5 rounded overflow-hidden" style={{ backgroundColor: 'var(--tv-secondary)' }}>
                <div className="h-full rounded" style={{ width: `${pct}%`, backgroundColor: 'var(--tv-primary-dark)' }} />
            </div>
        );
    }

    return (
        <button
            type="button"
            onMouseDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
            }}
            onPointerDown={(e) => {
                e.preventDefault();
                e.stopPropagation();
            }}
            onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                onChange(getLevelFromBarClick(e));
            }}
            aria-label={`Set ${label} level`}
            title={`${label}: click bar to change level`}
            className="relative flex-1 min-w-[60px] h-1.5 rounded overflow-hidden ring-1 ring-black/10 hover:ring-black/40"
            style={{ backgroundColor: 'var(--tv-secondary)' }}
        >
            <span className="absolute inset-y-0 left-0 rounded" style={{ width: `${pct}%`, backgroundColor: 'var(--tv-primary-dark)' }} />
        </button>
    );
}

function SkillBarRow({ skill, editMode, idx, onUpdate }: { skill: { name: string; level: string }; editMode: boolean; idx: number; onUpdate: (i: number, f: 'name' | 'level', v: string) => void }) {
    return (
        <div>
            <div className="flex items-center justify-between gap-2 mb-1">
                {editMode ? (
                    <EditableText value={skill.name} onChange={(v) => onUpdate(idx, 'name', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs text-black flex-1 min-w-0" as="div" />
                ) : (
                    <span className="text-xs text-black flex-1">{skill.name}</span>
                )}
                <EditableGaugeBar value={skill.level} label={skill.name || 'skill'} editMode={editMode} onChange={(value) => onUpdate(idx, 'level', value)} />
            </div>
        </div>
    );
}

function LanguageBarRow({ lang, editMode, idx, onUpdate }: { lang: { name: string; level: string }; editMode: boolean; idx: number; onUpdate: (i: number, f: 'name' | 'level', v: string) => void }) {
    return (
        <div>
            <div className="flex items-center justify-between gap-2 mb-1">
                {editMode ? (
                    <EditableText value={lang.name} onChange={(v) => onUpdate(idx, 'name', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs text-black flex-1 min-w-0" as="div" />
                ) : (
                    <span className="text-xs text-black flex-1">{lang.name}</span>
                )}
                <EditableGaugeBar value={lang.level} label={lang.name || 'language'} editMode={editMode} onChange={(value) => onUpdate(idx, 'level', value)} />
            </div>
        </div>
    );
}

function ProjectEntry({ proj, editMode, idx, onUpdate }: { proj: any; editMode: boolean; idx: number; onUpdate: (i: number, f: string, v: string) => void }) {
    const title = proj.title || proj.name || "Project";
    return (
        <div>
            <div className="flex justify-between items-baseline gap-2">
                <div className="text-xs font-bold text-black">
                    {editMode ? (
                        <EditableText value={title} onChange={(v) => onUpdate(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs font-bold inline" as="span" />
                    ) : (
                        title
                    )}
                </div>
                {proj.link ? (
                    <a href={proj.link} target="_blank" rel="noreferrer" className="text-xs text-slate-600 underline shrink-0">Link</a>
                ) : null}
            </div>
            {proj.technologies ? (
                editMode ? (
                    <EditableText value={String(proj.technologies)} onChange={(v) => onUpdate(idx, 'technologies', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs text-slate-600 mt-0.5" as="span" />
                ) : (
                    <div className="text-xs text-slate-600 mt-0.5">{proj.technologies}</div>
                )
            ) : null}
            {(editMode || proj.description) ? (
                <div className="mt-2">
                    {editMode ? (
                        <AiAssistEditableText value={String(proj.description)} onChange={(v) => onUpdate(idx, 'description', v)} editMode={editMode} aiField="project_description" aiMeta={{ template: 'stylish', index: idx, title }} liveUpdate layoutSafe wrapperClassName="pt-6" className="text-xs leading-relaxed text-black" as="div" multiline />
                    ) : (
                        <RenderMaybeBullets text={proj.description} forceBullets className="text-xs leading-relaxed text-black" />
                    )}
                </div>
            ) : editMode ? (
                <EditableText value="" onChange={(v) => onUpdate(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs mt-2" as="div" placeholder="Add description" multiline />
            ) : null}
        </div>
    );
}

function EducationEntry({ edu, editMode, idx, onUpdate }: { edu: any; editMode: boolean; idx: number; onUpdate: (i: number, f: string, v: string) => void }) {
    const degree = String(edu?.degree || edu?.title || '').trim();
    const field = String(edu?.field || edu?.focus || edu?.major || '').trim();
    const school = String(edu?.institution || edu?.school || '').trim();
    const year = String(edu?.year || edu?.dates || edu?.graduationDate || '').trim();
    const location = String(edu?.location || edu?.city || '').trim();
    const gpa = String(edu?.gpa ?? '').trim();

    return (
        <div>
            <div className="flex items-baseline justify-between gap-2">
                <div className="text-xs font-bold text-black">
                    {editMode ? (
                        <>
                            <EditableText value={degree || school || 'Education'} onChange={(v) => onUpdate(idx, 'degree', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs font-bold inline" as="span" />
                            {field ? (
                                <>
                                    {' — '}
                                    <EditableText value={field} onChange={(v) => onUpdate(idx, 'field', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs font-bold inline" as="span" />
                                </>
                            ) : null}
                        </>
                    ) : (
                        <>
                            {degree || school || 'Education'}
                            {field ? ` — ${field}` : ''}
                        </>
                    )}
                </div>
                {(year || editMode) ? (
                    editMode ? (
                        <EditableText value={year} onChange={(v) => onUpdate(idx, 'year', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs shrink-0" as="span" placeholder="Year" />
                    ) : (
                        <span className="text-xs text-black shrink-0">{year}</span>
                    )
                ) : null}
            </div>

            {(school || editMode) ? (
                editMode ? (
                    <EditableText value={school} onChange={(v) => onUpdate(idx, 'institution', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs text-slate-600 mt-0.5" as="div" placeholder="Institution" />
                ) : (
                    <div className="text-xs text-slate-600 mt-0.5">{school}</div>
                )
            ) : null}

            {(location || editMode) ? (
                editMode ? (
                    <EditableText value={location} onChange={(v) => onUpdate(idx, 'location', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs text-slate-600 mt-0.5" as="div" placeholder="Location" />
                ) : location ? (
                    <div className="text-xs text-slate-600 mt-0.5">{location}</div>
                ) : null
            ) : null}

            {gpa ? (
                editMode ? (
                    <div className="text-xs text-slate-600 mt-0.5">
                        GPA: <EditableText value={gpa} onChange={(v) => onUpdate(idx, 'gpa', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs inline" as="span" />
                    </div>
                ) : (
                    <div className="text-xs text-slate-600 mt-0.5">GPA: {gpa}</div>
                )
            ) : null}
        </div>
    );
}

function ExperienceEntry({ exp, editMode, idx, onUpdate }: { exp: any; editMode: boolean; idx: number; onUpdate: (i: number, f: string, v: string) => void }) {
    const role = exp.title || exp.position || "Role";
    const company = exp.company || exp.organization || "";
    const location = exp.location || exp.city || "";
    const dates = exp.duration || (exp.startDate && exp.endDate ? `${exp.startDate} - ${exp.currentlyWorking ? 'Present' : exp.endDate}` : "") || [exp.start, exp.end].filter(Boolean).join(" - ");

    return (
        <div>
            <div className="flex justify-between items-baseline gap-2">
                <div className="text-xs font-bold text-black">
                    {editMode ? (
                        <>
                            <EditableText value={role} onChange={(v) => onUpdate(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs font-bold inline" as="span" />
                            {', '}
                            <EditableText value={company} onChange={(v) => onUpdate(idx, 'company', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs font-bold inline" as="span" />
                        </>
                    ) : (
                        `${role}${company ? ', ' + company : ''}`
                    )}
                </div>
                {(location || editMode) ? (
                    editMode ? (
                        <EditableText value={location} onChange={(v) => onUpdate(idx, 'location', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs shrink-0" as="span" placeholder="Location" />
                    ) : (
                        <span className="text-xs text-black shrink-0">{location}</span>
                    )
                ) : null}
            </div>
            {editMode ? (
                <EditableText value={dates} onChange={(v) => onUpdate(idx, 'duration', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs text-black mt-0.5" as="span" placeholder="Dates" />
            ) : (
                <div className="text-xs text-black mt-0.5">{dates}</div>
            )}
            {(editMode || exp.description) ? (
                <div className="mt-2">
                    {editMode ? (
                        <AiAssistEditableText
                            value={String(exp.description)}
                            onChange={(v) => onUpdate(idx, 'description', v)}
                            editMode={editMode}
                            aiField="experience_description"
                            aiMeta={{ template: 'stylish', index: idx, role, company }}
                            liveUpdate
                            layoutSafe
                            wrapperClassName="pt-6"
                            className="text-xs leading-relaxed text-black"
                            as="div"
                            multiline
                        />
                    ) : (
                        <RenderMaybeBullets text={exp.description} forceBullets className="text-xs leading-relaxed text-black" />
                    )}
                </div>
            ) : editMode ? (
                <EditableText value="" onChange={(v) => onUpdate(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe className="text-xs mt-2" as="div" placeholder="Add bullets" multiline />
            ) : null}
        </div>
    );
}

function normalizeSkillsWithLevel(value: any): Array<{ name: string; level: string }> {
    if (!value) return [];
    if (Array.isArray(value)) {
        return value
            .map((s) => {
                if (typeof s === "string") return { name: s.trim(), level: "Proficient" };
                const name = s.name || s.skill || s.label || "";
                const level = s.level || s.proficiency || s.rating || "Proficient";
                return { name: String(name), level: String(level || "Proficient") };
            })
            .filter((x) => x.name);
    }
    if (typeof value === "string") {
        return value.split(/[,•\n]/g).map((s) => s.trim()).filter(Boolean).map((n) => ({ name: n, level: "Proficient" }));
    }
    return [];
}

function normalizeLanguages(value: any): Array<{ name: string; level: string }> {
    if (!value) return [];
    if (Array.isArray(value)) {
        return value
            .map((l) => {
                if (typeof l === "string") return { name: l, level: "Proficient" };
                const name = l.name || l.language || l.label || "";
                const level = l.level || l.proficiency || l.rating || "Proficient";
                return { name: String(name), level: String(level || "Proficient") };
            })
            .filter((x) => x.name);
    }
    if (typeof value === "string") {
        return value.split(/[,•\n]/g).map((s) => s.trim()).filter(Boolean).map((n) => ({ name: n, level: "Proficient" }));
    }
    return [];
}

function normalizeCertifications(value: any): any[] {
    if (!value) return [];
    if (Array.isArray(value)) {
        return value
            .map((c) => {
                if (typeof c === 'string') return c.trim();
                if (!c || typeof c !== 'object') return null;
                return c;
            })
            .filter(Boolean);
    }
    if (typeof value === 'string') {
        return value
            .split(/[,•\n]/g)
            .map((s) => s.trim())
            .filter(Boolean);
    }
    return [];
}

