import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Phone, MapPin, Mail, Globe } from "lucide-react";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import { AiAssistEditableText, EditableText } from "./EditableSection";
import SortableSectionList, { type SortableSectionRow } from "./SortableSectionList";

export default function ClassicRoseTemplate({
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

    const updateEducationYear = useCallback((index: number, value: string) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev?.education) ? [...prev.education] : [];
            updated[index] = { ...(updated[index] || {}), year: value, graduationDate: value };
            const next = { ...(prev || {}), education: updated };
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

    const updateLanguageItem = useCallback((index: number, value: string) => {
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

    const updateCertificationField = useCallback((index: number, field: 'name' | 'issuer' | 'year', value: string) => {
        setEditedData((prev: any) => {
            const current = normalizeCertifications(prev?.certifications);
            const nextArr = [...current];
            nextArr[index] = { ...(nextArr[index] || { name: '', issuer: '', year: '' }), [field]: value };
            const cleaned = nextArr.filter((c) => {
                const name = String((c as any)?.name || (c as any)?.title || '').trim();
                const issuer = String((c as any)?.issuer || '').trim();
                const year = String((c as any)?.year || (c as any)?.date || '').trim();
                return Boolean(name || issuer || year);
            });
            const next = { ...(prev || {}), certifications: cleaned };
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

    const data = editedData || {};
    const showEmpty = !!(editMode && (data as any)?._show_empty_sections);

    const getHeading = useCallback((key: string, fallback: string) => {
        const h = data?.section_headings?.[key];
        return String((typeof h === 'string' && h.trim() !== '') ? h : fallback);
    }, [data]);

    const skills = normalizeList(data.skills);
    const experience = Array.isArray(data.experience) ? data.experience : [];
    const education = Array.isArray(data.education) ? data.education : [];
    const projects = Array.isArray(data.projects) ? data.projects : [];
    const certifications = normalizeCertifications(data.certifications);
    const languages = normalizeList(data.languages);
    const customSections = Array.isArray(data.custom_sections) ? data.custom_sections : [];

    const mainRows: SortableSectionRow[] = useMemo(() => {
        const rows: SortableSectionRow[] = [];

        if (data.summary || showEmpty) {
            rows.push({
                key: 'summary',
                content: (
                    <Section title={getHeading('summary', 'Professional Statement')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('summary', v)}>
                        {(data.summary || showEmpty) && (
                            <div className="text-sm leading-relaxed text-slate-700">
                                {editMode ? (
                                    <AiAssistEditableText value={String(data.summary || '')} onChange={(v) => updateField('summary', v)} editMode={editMode} aiField="summary" aiMeta={{ template: 'classicRose', section: 'summary' }} liveUpdate layoutSafe wrapperClassName="pt-6" as="div" multiline />
                                ) : (
                                    <p>{String(data.summary || '')}</p>
                                )}
                            </div>
                        )}
                    </Section>
                ),
            });
        }

        if (experience.length > 0 || showEmpty) {
            rows.push({
                key: 'experience',
                content: (
                    <Section title={getHeading('experience', 'Work Experience')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('experience', v)}>
                        <div className="space-y-5">
                            {(experience.length > 0 || showEmpty) ? (
                                experience.slice(0, 5).map((exp: any, idx: number) => {
                                    const dates = exp.duration || (exp.startDate && exp.endDate ? `${exp.startDate} / ${exp.currentlyWorking ? 'Present' : exp.endDate}` : '') || [exp.start, exp.end].filter(Boolean).join(" / ");
                                    return (
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
                                            <div className="font-semibold text-sm text-slate-800">
                                                {editMode ? (
                                                    <>
                                                        <EditableText value={String(exp.title || exp.position || '')} onChange={(v) => updateExperience(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="span" placeholder="Role" />
                                                        {(exp.company || editMode) && (
                                                            <> | <EditableText value={String(exp.company || exp.employer || '')} onChange={(v) => updateExperience(idx, 'company', v)} editMode={editMode} liveUpdate layoutSafe as="span" placeholder="Company" /></>
                                                        )}
                                                    </>
                                                ) : (
                                                    `${exp.title || exp.position || ''}${exp.company ? ' | ' + exp.company : ''}`
                                                )}
                                            </div>
                                            <div className="text-xs text-slate-500 mb-1.5">{editMode ? <EditableText value={String(dates)} onChange={(v) => updateExperience(idx, 'duration', v)} editMode={editMode} liveUpdate layoutSafe as="span" placeholder="Dates" /> : dates}</div>
                                            {(editMode || exp.description) && (
                                                <div className="text-sm leading-relaxed text-slate-700">
                                                    {editMode ? (
                                                        <AiAssistEditableText value={String(exp.description)} onChange={(v) => updateExperience(idx, 'description', v)} editMode={editMode} aiField="experience_description" aiMeta={{ template: 'classicRose', index: idx, role: String(exp.title || exp.position || ''), company: String(exp.company || '') }} liveUpdate layoutSafe wrapperClassName="pt-6" as="div" multiline />
                                                    ) : (
                                                        <RenderMaybeBullets text={exp.description} forceBullets className="text-sm leading-relaxed" />
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })
                            ) : (
                                <div className="text-sm text-slate-500">Add experience</div>
                            )}
                        </div>
                    </Section>
                ),
            });
        }

        if (projects.length > 0 || showEmpty) {
            rows.push({
                key: 'projects',
                content: (
                    <Section title={getHeading('projects', 'Projects')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('projects', v)}>
                        <div className="space-y-5">
                            {(projects.length > 0 || showEmpty) ? (
                                projects.slice(0, 5).map((proj: any, idx: number) => (
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
                                        <div className="font-semibold text-sm text-slate-800">
                                            {editMode ? (
                                                <>
                                                    <EditableText value={String(proj.title || proj.name || '')} onChange={(v) => updateProject(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="span" placeholder="Project Title" />
                                                    {proj.link ? (
                                                        <span className="text-xs text-slate-600 ml-2 whitespace-nowrap align-middle inline-flex items-center gap-1">
                                                            <EditableText
                                                                value={String(formatLinkLabel(proj.link))}
                                                                onChange={(v) => updateProject(idx, 'link', v)}
                                                                editMode={editMode}
                                                                liveUpdate
                                                                layoutSafe
                                                                as="span"
                                                                className="inline"
                                                            />
                                                        </span>
                                                    ) : null}
                                                </>
                                            ) : (
                                                `${proj.title || proj.name || 'Project'}${proj.link ? ` ${formatLinkLabel(proj.link)}` : ''}`
                                            )}
                                        </div>
                                        {(editMode || proj.dates || proj.duration) && (
                                            <div className="text-xs text-slate-500">
                                                {editMode ? (
                                                    <EditableText
                                                        value={String(proj.dates || proj.duration || '')}
                                                        onChange={(v) => updateProject(idx, 'dates', v)}
                                                        editMode={editMode}
                                                        liveUpdate
                                                        layoutSafe
                                                        as="span"
                                                        placeholder="Dates"
                                                    />
                                                ) : (
                                                    String(proj.dates || proj.duration || '')
                                                )}
                                            </div>
                                        )}
                                        {proj.technologies ? (
                                            <div className="text-xs text-slate-600">{editMode ? <EditableText value={String(proj.technologies)} onChange={(v) => updateProject(idx, 'technologies', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : proj.technologies}</div>
                                        ) : null}
                                        {(editMode || proj.description) && (
                                            <div className="text-sm leading-relaxed text-slate-700 mt-1">
                                                {editMode ? (
                                                    <AiAssistEditableText value={String(proj.description)} onChange={(v) => updateProject(idx, 'description', v)} editMode={editMode} aiField="project_description" aiMeta={{ template: 'classicRose', index: idx, title: String(proj.title || proj.name || 'Project') }} liveUpdate layoutSafe wrapperClassName="pt-6" as="div" multiline />
                                                ) : (
                                                    <RenderMaybeBullets text={proj.description} forceBullets className="text-sm leading-relaxed" />
                                                )}
                                            </div>
                                        )}
                                    </div>
                                ))
                            ) : (
                                <div className="text-sm text-slate-500">Add projects</div>
                            )}
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
                    content: (
                        <Section key={idx} title={heading} editMode={editMode} onTitleChange={(v) => updateCustomHeading(idx, v)}>
                            <CustomSectionsRenderer
                                customSections={[sec]}
                                editMode={editMode}
                                onHeadingChange={(sIdx, v) => updateCustomHeading(idx + sIdx, v)}
                                onItemChange={(sIdx, iIdx, field, v) => updateCustomItem(idx + sIdx, iIdx, field, v)}
                                onBodyChange={(sIdx, v) => updateCustomBody(idx + sIdx, v)}
                                showSectionHeadings={false}
                                headingClassName="text-sm font-semibold text-slate-800"
                                itemTitleClassName="text-sm font-semibold text-slate-800"
                                itemMetaClassName="text-xs text-slate-500"
                                itemBodyClassName="text-sm leading-relaxed text-slate-700"
                            />
                        </Section>
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
        removeExperienceItem,
        removeProjectItem,
    ]);

    const website = getPrimaryWebsite(data);
    const hasContactInfo = Boolean(data.location || data.phone || data.email || website || editMode);

    const nameParts = String(data.name || "Your Name").trim().split(/\s+/);
    const professionalTitle = String(data.title || '').trim();
    const firstName = nameParts[0] || "Your";
    const lastName = nameParts.slice(1).join(" ") || "Name";

    return (
        <div data-template="classicrose" className="bg-white rounded-lg shadow-lg ring-1 ring-black/5 overflow-hidden max-w-5xl mx-auto">
            <div className="bg-white min-h-[900px] flex flex-col">
                <div className="px-8 flex-1 flex flex-col">
                    <div
                        className="-mx-8 px-8 pt-8 pb-6 border-b"
                        style={{ backgroundColor: 'var(--tv-secondary-dark)', borderColor: 'var(--tv-primary-dark)' }}
                    >
                        {/* Header: Name (first dark, last rose) + title centered */}
                        <div className="text-center">
                            <h1 className="text-2xl sm:text-3xl font-bold uppercase tracking-tight">
                                <span className="text-slate-800">
                                    {editMode ? (
                                        <EditableText value={firstName} onChange={(v) => {
                                            const rest = nameParts.slice(1).join(" ");
                                            updateField('name', [v, rest].filter(Boolean).join(" "));
                                        }} editMode={editMode} liveUpdate layoutSafe as="span" className="text-slate-800" />
                                    ) : (
                                        firstName
                                    )}
                                </span>
                                {" "}
                                <span style={{ color: 'var(--tv-primary-dark)' }}>
                                    {editMode ? (
                                        <EditableText value={lastName} onChange={(v) => {
                                            updateField('name', [firstName, v].filter(Boolean).join(" "));
                                        }} editMode={editMode} liveUpdate layoutSafe as="span" />
                                    ) : (
                                        lastName
                                    )}
                                </span>
                            </h1>
                            {(editMode || professionalTitle) ? (
                                <div className="text-sm font-normal text-slate-700 uppercase tracking-wide mt-1">
                                    {editMode ? (
                                        <EditableText value={String(data.title || '')} placeholder="Professional Title" onChange={(v) => updateField('title', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-sm text-slate-700" />
                                    ) : (
                                        professionalTitle
                                    )}
                                </div>
                            ) : null}

                            {hasContactInfo ? (
                                <div className="mt-4 pt-3 border-t" style={{ borderColor: 'var(--tv-primary-dark)' }}>
                                    <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-sm text-slate-700">
                                        {(data.location || editMode) && (
                                            <ContactRow icon={<MapPin className="w-3.5 h-3.5" />} value={String(data.location || '')} editMode={editMode} onChange={(v) => updateField('location', v)} compact />
                                        )}
                                        {(data.phone || editMode) && (
                                            <ContactRow icon={<Phone className="w-3.5 h-3.5" />} value={String(data.phone || '')} editMode={editMode} onChange={(v) => updateField('phone', v)} compact />
                                        )}
                                        {(data.email || editMode) && (
                                            <ContactRow icon={<Mail className="w-3.5 h-3.5" />} value={String(data.email || '')} editMode={editMode} onChange={(v) => updateField('email', v)} compact />
                                        )}
                                        {(website || editMode) && (
                                            <ContactRow icon={<Globe className="w-3.5 h-3.5" />} value={String(website || '')} editMode={editMode} onChange={(v) => updateField('website', v)} compact />
                                        )}
                                    </div>
                                </div>
                            ) : null}
                        </div>
                    </div>

                    <div className="-mx-8 flex-1 grid grid-cols-12 grid-rows-1 gap-0">
                        {/* LEFT COLUMN */}
                        <aside
                            className="col-span-4 border-r px-6 py-6 h-full"
                            style={{ borderColor: 'var(--tv-primary-dark)', backgroundColor: 'var(--tv-secondary)' }}
                        >
                            <Section sectionKey="education" title={getHeading('education', 'Education')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('education', v)}>
                                <div className="space-y-4">
                                    {(education.length > 0 || showEmpty) ? (
                                        education.slice(0, 5).map((edu: any, idx: number) => (
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
                                                <div className="font-semibold text-sm text-slate-800">
                                                    {editMode ? <EditableText value={String(edu.degree || edu.title || '')} onChange={(v) => updateEducation(idx, 'degree', v)} editMode={editMode} liveUpdate layoutSafe as="span" placeholder="Degree" /> : (edu.degree || edu.title || '')}
                                                </div>
                                                <div className="text-xs text-slate-600">{editMode ? <EditableText value={String(edu.school || edu.institution || '')} onChange={(v) => updateEducation(idx, 'school', v)} editMode={editMode} liveUpdate layoutSafe as="span" placeholder="School / Institution" /> : (edu.school || edu.institution || '')}</div>
                                                <div className="text-xs text-slate-500">
                                                    {editMode ? (
                                                        <EditableText
                                                            value={firstMeaningfulValue(edu.year, edu.graduationDate)}
                                                            onChange={(v) => updateEducationYear(idx, v)}
                                                            editMode={editMode}
                                                            liveUpdate
                                                            layoutSafe
                                                            as="span"
                                                            placeholder="Year"
                                                        />
                                                    ) : (
                                                        firstMeaningfulValue(edu.year, edu.graduationDate)
                                                    )}
                                                </div>
                                                {(editMode || String(edu?.gpa ?? '').trim()) ? (
                                                    <div className="text-xs text-slate-500">
                                                        {editMode ? (
                                                            <EditableText
                                                                value={String(edu?.gpa ?? '')}
                                                                onChange={(v) => updateEducation(idx, 'gpa', v)}
                                                                editMode={editMode}
                                                                liveUpdate
                                                                layoutSafe
                                                                as="span"
                                                                placeholder="GPA"
                                                            />
                                                        ) : (
                                                            `GPA: ${String(edu?.gpa ?? '').trim()}`
                                                        )}
                                                    </div>
                                                ) : null}
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-xs text-slate-500">Add education</div>
                                    )}
                                </div>
                            </Section>

                            {(certifications.length > 0 || showEmpty) && (
                                <Section sectionKey="certifications" title={getHeading('certifications', 'Certifications')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('certifications', v)}>
                                    <div className="space-y-3">
                                        {certifications.map((c: any, idx: number) => {
                                            if (typeof c === 'string') {
                                                return (
                                                    <div key={idx} className="relative group text-sm text-slate-700">
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
                                            const year = firstMeaningfulValue(c?.year, c?.date);

                                            return (
                                                <div key={idx} className="relative group">
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
                                                    <div className="font-semibold text-sm text-slate-800">
                                                        {editMode ? (
                                                            <EditableText
                                                                value={name}
                                                                placeholder="Certification"
                                                                onChange={(v) => updateCertificationField(idx, 'name', v)}
                                                                editMode={editMode}
                                                                liveUpdate
                                                                layoutSafe
                                                                as="span"
                                                                className="inline"
                                                            />
                                                        ) : (
                                                            name || 'Certification'
                                                        )}
                                                    </div>
                                                    {(issuer || year || editMode) ? (
                                                        <div className="text-xs text-slate-500">
                                                            {editMode ? (
                                                                <>
                                                                    <EditableText value={issuer} placeholder="Issuer" onChange={(v) => updateCertificationField(idx, 'issuer', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                                    {(issuer && year) ? <span> • </span> : null}
                                                                    <EditableText value={year} placeholder="Year" onChange={(v) => updateCertificationField(idx, 'year', v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                                </>
                                                            ) : (
                                                                [issuer, year].filter(Boolean).join(' • ')
                                                            )}
                                                        </div>
                                                    ) : null}
                                                </div>
                                            );
                                        })}
                                        {certifications.length === 0 ? (
                                            <div className="text-xs text-slate-500">Add certifications</div>
                                        ) : null}
                                    </div>
                                </Section>
                            )}

                            {(languages.length > 0 || showEmpty) && (
                                <Section title={getHeading('languages', 'Languages')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('languages', v)}>
                                    <div className="space-y-1.5">
                                        {languages.map((l, idx) => (
                                            <div key={idx} className="text-sm text-slate-700">
                                                {editMode ? (
                                                    <EditableText
                                                        value={String(l)}
                                                        onChange={(v) => updateLanguageItem(idx, v)}
                                                        editMode={editMode}
                                                        liveUpdate
                                                        layoutSafe
                                                        as="span"
                                                        className="inline"
                                                    />
                                                ) : (
                                                    String(l)
                                                )}
                                            </div>
                                        ))}
                                        {languages.length === 0 ? (
                                            <div className="text-xs text-slate-500">Add languages</div>
                                        ) : null}
                                    </div>
                                </Section>
                            )}

                            <Section title={getHeading('skills', 'Skills')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('skills', v)}>
                                <div className="space-y-1.5">
                                    {(skills.length > 0 || showEmpty) ? (
                                        skills.slice(0, 12).map((s, idx) => (
                                            <div key={idx} className="text-sm text-slate-700">
                                                {editMode ? (
                                                    <EditableText value={s} onChange={(v) => updateSkill(idx, v)} editMode={editMode} liveUpdate layoutSafe as="span" />
                                                ) : (
                                                    s
                                                )}
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-xs text-slate-500">Add skills</div>
                                    )}
                                </div>
                            </Section>
                        </aside>

                        {/* RIGHT COLUMN */}
                        <main className={`col-span-8 px-8 py-6 h-full ${editMode ? 'pl-10' : ''}`}>
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
            </div>
        </div>
    );
}

function Section({ title, children, editMode, onTitleChange, sectionKey }: { title: string; children: React.ReactNode; editMode?: boolean; onTitleChange?: (v: string) => void; sectionKey?: string }) {
    return (
        <section
            className="mb-6 last:mb-0"
            data-tv-section-key={sectionKey}
            tabIndex={sectionKey ? -1 : undefined}
        >
            <h3 className="text-xs font-semibold uppercase tracking-wide text-center mb-2" style={{ color: 'var(--tv-primary-dark)' }}>
                {editMode ? (
                    <EditableText value={title} onChange={(v) => onTitleChange?.(v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-center" />
                ) : (
                    `- ${title} -`
                )}
            </h3>
            <div className="h-px mb-3" style={{ backgroundColor: 'var(--tv-primary-dark)' }} />
            {children}
        </section>
    );
}

function ContactRow({ icon, value, editMode, onChange, compact = false }: { icon?: React.ReactNode; value: string; editMode?: boolean; onChange?: (v: string) => void; compact?: boolean }) {
    return (
        <div className={`flex gap-2 ${compact ? 'items-center' : 'items-start'}`}>
            {icon ? <span className={`text-slate-500 flex-shrink-0 ${compact ? '' : 'mt-0.5'}`}>{icon}</span> : null}
            <div className="text-slate-700 break-words flex-1">
                {editMode ? (
                    <EditableText value={String(value || '')} onChange={(v) => onChange?.(v)} editMode={!!editMode} liveUpdate layoutSafe as="div" className="text-sm" />
                ) : (
                    value || '—'
                )}
            </div>
        </div>
    );
}

function normalizeList(value: any): string[] {
    if (Array.isArray(value)) {
        return value.map((item) => (typeof item === "string" ? item : item?.name || item?.label || "")).map((s) => String(s).trim()).filter(Boolean);
    }
    if (typeof value === "string") {
        return value.split(/[,•\n]/g).map((s) => s.trim()).filter(Boolean);
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

function getPrimaryWebsite(data: any): string {
    const direct =
        data?.website ||
        data?.portfolio ||
        data?.linkedin ||
        data?.github ||
        data?.contact?.website ||
        data?.contact?.portfolio ||
        data?.contact?.linkedin ||
        data?.contact?.github ||
        data?.personalInfo?.website ||
        data?.personalInfo?.portfolio ||
        "";
    if (String(direct || '').trim()) return String(direct).trim();

    const links = Array.isArray(data?.links)
        ? data.links
        : (data?.links && typeof data.links === 'object')
            ? Object.values(data.links)
            : [];
    for (const link of links) {
        if (!link) continue;
        if (typeof link === 'string' && link.trim()) return link.trim();
        if (typeof link === 'object') {
            const candidate =
                link.url ||
                link.href ||
                link.link ||
                link.value ||
                link.website ||
                link.profile ||
                link.linkedin ||
                link.github ||
                '';
            if (String(candidate).trim()) return String(candidate).trim();

            // Final fallback: search nested object fields for first URL-like value.
            for (const v of Object.values(link)) {
                const s = String(v ?? '').trim();
                if (!s) continue;
                if (/^(https?:\/\/|www\.)/i.test(s) || /\.[a-z]{2,}(\/|$)/i.test(s)) {
                    return s;
                }
            }
        }
    }
    return '';
}

function formatLinkLabel(link: any): string {
    const raw = String(link || '').trim();
    if (!raw) return '';
    try {
        const normalized = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
        const host = new URL(normalized).hostname.replace(/^www\./i, '');
        return host || raw;
    } catch {
        return raw.replace(/^https?:\/\//i, '').replace(/^www\./i, '').split('/')[0] || raw;
    }
}

function cleanPlaceholderValue(value: any): string {
    const v = String(value ?? '').trim();
    if (!v) return '';
    if (v.toLowerCase() === 'n/a') return '';
    return v;
}

function firstMeaningfulValue(...values: any[]): string {
    for (const v of values) {
        const cleaned = cleanPlaceholderValue(v);
        if (cleaned) return cleaned;
    }
    return '';
}
