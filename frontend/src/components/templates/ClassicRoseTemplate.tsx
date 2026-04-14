import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Phone, MapPin, Mail, Globe } from "lucide-react";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import { EditableText } from "./EditableSection";
import AddSectionButton from "./AddSectionButton";

const ROSE_ACCENT = "#a67c6b";

export default function ClassicRoseTemplate({
    content,
    editMode = false,
    onContentChange,
}: {
    content: string;
    editMode?: boolean;
    onContentChange?: (changes: any) => void;
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
            const cleaned = nextArr.filter((c) => String((c as any)?.name || (c as any)?.title || '').trim());
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

    const website =
        data.website ||
        data.portfolio ||
        (Array.isArray(data.links) && data.links[0]?.url) ||
        (Array.isArray(data.links) && data.links[0]?.href) ||
        "";

    const nameParts = String(data.name || "Your Name").trim().split(/\s+/);
    const firstName = nameParts[0] || "Your";
    const lastName = nameParts.slice(1).join(" ") || "Name";

    return (
        <div className="bg-white rounded-lg shadow-lg ring-1 ring-black/5 overflow-hidden max-w-5xl mx-auto">
            {editMode ? <AddSectionButton onClick={() => { }} className="p-4 pb-0" /> : null}
            <div className="bg-white min-h-[900px]">
                <div className="px-8 pt-8 pb-6">
                    {/* Header: Name (first dark, last rose) + title centered */}
                    <div className="text-center mb-6">
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
                            <span style={{ color: ROSE_ACCENT }}>
                                {editMode ? (
                                    <EditableText value={lastName} onChange={(v) => {
                                        updateField('name', [firstName, v].filter(Boolean).join(" "));
                                    }} editMode={editMode} liveUpdate layoutSafe as="span" />
                                ) : (
                                    lastName
                                )}
                            </span>
                        </h1>
                        <div className="text-sm font-normal text-slate-700 uppercase tracking-wide mt-1">
                            {editMode ? (
                                <EditableText value={String(data.title || "Professional Title")} onChange={(v) => updateField('title', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-sm text-slate-700" />
                            ) : (
                                data.title || "Professional Title"
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-12 gap-6">
                        {/* LEFT COLUMN */}
                        <aside className="col-span-4 border-r pr-6" style={{ borderColor: ROSE_ACCENT + "40" }}>
                            <Section title={getHeading('contact', 'Contact')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('contact', v)} accentColor={ROSE_ACCENT}>
                                <div className="space-y-2 text-sm text-slate-700">
                                    {(data.location || editMode) && (
                                        <ContactRow icon={<MapPin className="w-3.5 h-3.5" />} value={String(data.location || '')} editMode={editMode} onChange={(v) => updateField('location', v)} />
                                    )}
                                    {(data.phone || editMode) && (
                                        <ContactRow icon={<Phone className="w-3.5 h-3.5" />} value={String(data.phone || '')} editMode={editMode} onChange={(v) => updateField('phone', v)} />
                                    )}
                                    {(data.email || editMode) && (
                                        <ContactRow icon={<Mail className="w-3.5 h-3.5" />} value={String(data.email || '')} editMode={editMode} onChange={(v) => updateField('email', v)} />
                                    )}
                                    {(website || editMode) && (
                                        <ContactRow icon={<Globe className="w-3.5 h-3.5" />} value={String(website || '')} editMode={editMode} onChange={(v) => updateField('website', v)} />
                                    )}
                                </div>
                            </Section>

                            <Section title={getHeading('education', 'Education')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('education', v)} accentColor={ROSE_ACCENT}>
                                <div className="space-y-4">
                                    {(education.length > 0 || showEmpty) ? (
                                        education.slice(0, 5).map((edu: any, idx: number) => (
                                            <div key={idx}>
                                                <div className="font-semibold text-sm text-slate-800">
                                                    {editMode ? <EditableText value={String(edu.degree || edu.title || '')} onChange={(v) => updateEducation(idx, 'degree', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : (edu.degree || edu.title || '')}
                                                </div>
                                                <div className="text-xs text-slate-600">{editMode ? <EditableText value={String(edu.school || edu.institution || '')} onChange={(v) => updateEducation(idx, 'school', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : (edu.school || edu.institution || '')}</div>
                                                <div className="text-xs text-slate-500">{editMode ? <EditableText value={String(edu.year || edu.graduationDate || '')} onChange={(v) => updateEducation(idx, 'graduationDate', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : (edu.year || edu.graduationDate || '')}</div>
                                                {String(edu?.gpa ?? '').trim() ? (
                                                    <div className="text-xs text-slate-500">
                                                        GPA: {editMode ? <EditableText value={String(edu?.gpa ?? '')} onChange={(v) => updateEducation(idx, 'gpa', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : String(edu?.gpa ?? '').trim()}
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
                                <Section title={getHeading('certifications', 'Certifications')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('certifications', v)} accentColor={ROSE_ACCENT}>
                                    <div className="space-y-3">
                                        {certifications.map((c: any, idx: number) => {
                                            if (typeof c === 'string') {
                                                return <div key={idx} className="text-sm text-slate-700">• {c}</div>;
                                            }

                                            const name = String(c?.name || c?.title || c?.certification || '').trim();
                                            const issuer = String(c?.issuer || c?.authority || c?.organization || '').trim();
                                            const year = String(c?.year || c?.date || '').trim();

                                            return (
                                                <div key={idx}>
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
                                <Section title={getHeading('languages', 'Languages')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('languages', v)} accentColor={ROSE_ACCENT}>
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

                            <Section title={getHeading('skills', 'Skills')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('skills', v)} accentColor={ROSE_ACCENT}>
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
                        <main className="col-span-8 pl-2">
                            <Section title={getHeading('summary', 'Professional Statement')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('summary', v)} accentColor={ROSE_ACCENT}>
                                {(data.summary || showEmpty) && (
                                    <div className="text-sm leading-relaxed text-slate-700">
                                        {editMode ? (
                                            <EditableText value={String(data.summary || '')} onChange={(v) => updateField('summary', v)} editMode={editMode} liveUpdate layoutSafe as="div" multiline />
                                        ) : (
                                            <p>{String(data.summary || '')}</p>
                                        )}
                                    </div>
                                )}
                            </Section>

                            <Section title={getHeading('experience', 'Work Experience')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('experience', v)} accentColor={ROSE_ACCENT}>
                                <div className="space-y-5">
                                    {(experience.length > 0 || showEmpty) ? (
                                        experience.slice(0, 5).map((exp: any, idx: number) => {
                                            const dates = exp.duration || (exp.startDate && exp.endDate ? `${exp.startDate} / ${exp.currentlyWorking ? 'Present' : exp.endDate}` : '') || [exp.start, exp.end].filter(Boolean).join(" / ");
                                            return (
                                                <div key={idx}>
                                                    <div className="font-semibold text-sm text-slate-800">
                                                        {editMode ? (
                                                            <>
                                                                <EditableText value={String(exp.title || exp.position || '')} onChange={(v) => updateExperience(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="span" />
                                                                {(exp.company || editMode) && (
                                                                    <> | <EditableText value={String(exp.company || '')} onChange={(v) => updateExperience(idx, 'company', v)} editMode={editMode} liveUpdate layoutSafe as="span" /></>
                                                                )}
                                                            </>
                                                        ) : (
                                                            `${exp.title || exp.position || ''}${exp.company ? ' | ' + exp.company : ''}`
                                                        )}
                                                    </div>
                                                    <div className="text-xs text-slate-500 mb-1.5">{editMode ? <EditableText value={String(dates)} onChange={(v) => updateExperience(idx, 'duration', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : dates}</div>
                                                    {exp.description && (
                                                        <div className="text-sm leading-relaxed text-slate-700">
                                                            {editMode ? (
                                                                <EditableText value={String(exp.description)} onChange={(v) => updateExperience(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe as="div" multiline />
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

                            {(projects.length > 0 || showEmpty) && (
                                <Section title={getHeading('projects', 'Projects')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('projects', v)} accentColor={ROSE_ACCENT}>
                                    <div className="space-y-5">
                                        {(projects.length > 0 || showEmpty) ? (
                                            projects.slice(0, 5).map((proj: any, idx: number) => (
                                                <div key={idx}>
                                                    <div className="font-semibold text-sm text-slate-800">
                                                        {editMode ? (
                                                            <EditableText value={String(proj.title || proj.name || '')} onChange={(v) => updateProject(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="span" />
                                                        ) : (
                                                            proj.title || proj.name || 'Project'
                                                        )}
                                                        {proj.link ? (
                                                            <a href={proj.link} target="_blank" rel="noreferrer" className="text-xs text-slate-600 underline ml-2">Link</a>
                                                        ) : null}
                                                    </div>
                                                    {proj.technologies ? (
                                                        <div className="text-xs text-slate-600">{editMode ? <EditableText value={String(proj.technologies)} onChange={(v) => updateProject(idx, 'technologies', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : proj.technologies}</div>
                                                    ) : null}
                                                    {proj.description && (
                                                        <div className="text-sm leading-relaxed text-slate-700 mt-1">
                                                            {editMode ? (
                                                                <EditableText value={String(proj.description)} onChange={(v) => updateProject(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe as="div" multiline />
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
                            )}

                            {customSections.length > 0 && customSections.map((sec: any, idx: number) => (
                                <Section key={idx} title={String(sec?.heading || sec?.title || sec?.label || 'Additional')} editMode={editMode} onTitleChange={(v) => updateCustomHeading(idx, v)} accentColor={ROSE_ACCENT}>
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
                            ))}
                        </main>
                    </div>
                </div>
            </div>
        </div>
    );
}

function Section({ title, children, editMode, onTitleChange, accentColor }: { title: string; children: React.ReactNode; editMode?: boolean; onTitleChange?: (v: string) => void; accentColor: string }) {
    return (
        <section className="mb-6 last:mb-0">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-center mb-2" style={{ color: accentColor }}>
                {editMode ? (
                    <EditableText value={title} onChange={(v) => onTitleChange?.(v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-center" />
                ) : (
                    `- ${title} -`
                )}
            </h3>
            <div className="h-px mb-3" style={{ backgroundColor: accentColor + "60" }} />
            {children}
        </section>
    );
}

function ContactRow({ icon, value, editMode, onChange }: { icon?: React.ReactNode; value: string; editMode?: boolean; onChange?: (v: string) => void }) {
    return (
        <div className="flex items-start gap-2">
            {icon ? <span className="text-slate-500 flex-shrink-0 mt-0.5">{icon}</span> : null}
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
