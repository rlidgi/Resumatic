import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { parseResumeContent } from '../../utils/resumeUtils';
import { RenderMaybeBullets } from './RenderMaybeBullets';
import { EditableText } from './EditableSection';
import CustomSectionsRenderer from './CustomSectionsRenderer';
import AddSectionButton from './AddSectionButton';
import SortableSectionList, { type SortableSectionRow } from './SortableSectionList';

export default function ProfessionalTemplate({
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
    const parsed = useMemo(() => parseResumeContent(content), [content]);
    const [editedData, setEditedData] = useState<any>(parsed);

    useEffect(() => {
        setEditedData(parsed);
    }, [parsed]);

    const emit = useCallback((next: any) => {
        if (onContentChange) onContentChange(next);
    }, [onContentChange]);

    const updateField = useCallback((field: string, value: string) => {
        setEditedData((prev: any) => {
            const next = { ...prev, [field]: value };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateExperience = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev.experience) ? [...prev.experience] : [];
            updated[index] = { ...(updated[index] || {}), [field]: value };
            const next = { ...prev, experience: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateEducation = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev.education) ? [...prev.education] : [];
            updated[index] = { ...(updated[index] || {}), [field]: value };
            const next = { ...prev, education: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateProject = useCallback((index: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const updated = Array.isArray(prev.projects) ? [...prev.projects] : [];
            updated[index] = { ...(updated[index] || {}), [field]: value };
            const next = { ...prev, projects: updated };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateSectionHeading = useCallback((key: string, heading: string) => {
        setEditedData((prev: any) => {
            const prevHeadings = (prev && typeof prev.section_headings === 'object' && prev.section_headings) ? prev.section_headings : {};
            const nextHeadings = { ...prevHeadings, [key]: heading };
            const next = { ...prev, section_headings: nextHeadings };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateCustomSectionHeading = useCallback((sectionIndex: number, heading: string) => {
        setEditedData((prev: any) => {
            const sectionsArr = Array.isArray(prev.custom_sections) ? [...prev.custom_sections] : [];
            const current = sectionsArr[sectionIndex] || {};
            sectionsArr[sectionIndex] = { ...(current || {}), heading };
            const next = { ...prev, custom_sections: sectionsArr };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateCustomSectionItem = useCallback((sectionIndex: number, itemIndex: number, field: string, value: string) => {
        setEditedData((prev: any) => {
            const sectionsArr = Array.isArray(prev.custom_sections) ? [...prev.custom_sections] : [];
            const currentSection = sectionsArr[sectionIndex] || {};
            const items = Array.isArray(currentSection.items) ? [...currentSection.items] : [];
            const currentItem = (items[itemIndex] && typeof items[itemIndex] === 'object') ? items[itemIndex] : {};
            items[itemIndex] = { ...(currentItem || {}), [field]: value };
            sectionsArr[sectionIndex] = { ...(currentSection || {}), items };
            const next = { ...prev, custom_sections: sectionsArr };
            emit(next);
            return next;
        });
    }, [emit]);

    const updateCustomSectionBody = useCallback((sectionIndex: number, value: string) => {
        setEditedData((prev: any) => {
            const sectionsArr = Array.isArray(prev.custom_sections) ? [...prev.custom_sections] : [];
            const currentSection = sectionsArr[sectionIndex] || {};
            sectionsArr[sectionIndex] = { ...(currentSection || {}), content: value };
            const next = { ...prev, custom_sections: sectionsArr };
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

    const updateSkillsFromText = useCallback((value: string) => {
        const skills = String(value || '')
            .split(/\n|,|•/g)
            .map((s) => s.trim())
            .filter(Boolean);
        setEditedData((prev: any) => {
            const next = { ...prev, skills };
            emit(next);
            return next;
        });
    }, [emit]);

    const sections = editedData || {};

    const getHeading = useCallback((key: string, fallback: string) => {
        const h = sections?.section_headings?.[key];
        return String((typeof h === 'string' && h.trim() !== '') ? h : fallback);
    }, [sections]);

    const sectionHeadingClass = useCallback((compact: boolean) => (
        compact
            ? 'text-xs font-bold text-slate-900 tracking-wider uppercase border-b-2 border-slate-300 pb-1 mb-2'
            : 'text-xs font-bold text-slate-900 tracking-wider uppercase border-b-2 border-slate-300 pb-1.5 mb-3'
    ), []);

    const customSections = Array.isArray(sections.custom_sections) ? sections.custom_sections : [];

    const rows: SortableSectionRow[] = [];

    if (String(sections.summary || '').trim()) {
        rows.push({
            key: 'summary',
            title: getHeading('summary', 'Professional Summary'),
            content: (
                <Section
                    title={getHeading('summary', 'Professional Summary')}
                    compact={editMode}
                    titleNode={editMode ? (
                        <EditableText
                            value={getHeading('summary', 'Professional Summary')}
                            onChange={(v) => updateSectionHeading('summary', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className={sectionHeadingClass(true)}
                            as="h3"
                        />
                    ) : undefined}
                >
                    {editMode ? (
                        <EditableText
                            value={String(sections.summary || '')}
                            onChange={(v) => updateField('summary', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className="text-slate-700 leading-snug text-sm"
                            as="div"
                            multiline
                        />
                    ) : (
                        <p className="text-slate-700 leading-snug text-sm">{sections.summary}</p>
                    )}
                </Section>
            ),
        });
    }

    if (Array.isArray(sections.experience) && sections.experience.length > 0) {
        rows.push({
            key: 'experience',
            title: getHeading('experience', 'Professional Experience'),
            content: (
                <Section
                    title={getHeading('experience', 'Professional Experience')}
                    compact={editMode}
                    titleNode={editMode ? (
                        <EditableText
                            value={getHeading('experience', 'Professional Experience')}
                            onChange={(v) => updateSectionHeading('experience', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className={sectionHeadingClass(true)}
                            as="h3"
                        />
                    ) : undefined}
                >
                    {sections.experience.map((exp: any, idx: number) => (
                        <div key={idx} className="mb-4 last:mb-0">
                            <div className="flex justify-between items-start mb-1.5 gap-3">
                                <div>
                                    {editMode ? (
                                        <>
                                            <EditableText
                                                value={String(exp.title || '')}
                                                onChange={(v) => updateExperience(idx, 'title', v)}
                                                editMode={editMode}
                                                liveUpdate
                                                layoutSafe
                                                className="font-bold text-slate-900 text-base"
                                                as="div"
                                            />
                                            <EditableText
                                                value={String(exp.company || '')}
                                                onChange={(v) => updateExperience(idx, 'company', v)}
                                                editMode={editMode}
                                                liveUpdate
                                                layoutSafe
                                                className="text-slate-700 font-medium text-sm"
                                                as="div"
                                            />
                                        </>
                                    ) : (
                                        <>
                                            <h4 className="font-bold text-slate-900 text-base">{exp.title}</h4>
                                            <p className="text-slate-700 font-medium text-sm">{exp.company}</p>
                                        </>
                                    )}
                                </div>
                                {editMode ? (
                                    <EditableText
                                        value={String(exp.duration || '')}
                                        onChange={(v) => updateExperience(idx, 'duration', v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        className="text-xs text-slate-600 font-medium whitespace-nowrap"
                                        as="div"
                                    />
                                ) : (
                                    <span className="text-xs text-slate-600 font-medium whitespace-nowrap">{exp.duration}</span>
                                )}
                            </div>
                            {editMode ? (
                                <EditableText
                                    value={String(exp.description || '')}
                                    onChange={(v) => updateExperience(idx, 'description', v)}
                                    editMode={editMode}
                                    liveUpdate
                                    layoutSafe
                                    className="text-slate-700 leading-snug text-sm"
                                    as="div"
                                    multiline
                                />
                            ) : (
                                <RenderMaybeBullets
                                    text={exp.description}
                                    forceBullets
                                    className="text-slate-700 leading-snug text-sm"
                                />
                            )}
                        </div>
                    ))}
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
                    <Section
                        title={heading}
                        compact={editMode}
                        titleNode={editMode ? (
                            <EditableText
                                value={String(sec?.heading || '')}
                                onChange={(v) => updateCustomSectionHeading(idx, v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                className={sectionHeadingClass(true)}
                                as="h3"
                            />
                        ) : null}
                    >
                        <CustomSectionsRenderer
                            customSections={[sec]}
                            editMode={editMode}
                            showSectionHeadings={false}
                            headingClassName={sectionHeadingClass(Boolean(editMode))}
                            itemTitleClassName="text-sm font-semibold text-slate-900"
                            itemMetaClassName="text-xs text-slate-500"
                            itemBodyClassName="text-slate-700 leading-snug text-sm"
                            onHeadingChange={(sIdx, value) => updateCustomSectionHeading(idx + sIdx, value)}
                            onItemChange={(sIdx, itemIndex, field, value) => updateCustomSectionItem(idx + sIdx, itemIndex, String(field), value)}
                            onBodyChange={(sIdx, value) => updateCustomSectionBody(idx + sIdx, value)}
                        />
                    </Section>
                ),
            });
        });
    }

    if (Array.isArray(sections.education) && sections.education.length > 0) {
        rows.push({
            key: 'education',
            title: getHeading('education', 'Education'),
            content: (
                <Section
                    title={getHeading('education', 'Education')}
                    compact={editMode}
                    titleNode={editMode ? (
                        <EditableText
                            value={getHeading('education', 'Education')}
                            onChange={(v) => updateSectionHeading('education', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className={sectionHeadingClass(true)}
                            as="h3"
                        />
                    ) : undefined}
                >
                    {sections.education.map((edu: any, idx: number) => (
                        <div key={idx} className="mb-2.5 last:mb-0 flex justify-between items-start gap-3">
                            <div>
                                {editMode ? (
                                    <>
                                        <EditableText
                                            value={String(edu.degree || '')}
                                            onChange={(v) => updateEducation(idx, 'degree', v)}
                                            editMode={editMode}
                                            liveUpdate
                                            layoutSafe
                                            className="font-bold text-slate-900 text-sm"
                                            as="div"
                                        />
                                        <EditableText
                                            value={String(edu.institution || '')}
                                            onChange={(v) => updateEducation(idx, 'institution', v)}
                                            editMode={editMode}
                                            liveUpdate
                                            layoutSafe
                                            className="text-slate-700 text-sm"
                                            as="div"
                                        />
                                    </>
                                ) : (
                                    <>
                                        <h4 className="font-bold text-slate-900 text-sm">{edu.degree}</h4>
                                        <p className="text-slate-700 text-sm">{edu.institution}</p>
                                    </>
                                )}
                            </div>
                            {editMode ? (
                                <EditableText
                                    value={String(edu.year || '')}
                                    onChange={(v) => updateEducation(idx, 'year', v)}
                                    editMode={editMode}
                                    liveUpdate
                                    layoutSafe
                                    className="text-xs text-slate-600 font-medium whitespace-nowrap"
                                    as="div"
                                />
                            ) : (
                                <span className="text-xs text-slate-600 font-medium whitespace-nowrap">{edu.year}</span>
                            )}
                        </div>
                    ))}
                </Section>
            ),
        });
    }

    if (Array.isArray(sections.projects) && sections.projects.length > 0) {
        rows.push({
            key: 'projects',
            title: getHeading('projects', 'Projects'),
            content: (
                <Section
                    title={getHeading('projects', 'Projects')}
                    compact={editMode}
                    titleNode={editMode ? (
                        <EditableText
                            value={getHeading('projects', 'Projects')}
                            onChange={(v) => updateSectionHeading('projects', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className={sectionHeadingClass(true)}
                            as="h3"
                        />
                    ) : undefined}
                >
                    {sections.projects.map((proj: any, idx: number) => (
                        <div key={idx} className="mb-4 last:mb-0">
                            <div className="flex justify-between items-start mb-1 gap-3">
                                {editMode ? (
                                    <EditableText
                                        value={String(proj.title || '')}
                                        onChange={(v) => updateProject(idx, 'title', v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        className="font-bold text-slate-900 text-base"
                                        as="div"
                                    />
                                ) : (
                                    <h4 className="font-bold text-slate-900 text-base">{proj.title}</h4>
                                )}
                                {proj.link && (
                                    <a
                                        href={proj.link}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-xs text-slate-700 underline underline-offset-2 hover:text-slate-900 whitespace-nowrap"
                                    >
                                        Link
                                    </a>
                                )}
                            </div>
                            {editMode ? (
                                <>
                                    <EditableText
                                        value={String(proj.technologies || '')}
                                        onChange={(v) => updateProject(idx, 'technologies', v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        className="text-xs text-slate-600 mb-1.5"
                                        as="div"
                                    />
                                    <EditableText
                                        value={String(proj.description || '')}
                                        onChange={(v) => updateProject(idx, 'description', v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        className="text-slate-700 leading-snug text-sm"
                                        as="div"
                                        multiline
                                    />
                                </>
                            ) : (
                                <>
                                    {proj.technologies && (
                                        <p className="text-xs text-slate-600 mb-1.5">{proj.technologies}</p>
                                    )}
                                    {proj.description && (
                                        <p className="text-slate-700 leading-snug text-sm">{proj.description}</p>
                                    )}
                                </>
                            )}
                        </div>
                    ))}
                </Section>
            ),
        });
    }

    if (Array.isArray(sections.certifications) && sections.certifications.length > 0) {
        rows.push({
            key: 'certifications',
            title: getHeading('certifications', 'Certifications'),
            content: (
                <Section
                    title={getHeading('certifications', 'Certifications')}
                    compact={editMode}
                    titleNode={editMode ? (
                        <EditableText
                            value={getHeading('certifications', 'Certifications')}
                            onChange={(v) => updateSectionHeading('certifications', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className={sectionHeadingClass(true)}
                            as="h3"
                        />
                    ) : undefined}
                >
                    <div className="space-y-3">
                        {sections.certifications.map((cert: any, idx: number) => {
                            if (typeof cert === 'string') {
                                return (
                                    <div key={idx} className="text-slate-700 text-sm">
                                        • {cert}
                                    </div>
                                );
                            }

                            const name = cert?.name || '';
                            const issuer = cert?.issuer || '';
                            const year = cert?.year || '';

                            return (
                                <div key={idx} className="flex items-baseline justify-between gap-4">
                                    <div className="min-w-0">
                                        <div className="font-bold text-slate-900 text-sm">{name}</div>
                                        {(issuer || year) && (
                                            <div className="text-xs text-slate-600">
                                                {[issuer, year].filter(Boolean).join(' • ')}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </Section>
            ),
        });
    }

    if (Array.isArray(sections.skills) && sections.skills.length > 0) {
        rows.push({
            key: 'skills',
            title: getHeading('skills', 'Core Competencies'),
            content: (
                <Section
                    title={getHeading('skills', 'Core Competencies')}
                    compact={editMode}
                    titleNode={editMode ? (
                        <EditableText
                            value={getHeading('skills', 'Core Competencies')}
                            onChange={(v) => updateSectionHeading('skills', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className={sectionHeadingClass(true)}
                            as="h3"
                        />
                    ) : undefined}
                >
                    {editMode ? (
                        <EditableText
                            value={Array.isArray(sections.skills) ? sections.skills.join('\n') : ''}
                            onChange={(v) => updateSkillsFromText(v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className="text-slate-700 font-medium text-sm"
                            as="div"
                            multiline
                        />
                    ) : (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                            {sections.skills.map((skill: string, idx: number) => (
                                <div key={idx} className="text-slate-700 font-medium text-sm">
                                    • {skill}
                                </div>
                            ))}
                        </div>
                    )}
                </Section>
            ),
        });
    }

    return (
        <div className="bg-white rounded-lg shadow-xl overflow-hidden max-w-4xl mx-auto border-t-4 border-slate-800">
            {/* Header */}
            <div className="border-b-2 border-slate-800 p-6 text-center">
                {editMode ? (
                    <>
                        <EditableText
                            value={String(sections.name || 'YOUR NAME')}
                            onChange={(v) => updateField('name', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className="text-3xl font-bold text-slate-900 mb-1.5"
                            as="h1"
                        />
                        <EditableText
                            value={String(sections.title || 'Professional Title')}
                            onChange={(v) => updateField('title', v)}
                            editMode={editMode}
                            liveUpdate
                            layoutSafe
                            className="text-base text-slate-700 font-medium mb-2"
                            as="p"
                        />
                    </>
                ) : (
                    <>
                        <h1 className="text-3xl font-bold text-slate-900 mb-1.5">{sections.name || 'YOUR NAME'}</h1>
                        <p className="text-base text-slate-700 font-medium mb-2">{sections.title || 'Professional Title'}</p>
                    </>
                )}
                <div className="flex justify-center flex-wrap gap-3 text-xs text-slate-600">
                    {editMode ? (
                        <>
                            <EditableText
                                value={String(sections.email || '')}
                                onChange={(v) => updateField('email', v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                className=""
                                as="span"
                            />
                            {(String(sections.email || '').trim() && String(sections.phone || '').trim()) ? <span>•</span> : null}
                            <EditableText
                                value={String(sections.phone || '')}
                                onChange={(v) => updateField('phone', v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                className=""
                                as="span"
                            />
                            {(String(sections.phone || '').trim() && String(sections.location || '').trim()) ? <span>•</span> : null}
                            <EditableText
                                value={String(sections.location || '')}
                                onChange={(v) => updateField('location', v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                className=""
                                as="span"
                            />
                        </>
                    ) : (
                        <>
                            {sections.email && <span>{sections.email}</span>}
                            {sections.phone && <span>•</span>}
                            {sections.phone && <span>{sections.phone}</span>}
                            {sections.location && <span>•</span>}
                            {sections.location && <span>{sections.location}</span>}
                        </>
                    )}
                </div>
            </div>

            {/* Body */}
            <div className={editMode ? 'p-6 pl-16 space-y-4' : 'p-6 space-y-6'}>
                {editMode ? (
                    <AddSectionButton onClick={addSection} className="mb-3" />
                ) : null}
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
    compact = false,
    titleNode,
}: {
    title: string;
    children: React.ReactNode;
    compact?: boolean;
    titleNode?: React.ReactNode;
}) {
    return (
        <div>
            {titleNode ? (
                titleNode
            ) : (
                <h3 className={compact
                    ? 'text-xs font-bold text-slate-900 tracking-wider uppercase border-b-2 border-slate-300 pb-1 mb-2'
                    : 'text-xs font-bold text-slate-900 tracking-wider uppercase border-b-2 border-slate-300 pb-1.5 mb-3'}>
                    {title}
                </h3>
            )}
            {children}
        </div>
    );
}