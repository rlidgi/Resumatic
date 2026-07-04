import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Mail, Phone, MapPin, Linkedin, Globe } from "lucide-react";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import { AiAssistEditableText, EditableText } from "./EditableSection";
import SortableSectionList, { type SortableSectionRow } from "./SortableSectionList";

export default function ModernTemplate({
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

    const updateLanguage = useCallback((index: number, field: 'name' | 'level', value: string) => {
        setEditedData((prev: any) => {
            const current = normalizeLanguages(prev?.languages);
            const nextArr = [...current];
            nextArr[index] = { ...(nextArr[index] || { name: '', level: 'Proficient' }), [field]: value };
            const cleaned = nextArr.filter((l) => String(l?.name || '').trim());
            const next = { ...(prev || {}), languages: cleaned };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateCertification = useCallback((index: number, field: 'name' | 'issuer' | 'year', value: string) => {
        setEditedData((prev: any) => {
            const current = normalizeCertifications(prev?.certifications);
            const nextArr = [...current];
            nextArr[index] = { ...(nextArr[index] || { name: '', issuer: '', year: '' }), [field]: value };
            const cleaned = nextArr.filter((c) => String(c?.name || '').trim());
            const next = { ...(prev || {}), certifications: cleaned };
            emit(next);
            return next;
        });
    }, [emit]);

    const removeExperienceItem = useCallback((index: number) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev?.experience) ? prev.experience.filter((_: any, i: number) => i !== index) : [];
            const next = { ...(prev || {}), experience: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const removeEducationItem = useCallback((index: number) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev?.education) ? prev.education.filter((_: any, i: number) => i !== index) : [];
            const next = { ...(prev || {}), education: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const removeProjectItem = useCallback((index: number) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev?.projects) ? prev.projects.filter((_: any, i: number) => i !== index) : [];
            const next = { ...(prev || {}), projects: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const removeCertificationItem = useCallback((index: number) => {
        setEditedData((prev: any) => {
            const current = normalizeCertifications(prev?.certifications);
            const updated = current.filter((_: any, i: number) => i !== index);
            const next = { ...(prev || {}), certifications: updated };
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

    const links = Array.isArray(data.links) ? data.links : [];
    const skills = normalizeList(data.skills);
    const languages = normalizeLanguages(data.languages);
    const certifications = normalizeCertifications(data.certifications);
    const strengths = extractStrengths(data);
    const education = Array.isArray(data.education) ? data.education : [];
    const experience = Array.isArray(data.experience) ? data.experience : [];
    const projects = Array.isArray(data.projects) ? data.projects : [];
    const customSections = Array.isArray(data.custom_sections) ? data.custom_sections : [];

    const fullName = String(data.name || 'Your Name').trim();
    const professionalTitle = String(data.title || '').trim();
    const nameParts = fullName.split(/\s+/).filter(Boolean);
    const firstName = nameParts[0] || '';
    const lastName = nameParts.slice(1).join(' ');

    const mainRows: SortableSectionRow[] = useMemo(() => {
        const rows: SortableSectionRow[] = [];

        if (data.summary || showEmpty) {
            rows.push({
                key: 'summary',
                title: getHeading('summary', 'Summary'),
                content: (
                    <MainSection
                        title={getHeading('summary', 'Summary')}
                        editMode={editMode}
                        onTitleChange={(v) => updateSectionHeading('summary', v)}
                    >
                        {editMode ? (
                            <AiAssistEditableText
                                value={String(data.summary)}
                                onChange={(v) => updateField('summary', v)}
                                editMode={editMode}
                                aiField="summary"
                                aiMeta={{ template: 'modern', section: 'summary' }}
                                liveUpdate
                                layoutSafe
                                wrapperClassName="pt-6"
                                className="text-[12px] leading-relaxed text-slate-700"
                                as="div"
                                multiline
                            />
                        ) : (
                            <p className="text-[12px] leading-relaxed text-slate-700">{String(data.summary)}</p>
                        )}
                    </MainSection>
                ),
            });
        }

        if (experience.length > 0 || showEmpty) {
            rows.push({
                key: 'experience',
                title: getHeading('experience', 'Experience'),
                content: (
                    <MainSection
                        title={getHeading('experience', 'Experience')}
                        editMode={editMode}
                        onTitleChange={(v) => updateSectionHeading('experience', v)}
                    >
                        <div className="space-y-6">
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
                                            className="absolute right-0 top-0 z-20 px-2 py-1 rounded bg-white border border-red-200 text-[11px] font-semibold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                            aria-label="Remove experience entry"
                                            title="Remove entry"
                                        >
                                            Remove
                                        </button>
                                    ) : null}
                                    <ExperienceBlock exp={exp} editMode={editMode} idx={idx} onUpdate={updateExperience} />
                                </div>
                            ))}
                            {experience.length === 0 ? (
                                <div className="text-[12px] text-slate-500">Add experience to populate this section.</div>
                            ) : null}
                        </div>
                    </MainSection>
                ),
            });
        }

        if (projects.length > 0 || showEmpty) {
            rows.push({
                key: 'projects',
                title: getHeading('projects', 'Projects'),
                content: (
                    <MainSection
                        title={getHeading('projects', 'Projects')}
                        editMode={editMode}
                        onTitleChange={(v) => updateSectionHeading('projects', v)}
                    >
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
                                            className="absolute right-0 top-0 z-20 px-2 py-1 rounded bg-white border border-red-200 text-[11px] font-semibold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                            aria-label="Remove project"
                                            title="Remove project"
                                        >
                                            Remove
                                        </button>
                                    ) : null}
                                    <div className="flex items-baseline justify-between gap-3">
                                        <div className="text-[12px] font-semibold text-slate-900">
                                            {editMode ? (
                                                <EditableText
                                                    value={String(proj.title || proj.name || 'Project')}
                                                    onChange={(v) => updateProject(idx, 'title', v)}
                                                    editMode={editMode}
                                                    liveUpdate
                                                    layoutSafe
                                                    className="text-[12px] font-semibold text-slate-900"
                                                    as="div"
                                                />
                                            ) : (
                                                proj.title || proj.name || "Project"
                                            )}
                                        </div>
                                        {proj.link ? (
                                            <a
                                                href={proj.link}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="text-[11px] text-slate-600 underline underline-offset-2 hover:text-slate-900"
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
                                                className="mt-1 text-[11px] text-slate-600"
                                                as="div"
                                            />
                                        ) : (
                                            <div className="mt-1 text-[11px] text-slate-600">{String(proj.technologies)}</div>
                                        )
                                    ) : null}
                                    {(editMode || proj.description) ? (
                                        <div className="mt-2">
                                            {editMode ? (
                                                <AiAssistEditableText
                                                    value={String(proj.description)}
                                                    onChange={(v) => updateProject(idx, 'description', v)}
                                                    editMode={editMode}
                                                    aiField="project_description"
                                                    aiMeta={{ template: 'modern', index: idx, title: String(proj.title || proj.name || 'Project') }}
                                                    liveUpdate
                                                    layoutSafe
                                                    wrapperClassName="pt-6"
                                                    className="text-[12px] leading-relaxed text-slate-700"
                                                    as="div"
                                                    multiline
                                                />
                                            ) : (
                                                <RenderMaybeBullets
                                                    text={String(proj.description)}
                                                    forceBullets
                                                    className="text-[12px] leading-relaxed text-slate-700"
                                                />
                                            )}
                                        </div>
                                    ) : null}
                                </div>
                            ))}
                            {projects.length === 0 ? (
                                <div className="text-[12px] text-slate-500">Add projects to populate this section.</div>
                            ) : null}
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
                        <MainSection
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
                                headingClassName="text-[12px] font-semibold text-slate-900"
                                itemTitleClassName="text-[12px] font-semibold text-slate-900"
                                itemMetaClassName="text-[11px] text-slate-500"
                                itemBodyClassName="text-[12px] leading-relaxed text-slate-700"
                            />
                        </MainSection>
                    ),
                });
            }
        }

        return rows;
    }, [
        customSections,
        data.summary,
        editMode,
        experience,
        getHeading,
        projects,
        showEmpty,
        updateCustomBody,
        updateCustomHeading,
        updateCustomItem,
        updateExperience,
        updateField,
        updateProject,
        updateSectionHeading,
    ]);

    return (
        <div data-template="modern" className="bg-white rounded-lg shadow-lg ring-1 ring-black/5 overflow-hidden max-w-5xl mx-auto font-sans">
            <div
                className="px-10 pt-10 pb-6 border-b"
                style={{ backgroundColor: 'var(--tv-secondary-dark)', borderColor: 'var(--tv-primary-dark)' }}
            >
                <div className="text-3xl font-extrabold tracking-tight">
                    {editMode ? (
                        <div className="text-3xl font-extrabold tracking-tight">
                            <EditableText
                                value={firstName}
                                placeholder="First"
                                onChange={(v) => updateField('name', [v, lastName].filter(Boolean).join(' '))}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                className="text-slate-900"
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
                                className="text-slate-600"
                                as="span"
                            />
                        </div>
                    ) : (
                        <>
                            <span className="text-slate-900">{firstName || 'Your'}</span>
                            {lastName ? <span className="text-slate-600"> {lastName}</span> : null}
                        </>
                    )}
                </div>
                {(editMode || professionalTitle) ? (
                    <div className="mt-1 text-sm text-slate-700 font-medium">
                        {editMode ? (
                            <EditableText
                                value={String(data.title || '')}
                                placeholder="Professional Title"
                                onChange={(v) => updateField('title', v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                className="text-sm text-slate-700 font-medium"
                                as="div"
                            />
                        ) : (
                            professionalTitle
                        )}
                    </div>
                ) : null}

                <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-[12px] text-slate-600">
                    {(editMode || data.location) && (
                        editMode ? (
                            <div className="inline-flex items-center gap-2">
                                <span style={{ color: 'var(--tv-accent)' }}><MapPin className="w-4 h-4" /></span>
                                <EditableText value={String(data.location)} onChange={(v) => updateField('location', v)} editMode={editMode} liveUpdate layoutSafe as="span" />
                            </div>
                        ) : (
                            <InlineContact icon={<MapPin className="w-4 h-4" />} value={String(data.location)} />
                        )
                    )}
                    {(editMode || data.phone) && (
                        editMode ? (
                            <div className="inline-flex items-center gap-2">
                                <span style={{ color: 'var(--tv-accent)' }}><Phone className="w-4 h-4" /></span>
                                <EditableText value={String(data.phone)} onChange={(v) => updateField('phone', v)} editMode={editMode} liveUpdate layoutSafe as="span" />
                            </div>
                        ) : (
                            <InlineContact icon={<Phone className="w-4 h-4" />} value={String(data.phone)} />
                        )
                    )}
                    {(editMode || data.email) && (
                        editMode ? (
                            <div className="inline-flex items-center gap-2">
                                <span style={{ color: 'var(--tv-accent)' }}><Mail className="w-4 h-4" /></span>
                                <EditableText value={String(data.email)} onChange={(v) => updateField('email', v)} editMode={editMode} liveUpdate layoutSafe as="span" />
                            </div>
                        ) : (
                            <InlineContact icon={<Mail className="w-4 h-4" />} value={String(data.email)} />
                        )
                    )}
                    {links.slice(0, 1).map((l: any, idx: number) => {
                        const url = l.url || l.href;
                        if (!url) return null;
                        const isLinkedIn = String(l.label || l.name || url).toLowerCase().includes("linkedin") || String(url).toLowerCase().includes("linkedin");
                        return (
                            <InlineContact
                                key={idx}
                                icon={isLinkedIn ? <Linkedin className="w-4 h-4" /> : <Globe className="w-4 h-4" />}
                                value={url}
                                href={url}
                            />
                        );
                    })}
                </div>
            </div>

            <div className="grid grid-cols-12 gap-10 px-10 pt-6 pb-10">
                {/* MAIN */}
                <main className={`col-span-7 ${editMode ? 'pl-16' : ''}`}>
                    <SortableSectionList
                        rows={mainRows}
                        editMode={!!editMode}
                        sectionOrder={sectionOrder}
                        onSectionOrderChange={onSectionOrderChange}
                        hiddenSectionKeys={hiddenSectionKeys}
                        onHiddenSectionKeysChange={onHiddenSectionKeysChange}
                    />
                </main>

                {/* SIDEBAR */}
                <aside
                    className="col-span-5 -mr-10 p-6 pr-10"
                    style={{ backgroundColor: 'var(--tv-secondary)' }}
                >
                    {(education.length > 0 || showEmpty) && (
                        <SideSection
                            sectionKey="education"
                            title={getHeading('education', 'Education')}
                            editMode={editMode}
                            onTitleChange={(v) => updateSectionHeading('education', v)}
                        >
                            <div className="space-y-4">
                                {education.map((edu: any, idx: number) => {
                                    const gpa = String(edu?.gpa ?? '').trim();

                                    return (
                                        <div key={idx} className="relative group">
                                            {editMode ? (
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.preventDefault();
                                                        e.stopPropagation();
                                                        removeEducationItem(idx);
                                                    }}
                                                    className="absolute right-0 top-0 z-20 px-2 py-1 rounded bg-white border border-red-200 text-[11px] font-semibold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                                    aria-label="Remove education entry"
                                                    title="Remove entry"
                                                >
                                                    Remove
                                                </button>
                                            ) : null}
                                            <div className="text-[12px] font-semibold text-slate-900">
                                                {editMode ? (
                                                    <EditableText value={String(edu.degree || edu.title || 'Degree')} onChange={(v) => updateEducation(idx, 'degree', v)} editMode={editMode} liveUpdate layoutSafe as="div" />
                                                ) : (
                                                    edu.degree || edu.title || "Degree"
                                                )}
                                            </div>
                                            <div className="text-[11px] text-slate-700 font-medium">
                                                {editMode ? (
                                                    <EditableText value={String(edu.institution || edu.school || '')} onChange={(v) => updateEducation(idx, 'institution', v)} editMode={editMode} liveUpdate layoutSafe as="div" />
                                                ) : (
                                                    edu.institution || edu.school || ""
                                                )}
                                            </div>
                                            <div className="mt-1 text-[11px] text-slate-500 flex items-center gap-2">
                                                {editMode ? (
                                                    <EditableText value={String(edu.year || edu.dates || edu.graduationDate || '')} onChange={(v) => updateEducation(idx, 'year', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                ) : (
                                                    edu.year || edu.dates || edu.graduationDate || ""
                                                )}
                                                {(edu.location || edu.city) ? <span className="text-slate-300">•</span> : null}
                                                {editMode ? (
                                                    <EditableText value={String(edu.location || edu.city || '')} onChange={(v) => updateEducation(idx, 'location', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                ) : (
                                                    edu.location || edu.city || ""
                                                )}
                                                {gpa ? <span className="text-slate-300">•</span> : null}
                                                {gpa ? (
                                                    editMode ? (
                                                        <span>
                                                            GPA: <EditableText value={String(gpa)} onChange={(v) => updateEducation(idx, 'gpa', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                        </span>
                                                    ) : (
                                                        <span>GPA: {String(gpa)}</span>
                                                    )
                                                ) : null}
                                            </div>
                                        </div>
                                    );
                                })}
                                {education.length === 0 ? (
                                    <div className="text-[11px] text-slate-500">Add education to populate this section.</div>
                                ) : null}
                            </div>
                        </SideSection>
                    )}

                    {(skills.length > 0 || showEmpty) && (
                        <SideSection
                            title={getHeading('skills', 'Skills')}
                            editMode={editMode}
                            onTitleChange={(v) => updateSectionHeading('skills', v)}
                        >
                            <div className="grid grid-cols-3 gap-x-4 gap-y-2 text-[11px] text-slate-700">
                                {skills.slice(0, 18).map((s, idx) => (
                                    editMode ? (
                                        <EditableText key={idx} value={s} onChange={(v) => updateSkill(idx, v)} editMode={editMode} liveUpdate layoutSafe as="div" className="font-medium" />
                                    ) : (
                                        <div key={idx} className="font-medium">{s}</div>
                                    )
                                ))}
                                {skills.length === 0 ? (
                                    <div className="col-span-3 text-[11px] text-slate-500">Add skills to populate this section.</div>
                                ) : null}
                            </div>
                        </SideSection>
                    )}

                    {strengths.length > 0 && (
                        <SideSection
                            title={getHeading('strengths', 'Strengths')}
                            editMode={editMode}
                            onTitleChange={(v) => updateSectionHeading('strengths', v)}
                        >
                            <div className="space-y-4">
                                {strengths.slice(0, 4).map((st, idx) => (
                                    <div key={idx}>
                                        <div className="text-[12px] font-semibold text-slate-900">{st.title}</div>
                                        {st.body ? (
                                            <div className="mt-1 text-[11px] leading-relaxed text-slate-700">{st.body}</div>
                                        ) : null}
                                    </div>
                                ))}
                                {strengths.length === 0 ? (
                                    <div className="text-[11px] text-slate-500">Add strengths to populate this section.</div>
                                ) : null}
                            </div>
                        </SideSection>
                    )}

                    {(languages.length > 0 || showEmpty) && (
                        <SideSection
                            title={getHeading('languages', 'Languages')}
                            editMode={editMode}
                            onTitleChange={(v) => updateSectionHeading('languages', v)}
                        >
                            <div className="space-y-3">
                                {languages.slice(0, 5).map((lang, idx) => (
                                    <LanguageRow key={idx} name={lang.name} level={lang.level} editMode={editMode} idx={idx} onUpdate={updateLanguage} />
                                ))}
                                {languages.length === 0 ? (
                                    <div className="text-[11px] text-slate-500">Add languages to populate this section.</div>
                                ) : null}
                            </div>
                        </SideSection>
                    )}

                    {(certifications.length > 0 || showEmpty) && (
                        <SideSection
                            sectionKey="certifications"
                            title={getHeading('certifications', 'Certifications')}
                            editMode={editMode}
                            onTitleChange={(v) => updateSectionHeading('certifications', v)}
                        >
                            <div className="space-y-3">
                                {certifications.slice(0, 5).map((c, idx) => (
                                    <div key={idx} className="relative group">
                                        {editMode ? (
                                            <button
                                                type="button"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    removeCertificationItem(idx);
                                                }}
                                                className="absolute right-0 top-0 z-20 px-2 py-1 rounded bg-white border border-red-200 text-[11px] font-semibold text-red-600 opacity-0 group-hover:opacity-100 transition-opacity"
                                                aria-label="Remove certification entry"
                                                title="Remove entry"
                                            >
                                                Remove
                                            </button>
                                        ) : null}
                                        <CertificationRow cert={c} editMode={editMode} idx={idx} onUpdate={updateCertification} />
                                    </div>
                                ))}
                                {certifications.length === 0 ? (
                                    <div className="text-[11px] text-slate-500">Add certifications to populate this section.</div>
                                ) : null}
                            </div>
                        </SideSection>
                    )}
                </aside>
            </div>
        </div>
    );
}

function CertificationRow({
    cert,
    editMode,
    idx,
    onUpdate,
}: {
    cert: { name: string; issuer: string; year: string };
    editMode: boolean;
    idx: number;
    onUpdate: (index: number, field: 'name' | 'issuer' | 'year', value: string) => void;
}) {
    const name = String(cert?.name || '').trim();
    const issuer = String(cert?.issuer || '').trim();
    const year = String(cert?.year || '').trim();
    return (
        <div>
            <div className="text-[12px] font-semibold text-slate-900">
                {editMode ? (
                    <EditableText
                        value={name}
                        placeholder="Certification"
                        onChange={(v) => onUpdate(idx, 'name', v)}
                        editMode={editMode}
                        liveUpdate
                        layoutSafe
                        as="div"
                        className="text-[12px] font-semibold text-slate-900"
                    />
                ) : (
                    name
                )}
            </div>
            <div className="mt-0.5 text-[11px] text-slate-600">
                {editMode ? (
                    <>
                        <EditableText value={issuer} placeholder="Issuer" onChange={(v) => onUpdate(idx, 'issuer', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                        {(issuer && year) ? <span> • </span> : null}
                        <EditableText value={year} placeholder="Year" onChange={(v) => onUpdate(idx, 'year', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                    </>
                ) : (
                    [issuer, year].filter(Boolean).join(' • ')
                )}
            </div>
        </div>
    );
}

function MainSection({
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
    onTitleChange?: (value: string) => void;
}) {
    return (
        <section className="mb-7 last:mb-0">
            <h2 className="text-sm font-bold tracking-wide uppercase" style={{ color: 'var(--tv-primary)' }}>
                {editMode ? (
                    <EditableText
                        value={String(title || '')}
                        onChange={(v) => onTitleChange?.(v)}
                        editMode={!!editMode}
                        liveUpdate
                        layoutSafe
                        className="text-sm font-bold tracking-wide uppercase"
                        as="div"
                    />
                ) : (
                    title
                )}
            </h2>
            <div className="h-px mt-2 mb-4" style={{ backgroundColor: 'var(--tv-primary-dark)' }} />
            {panelTone === 'none' ? (
                children
            ) : (
                <div
                    className="rounded-md p-3"
                    style={{ backgroundColor: panelTone === 'secondary-dark' ? 'var(--tv-secondary-dark)' : 'var(--tv-secondary)' }}
                >
                    {children}
                </div>
            )}
        </section>
    );
}

function SideSection({
    title,
    children,
    panelTone = 'none',
    sectionKey,
    editMode,
    onTitleChange,
}: {
    title: string;
    children: React.ReactNode;
    panelTone?: 'none' | 'secondary' | 'secondary-dark';
    sectionKey?: string;
    editMode?: boolean;
    onTitleChange?: (value: string) => void;
}) {
    return (
        <section
            className="mb-7 last:mb-0"
            data-tv-section-key={sectionKey}
            tabIndex={sectionKey ? -1 : undefined}
        >
            <h2 className="text-sm font-bold tracking-wide uppercase" style={{ color: 'var(--tv-primary)' }}>
                {editMode ? (
                    <EditableText
                        value={String(title || '')}
                        onChange={(v) => onTitleChange?.(v)}
                        editMode={!!editMode}
                        liveUpdate
                        layoutSafe
                        className="text-sm font-bold tracking-wide uppercase"
                        as="div"
                    />
                ) : (
                    title
                )}
            </h2>
            <div className="h-px mt-2 mb-4" style={{ backgroundColor: 'var(--tv-primary-dark)' }} />
            {panelTone === 'none' ? (
                children
            ) : (
                <div
                    className="rounded-md p-3"
                    style={{ backgroundColor: panelTone === 'secondary-dark' ? 'var(--tv-secondary-dark)' : 'var(--tv-secondary)' }}
                >
                    {children}
                </div>
            )}
        </section>
    );
}

function InlineContact({ icon, value, href }: { icon: React.ReactNode; value: string; href?: string }) {
    return (
        <div className="inline-flex items-center gap-2">
            <span className="text-slate-500">{icon}</span>
            {href ? (
                <a href={href} target="_blank" rel="noreferrer" className="hover:underline underline-offset-2">
                    {value}
                </a>
            ) : (
                <span>{value}</span>
            )}
        </div>
    );
}

function ExperienceBlock({ exp, editMode, idx, onUpdate }: { exp: any; editMode: boolean; idx: number; onUpdate: (index: number, field: string, value: string) => void }) {
    const role = exp.title || exp.position || "Role";
    const dates = exp.duration || exp.dates || [exp.start, exp.end].filter(Boolean).join(" - ");
    const company = exp.company || exp.organization || "";
    const location = exp.location || exp.city || "";

    return (
        <div>
            {editMode ? (
                <EditableText value={String(role)} onChange={(v) => onUpdate(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-[12px] font-semibold text-slate-900" />
            ) : (
                <div className="text-[12px] font-semibold text-slate-900">{role}</div>
            )}
            <div className="mt-1 text-[11px] text-slate-600 flex flex-wrap items-center gap-x-2 gap-y-1">
                {editMode ? (
                    <>
                        <EditableText
                            value={String(company || '')}
                            placeholder="Company"
                            onChange={(v) => onUpdate(idx, 'company', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            as="span"
                            className="font-medium text-slate-700 inline"
                        />
                        <span className="text-slate-300">•</span>
                        <EditableText
                            value={String(dates || '')}
                            placeholder="Dates"
                            onChange={(v) => onUpdate(idx, 'duration', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            as="span"
                            className="inline"
                        />
                        <span className="text-slate-300">•</span>
                        <EditableText
                            value={String(location || '')}
                            placeholder="Location"
                            onChange={(v) => onUpdate(idx, 'location', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            as="span"
                            className="inline"
                        />
                    </>
                ) : (
                    <>
                        {company ? <span className="font-medium text-slate-700">{company}</span> : null}
                        {company && (dates || location) ? <span className="text-slate-300">•</span> : null}
                        {dates ? <span>{dates}</span> : null}
                        {dates && location ? <span className="text-slate-300">•</span> : null}
                        {location ? <span>{location}</span> : null}
                    </>
                )}
            </div>
            {(editMode || exp.description) ? (
                <div className="mt-2">
                    {editMode ? (
                        <AiAssistEditableText
                            value={String(exp.description)}
                            placeholder="Add bullets or a short description"
                            onChange={(v) => onUpdate(idx, 'description', v)}
                            editMode={editMode}
                            aiField="experience_description"
                            aiMeta={{ template: 'modern', index: idx, role: String(role), company: String(company) }}
                            liveUpdate
                            layoutSafe
                            wrapperClassName="pt-6"
                            as="div"
                            className="text-[11px] leading-relaxed text-slate-700"
                            multiline
                        />
                    ) : (
                        <RenderMaybeBullets
                            text={exp.description}
                            forceBullets
                            className="text-[11px] leading-relaxed text-slate-700"
                        />
                    )}
                </div>
            ) : null}
        </div>
    );
}

function LanguageRow({ name, level, editMode, idx, onUpdate }: { name: string; level: string; editMode: boolean; idx: number; onUpdate: (index: number, field: 'name' | 'level', value: string) => void }) {
    const dots = levelToDots(level);
    return (
        <div className="flex items-center justify-between gap-3">
            <div>
                {editMode ? (
                    <EditableText value={String(name)} onChange={(v) => onUpdate(idx, 'name', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-[12px] font-semibold text-slate-900" />
                ) : (
                    <div className="text-[12px] font-semibold text-slate-900">{name}</div>
                )}
                {editMode ? (
                    <EditableText value={String(level)} onChange={(v) => onUpdate(idx, 'level', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-[10px] text-slate-500" />
                ) : (
                    <div className="text-[10px] text-slate-500">{level}</div>
                )}
            </div>
            <div className="flex items-center gap-1">
                {Array.from({ length: 5 }).map((_, idx) => (
                    <span
                        key={idx}
                        className={`w-2 h-2 rounded-full ${idx < dots ? "bg-slate-600" : "bg-slate-200"}`}
                    />
                ))}
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

function normalizeLanguages(value: any): Array<{ name: string; level: string }> {
    if (!value) return [];
    if (Array.isArray(value)) {
        return value
            .map((l) => {
                if (typeof l === "string") return { name: l, level: "Proficient" };
                const name = l.name || l.language || l.label || "";
                const level = l.level || l.proficiency || l.rating || "";
                return { name: String(name), level: String(level || "Proficient") };
            })
            .filter((x) => x.name);
    }
    if (typeof value === "string") {
        return normalizeList(value).map((n) => ({ name: n, level: "Proficient" }));
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

function levelToDots(level: string): number {
    const s = String(level || "").toLowerCase();
    if (s.includes("native")) return 5;
    if (s.includes("fluent")) return 5;
    if (s.includes("advanced")) return 4;
    if (s.includes("proficient")) return 4;
    if (s.includes("intermediate")) return 3;
    if (s.includes("basic") || s.includes("beginner")) return 2;
    return 3;
}

function extractStrengths(sections: any): Array<{ title: string; body?: string }> {
    const out: Array<{ title: string; body?: string }> = [];
    const custom = Array.isArray(sections.custom_sections) ? sections.custom_sections : [];
    const match = custom.find((sec: any) => {
        const label = String(sec.title || sec.heading || sec.label || "").toLowerCase();
        return label.includes("strength");
    });
    if (match) {
        const items = Array.isArray(match.items) ? match.items : [];
        items.forEach((it: any) => {
            const title = it.title || it.name || it.label || "";
            const body = it.content || it.text || it.body || it.description || "";
            if (title) out.push({ title: String(title), body: body ? String(body) : undefined });
        });
        if (out.length > 0) return out;
    }

    // No explicit strengths section found.
    return [];
}




