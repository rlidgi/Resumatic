import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Phone, MapPin, Mail, Globe } from "lucide-react";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import { EditableText } from "./EditableSection";
import AddSectionButton from "./AddSectionButton";

export default function Creative2Template({
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
    const customSections = Array.isArray(data.custom_sections) ? data.custom_sections : [];

    const website =
        data.website ||
        data.portfolio ||
        (Array.isArray(data.links) && data.links[0]?.url) ||
        (Array.isArray(data.links) && data.links[0]?.href) ||
        "";

    return (
        <>
            <style>{`
            @media print {
                [data-template="creative2"] .creative2-template { font-size: 0.82em !important; }
                [data-template="creative2"] .creative2-body {
                    /* Preserve the template's left accent gutter (pl-12) and right padding (pr-8)
                       while slightly compacting vertical padding for multi-page PDF/print. */
                    padding-top: 0.25rem !important;
                    padding-bottom: 0.25rem !important;
                    padding-left: 3rem !important;
                    padding-right: 2rem !important;
                }
                [data-template="creative2"] .creative2-header { margin-bottom: 0.25rem !important; break-after: auto !important; page-break-after: auto !important; }
                /* Printing fragmentation: many browsers don't fragment CSS grid well; force normal flow for multi-page PDFs */
                [data-template="creative2"] .creative2-grid { display: block !important; page-break-inside: auto !important; break-inside: auto !important; }
                [data-template="creative2"] .creative2-grid::after { content: "" !important; display: block !important; clear: both !important; }
                [data-template="creative2"] .creative2-grid > aside { float: left !important; width: 32% !important; }
                [data-template="creative2"] .creative2-grid > main { display: block !important; margin-left: 36% !important; }
                [data-template="creative2"] .creative2-grid > * + * { margin-top: 0 !important; }
                [data-template="creative2"] .creative2-summary { margin-top: 0.5rem !important; margin-bottom: 0 !important; line-height: 1.25 !important; max-width: none !important; }
                [data-template="creative2"] section { margin-bottom: 0.3rem !important; }
                [data-template="creative2"] section h3 { margin-bottom: 0.1rem !important; }
                /* Allow long items to paginate; avoid flex rows in print which can create large bottom whitespace */
                [data-template="creative2"] .creative2-item { display: flow-root !important; page-break-inside: auto !important; break-inside: auto !important; }
                [data-template="creative2"] .creative2-item > span { float: left !important; margin-right: 0.75rem !important; }
            }
        `}</style>
            <div className="bg-white rounded-lg shadow-lg ring-1 ring-black/5 max-w-5xl mx-auto creative2-template" data-template="creative2">
                {editMode ? <AddSectionButton onClick={() => { }} className="p-4 pb-0" /> : null}
                <div className="relative">
                    {/* Yellow accent bar on left - hidden in print to avoid layout issues */}
                    <div className="absolute left-0 top-0 bottom-0 w-2 bg-[#facc15] creative2-decorative" aria-hidden="true" />

                    {/* Decorative shapes - top right - hidden in print to avoid layout issues */}
                    <div className="absolute top-0 right-0 flex gap-0.5 pointer-events-none creative2-decorative" aria-hidden="true">
                        <div className="w-12 h-12 bg-[#00a99d]" />
                        <div className="w-10 h-12 bg-[#f25a4b]" />
                        <div className="w-14 h-12 bg-black" />
                        <div className="w-8 h-12 bg-[#facc15]" />
                    </div>

                    {/* Yellow star - top left - hidden in print to avoid layout issues */}
                    <div className="absolute top-2 left-3 w-8 h-8 bg-[#facc15] opacity-90 pointer-events-none creative2-decorative" style={{ clipPath: "polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%)" }} aria-hidden="true" />

                    <div className="pl-12 pr-8 pt-4 pb-4 creative2-body">
                        {/* Header: Hello! I'm + name + title */}
                        <div className="mb-3 creative2-header">
                            <div className="text-xs text-black/70 mb-0.5">Hello! I&apos;m</div>
                            <div className="text-3xl font-bold text-black tracking-tight">
                                {editMode ? (
                                    <EditableText value={String(data.name || "Your Name")} onChange={(v) => updateField('name', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-3xl font-bold" />
                                ) : (
                                    data.name || "Your Name"
                                )}
                            </div>
                            <div className="text-base italic text-black/80 mt-0.5">
                                {editMode ? (
                                    <EditableText value={String(data.title || "Professional Title")} onChange={(v) => updateField('title', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-lg italic" />
                                ) : (
                                    data.title || "Professional Title"
                                )}
                            </div>
                        </div>

                        {/* Summary: before grid */}
                        {(data.summary || showEmpty) && (
                            <div className="mt-1.5 mb-3 text-xs leading-relaxed text-black/80 max-w-2xl creative2-summary">
                                {editMode ? (
                                    <EditableText value={String(data.summary || '')} onChange={(v) => updateField('summary', v)} editMode={editMode} liveUpdate layoutSafe as="div" multiline />
                                ) : (
                                    <p>{String(data.summary || '')}</p>
                                )}
                            </div>
                        )}

                        <div className="grid grid-cols-12 gap-4 creative2-grid">
                            {/* LEFT COLUMN: Contact, Skills */}
                            <aside className="col-span-4">
                                <Section title={getHeading('contact', 'Contact')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('contact', v)}>
                                    <div className="space-y-2 text-sm">
                                        {(data.phone || editMode) && (
                                            <ContactRow icon={<Phone className="w-4 h-4" />} value={String(data.phone || '')} editMode={editMode} onChange={(v) => updateField('phone', v)} />
                                        )}
                                        {(data.location || editMode) && (
                                            <ContactRow icon={<MapPin className="w-4 h-4" />} value={String(data.location || '')} editMode={editMode} onChange={(v) => updateField('location', v)} />
                                        )}
                                        {(data.email || editMode) && (
                                            <ContactRow icon={<Mail className="w-4 h-4" />} value={String(data.email || '')} editMode={editMode} onChange={(v) => updateField('email', v)} />
                                        )}
                                        {(website || editMode) && (
                                            <ContactRow icon={<Globe className="w-4 h-4" />} value={String(website || '')} editMode={editMode} onChange={(v) => updateField('website', v)} />
                                        )}
                                    </div>
                                </Section>

                                <Section title={getHeading('skills', 'Skills')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('skills', v)}>
                                    <div className="space-y-2">
                                        {(skills.length > 0 || showEmpty) ? (
                                            skills.slice(0, 8).map((s, idx) => (
                                                <div key={idx} className="flex items-start gap-2">
                                                    <span className="w-2 h-2 rounded-full border border-[#f25a4b] mt-1.5 flex-shrink-0" />
                                                    {editMode ? (
                                                        <EditableText value={s} onChange={(v) => updateSkill(idx, v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-sm flex-1" />
                                                    ) : (
                                                        <span className="text-sm">{s}</span>
                                                    )}
                                                </div>
                                            ))
                                        ) : (
                                            <div className="text-xs text-black/60">Add skills</div>
                                        )}
                                    </div>
                                </Section>
                            </aside>

                            {/* RIGHT COLUMN: Education, Experience */}
                            <main className="col-span-8">
                                <Section title={getHeading('education', 'Education')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('education', v)}>
                                    <div className="space-y-4">
                                        {(education.length > 0 || showEmpty) ? (
                                            education.slice(0, 5).map((edu: any, idx: number) => (
                                                <div key={idx} className="flex gap-3 creative2-item">
                                                    <span className="w-2 h-2 rounded-full border border-[#f25a4b] mt-1.5 flex-shrink-0" />
                                                    <div>
                                                        <div className="font-semibold text-sm">{editMode ? <EditableText value={String(edu.degree || edu.title || 'Degree')} onChange={(v) => updateEducation(idx, 'degree', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : (edu.degree || edu.title || 'Degree')}</div>
                                                        <div className="text-xs text-black/70">{editMode ? <EditableText value={String(edu.school || edu.institution || '')} onChange={(v) => updateEducation(idx, 'school', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : (edu.school || edu.institution || '')}</div>
                                                        <div className="text-xs text-black/60">{editMode ? <EditableText value={String(edu.year || edu.graduationDate || '')} onChange={(v) => updateEducation(idx, 'graduationDate', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : (edu.year || edu.graduationDate || '')}</div>
                                                        {String(edu?.gpa ?? '').trim() ? (
                                                            <div className="text-xs text-black/60">
                                                                GPA: {editMode ? <EditableText value={String(edu?.gpa ?? '')} onChange={(v) => updateEducation(idx, 'gpa', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : String(edu?.gpa ?? '').trim()}
                                                            </div>
                                                        ) : null}
                                                    </div>
                                                </div>
                                            ))
                                        ) : (
                                            <div className="text-sm text-black/60">Add education</div>
                                        )}
                                    </div>
                                </Section>

                                <Section title={getHeading('experience', 'Experience')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('experience', v)}>
                                    <div className="space-y-5">
                                        {(experience.length > 0 || showEmpty) ? (
                                            experience.slice(0, 5).map((exp: any, idx: number) => {
                                                const dates = exp.duration || (exp.startDate && exp.endDate ? `${exp.startDate} / ${exp.currentlyWorking ? 'Present' : exp.endDate}` : '') || [exp.start, exp.end].filter(Boolean).join(" / ");
                                                return (
                                                    <div key={idx} className="flex gap-3 creative2-item">
                                                        <span className="w-2 h-2 rounded-full border border-[#f25a4b] mt-1.5 flex-shrink-0" />
                                                        <div className="flex-1">
                                                            <div className="text-xs text-black/60 mb-0.5">
                                                                {editMode ? <EditableText value={String(dates)} onChange={(v) => updateExperience(idx, 'duration', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : dates}
                                                            </div>
                                                            <div className="font-semibold text-sm">
                                                                {editMode ? (
                                                                    <EditableText value={String(exp.title || exp.position || 'Role')} onChange={(v) => updateExperience(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="span" />
                                                                ) : (
                                                                    exp.title || exp.position || 'Role'
                                                                )}
                                                                {(exp.company || editMode) && (
                                                                    <> — {editMode ? <EditableText value={String(exp.company || '')} onChange={(v) => updateExperience(idx, 'company', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : exp.company}</>
                                                                )}
                                                            </div>
                                                            {exp.description && (
                                                                <div className="mt-1.5 text-sm leading-relaxed text-black/80">
                                                                    {editMode ? (
                                                                        <EditableText value={String(exp.description)} onChange={(v) => updateExperience(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe as="div" multiline />
                                                                    ) : (
                                                                        <RenderMaybeBullets text={exp.description} forceBullets className="text-sm leading-relaxed" />
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })
                                        ) : (
                                            <div className="text-sm text-black/60">Add experience</div>
                                        )}
                                    </div>
                                </Section>

                                {(projects.length > 0 || showEmpty) && (
                                    <Section title={getHeading('projects', 'Projects')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('projects', v)}>
                                        <div className="space-y-5">
                                            {(projects.length > 0 || showEmpty) ? (
                                                projects.slice(0, 5).map((proj: any, idx: number) => (
                                                    <div key={idx} className="flex gap-3 creative2-item">
                                                        <span className="w-2 h-2 rounded-full border border-[#f25a4b] mt-1.5 flex-shrink-0" />
                                                        <div className="flex-1">
                                                            <div className="font-semibold text-sm">
                                                                {editMode ? (
                                                                    <EditableText value={String(proj.title || proj.name || 'Project')} onChange={(v) => updateProject(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="span" />
                                                                ) : (
                                                                    proj.title || proj.name || 'Project'
                                                                )}
                                                                {proj.link ? (
                                                                    <a href={proj.link} target="_blank" rel="noreferrer" className="text-xs text-black/60 underline ml-2">Link</a>
                                                                ) : null}
                                                            </div>
                                                            {proj.technologies ? (
                                                                <div className="text-xs text-black/60 mt-0.5">{editMode ? <EditableText value={String(proj.technologies)} onChange={(v) => updateProject(idx, 'technologies', v)} editMode={editMode} liveUpdate layoutSafe as="span" /> : proj.technologies}</div>
                                                            ) : null}
                                                            {proj.description && (
                                                                <div className="mt-1.5 text-sm leading-relaxed text-black/80">
                                                                    {editMode ? (
                                                                        <EditableText value={String(proj.description)} onChange={(v) => updateProject(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe as="div" multiline />
                                                                    ) : (
                                                                        <RenderMaybeBullets text={proj.description} forceBullets className="text-sm leading-relaxed" />
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))
                                            ) : (
                                                <div className="text-sm text-black/60">Add projects</div>
                                            )}
                                        </div>
                                    </Section>
                                )}

                                {(certifications.length > 0 || showEmpty) && (
                                    <Section title={getHeading('certifications', 'Certifications')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('certifications', v)}>
                                        <div className="space-y-3">
                                            {certifications.map((c: any, idx: number) => {
                                                if (typeof c === 'string') {
                                                    return (
                                                        <div key={idx} className="flex gap-3 creative2-item">
                                                            <span className="w-2 h-2 rounded-full border border-[#f25a4b] mt-1.5 flex-shrink-0" />
                                                            <div className="text-sm leading-relaxed text-black/80">• {c}</div>
                                                        </div>
                                                    );
                                                }

                                                const name = String(c?.name || c?.title || c?.certification || '').trim();
                                                const issuer = String(c?.issuer || c?.authority || c?.organization || '').trim();
                                                const year = String(c?.year || c?.date || '').trim();

                                                return (
                                                    <div key={idx} className="flex gap-3 creative2-item">
                                                        <span className="w-2 h-2 rounded-full border border-[#f25a4b] mt-1.5 flex-shrink-0" />
                                                        <div className="flex-1">
                                                            <div className="font-semibold text-sm">{name || 'Certification'}</div>
                                                            {(issuer || year) ? (
                                                                <div className="text-xs text-black/60">
                                                                    {[issuer, year].filter(Boolean).join(' • ')}
                                                                </div>
                                                            ) : null}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                            {certifications.length === 0 ? (
                                                <div className="text-sm text-black/60">Add certifications</div>
                                            ) : null}
                                        </div>
                                    </Section>
                                )}

                                {customSections.length > 0 && customSections.map((sec: any, idx: number) => (
                                    <Section key={idx} title={String(sec?.heading || sec?.title || sec?.label || 'Additional')} editMode={editMode} onTitleChange={(v) => updateCustomHeading(idx, v)}>
                                        <CustomSectionsRenderer
                                            customSections={[sec]}
                                            editMode={editMode}
                                            onHeadingChange={(sIdx, v) => updateCustomHeading(idx + sIdx, v)}
                                            onItemChange={(sIdx, iIdx, field, v) => updateCustomItem(idx + sIdx, iIdx, field, v)}
                                            onBodyChange={(sIdx, v) => updateCustomBody(idx + sIdx, v)}
                                            showSectionHeadings={false}
                                            headingClassName="font-bold text-black text-sm"
                                            itemTitleClassName="font-semibold text-sm"
                                            itemMetaClassName="text-xs text-black/60"
                                            itemBodyClassName="text-sm leading-relaxed text-black/80"
                                        />
                                    </Section>
                                ))}
                            </main>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}

function Section({ title, children, editMode, onTitleChange }: { title: string; children: React.ReactNode; editMode?: boolean; onTitleChange?: (v: string) => void }) {
    return (
        <section className="mb-3 last:mb-0">
            <h3 className="font-bold text-black text-sm uppercase tracking-wide mb-2">
                {editMode ? <EditableText value={title} onChange={(v) => onTitleChange?.(v)} editMode={editMode} liveUpdate layoutSafe as="div" className="font-bold text-sm" /> : title}
            </h3>
            <div className="h-px bg-black/20 mb-3" />
            {children}
        </section>
    );
}

function ContactRow({ icon, value, editMode, onChange }: { icon?: React.ReactNode; value: string; editMode?: boolean; onChange?: (v: string) => void }) {
    return (
        <div className="flex items-start gap-2">
            {icon ? <span className="text-black/60 flex-shrink-0">{icon}</span> : null}
            <div className="text-black break-words flex-1">
                {editMode ? (
                    <EditableText value={String(value || '')} onChange={(v) => onChange?.(v)} editMode={!!editMode} liveUpdate layoutSafe as="div" />
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
