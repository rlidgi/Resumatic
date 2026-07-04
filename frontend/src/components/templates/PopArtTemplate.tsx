import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Phone, MapPin, Mail, Globe } from "lucide-react";
import { parseResumeContent } from "../../utils/resumeUtils";
import { RenderMaybeBullets } from "./RenderMaybeBullets";
import CustomSectionsRenderer from "./CustomSectionsRenderer";
import { EditableText } from "./EditableSection";
import AddSectionButton from "./AddSectionButton";

export default function PopArtTemplate({
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

    const fullName = String(data.name || "").trim() || "Your Name";
    const firstName = fullName.split(/\s+/)[0] || "Your";
    const lastName = fullName.split(/\s+/).slice(1).join(" ") || "Name";

    const languages = normalizeList(data.languages);
    const skills = normalizeList(data.skills);
    const projects = Array.isArray(data.projects) ? data.projects : [];
    const customSections = Array.isArray(data.custom_sections) ? data.custom_sections : [];

    const website =
        data.website ||
        data.portfolio ||
        (Array.isArray(data.links) && data.links[0]?.url) ||
        (Array.isArray(data.links) && data.links[0]?.href) ||
        "";

    const initials = getInitials(fullName);
    const heroLetters = getHeroLetters(fullName);

    return (
        <div className="bg-[#f6efe4] rounded-lg shadow-lg ring-1 ring-black/5 overflow-hidden max-w-5xl mx-auto">
            {editMode ? (<AddSectionButton onClick={addSection} className="p-4 pb-0" />) : null}
            <div className="border-[10px] border-[#00a99d]">
                <div className="grid grid-cols-12 min-h-[980px]">
                    {/* LEFT COLUMN */}
                    <aside className="col-span-4 border-r border-black/20">
                        {/* Pop-art header grid */}
                        <div className="grid grid-cols-3">
                            <HeroCell bg="#f25a4b" text={heroLetters[0]} />
                            <HeroCell bg="#ffcc4d" text={heroLetters[1]} />
                            <HeroCell bg="#00a99d" text={heroLetters[2]} textColor="#0b0b0b" />
                        </div>

                        {/* Intro panel */}
                        <div className="bg-[#00a99d] text-black px-6 py-7 border-t border-black/20">
                            <div className="mt-2 leading-[0.95]">
                                <div className="text-[44px] font-black tracking-tight">
                                    {editMode ? (
                                        <EditableText value={firstName} onChange={(v) => updateField('name', `${v} ${lastName}`.trim())} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                    ) : (
                                        firstName
                                    )}
                                </div>
                                <div className="text-[44px] font-black tracking-tight">
                                    {editMode ? (
                                        <EditableText value={lastName} onChange={(v) => updateField('name', `${firstName} ${v}`.trim())} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                    ) : (
                                        lastName
                                    )}
                                </div>
                            </div>
                            {(editMode || data.summary) && (
                                editMode ? (
                                    <EditableText value={String(data.summary || '')} onChange={(v) => updateField('summary', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="mt-4 text-[11px] leading-relaxed max-w-[18rem]" multiline />
                                ) : (
                                    <p className="mt-4 text-[11px] leading-relaxed max-w-[18rem]">
                                        {String(data.summary)}
                                    </p>
                                )
                            )}
                        </div>

                        {/* Left content */}
                        <div className="px-6 py-6 bg-[#f6efe4]">
                            <LeftSection title={getHeading('languages', 'Language')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('languages', v)}>
                                {languages.length > 0 ? (
                                    <div className="space-y-2">
                                        {languages.slice(0, 5).map((lang, idx) => (
                                            <LanguageBar key={idx} label={lang} editMode={editMode} onChange={(v) => updateLanguage(idx, v)} />
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-xs text-black/60">Add languages to show bars.</div>
                                )}
                            </LeftSection>

                            <LeftSection
                                title={getHeading('skills', 'Skills')}
                                editMode={editMode}
                                onTitleChange={(v) => updateSectionHeading('skills', v)}
                                rightAddon={
                                    <div className="flex items-center gap-1">
                                        <StarDot filled />
                                        <StarDot filled />
                                        <StarDot filled />
                                    </div>
                                }
                            >
                                {skills.length > 0 ? (
                                    <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-[11px]">
                                        {skills.slice(0, 10).map((s, idx) => (
                                            <div key={idx} className="border-b border-black/20 pb-1">
                                                {editMode ? (
                                                    <EditableText value={s} onChange={(v) => updateSkill(idx, v)} editMode={editMode} liveUpdate layoutSafe as="span" className="inline" />
                                                ) : (
                                                    s
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-xs text-black/60">Add skills to populate this section.</div>
                                )}
                            </LeftSection>

                            {/* Small monogram (matches vibe of the reference) */}
                            <div className="mt-8 flex items-center gap-3">
                                <div className="w-12 h-12 bg-white border border-black/30 grid place-items-center">
                                    <div className="font-serif text-lg font-bold">{initials}</div>
                                </div>
                            </div>
                        </div>
                    </aside>

                    {/* RIGHT COLUMN */}
                    <section className="col-span-8 bg-[#f6efe4] px-8 py-8">
                        <RightSection title={getHeading('experience', 'Work experience')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('experience', v)}>
                            <div className="space-y-5">
                                {(Array.isArray(data.experience) ? data.experience : []).slice(0, 5).map((exp: any, idx: number) => (
                                    <RightItem
                                        key={idx}
                                        title={String(exp.title || exp.position || "Role")}
                                        dates={String(exp.duration || exp.dates || [exp.start, exp.end].filter(Boolean).join(" / ") || '')}
                                        subtitle={String(exp.company || exp.organization || '')}
                                        body={exp.description}
                                        editMode={editMode}
                                        onTitleChange={(v) => updateExperience(idx, 'title', v)}
                                        onSubtitleChange={(v) => updateExperience(idx, 'company', v)}
                                        onDatesChange={(v) => updateExperience(idx, 'duration', v)}
                                        onBodyChange={(v) => updateExperience(idx, 'description', v)}
                                    />
                                ))}
                                {(!data.experience || data.experience.length === 0) && (
                                    <div className="text-sm text-black/60">Add experience to populate this section.</div>
                                )}
                            </div>
                        </RightSection>

                        {projects.length > 0 && (
                            <RightSection title={getHeading('projects', 'Projects')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('projects', v)}>
                                <div className="space-y-5">
                                    {projects.slice(0, 5).map((proj: any, idx: number) => (
                                        <div key={idx} className="grid grid-cols-12 gap-4">
                                            <div className="col-span-1 pt-1">
                                                <div className="w-2.5 h-2.5 bg-[#f25a4b] border border-black/50" />
                                            </div>
                                            <div className="col-span-11">
                                                <div className="flex items-start justify-between gap-4">
                                                    <div className="font-semibold text-[13px]">
                                                        {editMode ? (
                                                            <EditableText value={String(proj.title || proj.name || 'Project')} onChange={(v) => updateProject(idx, 'title', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="font-semibold text-[13px]" />
                                                        ) : (
                                                            String(proj.title || proj.name || "Project")
                                                        )}
                                                    </div>
                                                    {proj.link ? (
                                                        <a
                                                            href={String(proj.link)}
                                                            target="_blank"
                                                            rel="noreferrer"
                                                            className="text-[11px] text-black/70 whitespace-nowrap underline underline-offset-2 hover:text-black"
                                                        >
                                                            Link
                                                        </a>
                                                    ) : null}
                                                </div>

                                                {proj.technologies ? (
                                                    editMode ? (
                                                        <EditableText value={String(proj.technologies)} onChange={(v) => updateProject(idx, 'technologies', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="mt-1 text-[11px] text-black/70" />
                                                    ) : (
                                                        <div className="mt-1 text-[11px] text-black/70">{String(proj.technologies)}</div>
                                                    )
                                                ) : null}

                                                {(editMode || proj.description) ? (
                                                    <div className="mt-1.5">
                                                        {editMode ? (
                                                            <EditableText value={String(proj.description)} onChange={(v) => updateProject(idx, 'description', v)} editMode={editMode} liveUpdate layoutSafe as="div" className="text-[11px] leading-relaxed text-black/80" multiline />
                                                        ) : (
                                                            <RenderMaybeBullets
                                                                text={String(proj.description)}
                                                                forceBullets
                                                                className="text-[11px] leading-relaxed text-black/80"
                                                            />
                                                        )}
                                                    </div>
                                                ) : null}

                                                <div className="h-px bg-black/20 mt-4" />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </RightSection>
                        )}

                        <RightSection title={getHeading('education', 'Education')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('education', v)}>
                            <div className="space-y-5">
                                {(Array.isArray(data.education) ? data.education : []).slice(0, 5).map((edu: any, idx: number) => (
                                    <RightItem
                                        key={idx}
                                        title={String(edu.degree || edu.title || 'Degree')}
                                        dates={String(edu.year || edu.dates || edu.graduationDate || '')}
                                        subtitle={String(edu.institution || edu.school || '')}
                                        body={edu.description}
                                        editMode={editMode}
                                        onTitleChange={(v) => updateEducation(idx, 'degree', v)}
                                        onSubtitleChange={(v) => updateEducation(idx, 'institution', v)}
                                        onDatesChange={(v) => updateEducation(idx, 'year', v)}
                                        onBodyChange={(v) => updateEducation(idx, 'description', v)}
                                    />
                                ))}
                                {(!data.education || data.education.length === 0) && (
                                    <div className="text-sm text-black/60">Add education to populate this section.</div>
                                )}
                            </div>
                        </RightSection>

                        <RightSection title={getHeading('contact', 'Contact')} editMode={editMode} onTitleChange={(v) => updateSectionHeading('contact', v)}>
                            <div className="text-[12px] space-y-2">
                                {(editMode || data.phone) && <ContactRow icon={<Phone className="w-4 h-4" />} label="Phone" value={String(data.phone || '')} editMode={editMode} onChange={(v) => updateField('phone', v)} />}
                                {(editMode || data.email) && <ContactRow icon={<Mail className="w-4 h-4" />} label="Email" value={String(data.email || '')} editMode={editMode} onChange={(v) => updateField('email', v)} />}
                                {(editMode || data.location) && <ContactRow icon={<MapPin className="w-4 h-4" />} label="Address" value={String(data.location || '')} editMode={editMode} onChange={(v) => updateField('location', v)} />}
                                {(editMode || website) && <ContactRow icon={<Globe className="w-4 h-4" />} label="Website" value={String(website || '')} editMode={editMode} onChange={(v) => updateField('website', v)} />}
                                {(!editMode && !data.phone && !data.email && !data.location && !website) && (
                                    <div className="text-sm text-black/60">Add contact fields to show them here.</div>
                                )}
                            </div>
                        </RightSection>

                        {customSections.length > 0 && (
                            <>
                                {customSections.map((sec: any, idx: number) => {
                                    const heading = String(sec?.heading || sec?.title || sec?.label || 'Additional').trim();
                                    return (
                                        <RightSection key={idx} title={heading} editMode={editMode} onTitleChange={(v) => updateCustomHeading(idx, v)}>
                                            <CustomSectionsRenderer
                                                customSections={[sec]}
                                                editMode={editMode}
                                                onHeadingChange={(sIdx, v) => updateCustomHeading(idx + sIdx, v)}
                                                onItemChange={(sIdx, iIdx, field, v) => updateCustomItem(idx + sIdx, iIdx, field, v)}
                                                onBodyChange={(sIdx, v) => updateCustomBody(idx + sIdx, v)}
                                                showSectionHeadings={false}
                                                headingClassName="text-[13px] font-semibold text-black"
                                                itemTitleClassName="text-[12px] font-semibold text-black"
                                                itemMetaClassName="text-[11px] text-black/70"
                                                itemBodyClassName="text-[11px] leading-relaxed text-black/80"
                                            />
                                        </RightSection>
                                    );
                                })}
                            </>
                        )}
                    </section>
                </div>
            </div>
        </div>
    );
}

function HeroCell({ bg, text, textColor }: { bg: string; text: string; textColor?: string }) {
    return (
        <div
            className="h-[160px] border-b border-black/20 border-r border-black/20 last:border-r-0 flex items-center justify-center"
            style={{ background: bg }}
        >
            <div
                className="font-serif font-black leading-none"
                style={{ fontSize: 86, color: textColor || "#0b0b0b" }}
            >
                {text}
            </div>
        </div>
    );
}

function LeftSection({
    title,
    rightAddon,
    children,
    editMode,
    onTitleChange,
}: {
    title: string;
    rightAddon?: React.ReactNode;
    children: React.ReactNode;
    editMode?: boolean;
    onTitleChange?: (value: string) => void;
}) {
    return (
        <section className="mb-7 last:mb-0">
            <div className="flex items-end justify-between gap-3">
                <h3 className="font-serif font-bold text-lg">
                    {editMode ? (
                        <EditableText
                            value={String(title || '')}
                            onChange={(v) => onTitleChange?.(v)}
                            editMode={!!editMode}
                            liveUpdate
                            layoutSafe
                            as="div"
                            className="font-serif font-bold text-lg"
                        />
                    ) : (
                        title
                    )}
                </h3>
                {rightAddon}
            </div>
            <div className="h-px bg-black/40 mt-2 mb-3" />
            {children}
        </section>
    );
}

function RightSection({ title, children, editMode, onTitleChange }: { title: string; children: React.ReactNode; editMode?: boolean; onTitleChange?: (value: string) => void }) {
    return (
        <section className="mb-8 last:mb-0">
            <h2 className="font-serif font-bold text-2xl">
                {editMode ? (
                    <EditableText
                        value={String(title || '')}
                        onChange={(v) => onTitleChange?.(v)}
                        editMode={!!editMode}
                        liveUpdate
                        layoutSafe
                        as="div"
                        className="font-serif font-bold text-2xl"
                    />
                ) : (
                    title
                )}
            </h2>
            <div className="h-px bg-black/50 mt-2 mb-5" />
            {children}
        </section>
    );
}

function RightItem({
    title,
    dates,
    subtitle,
    body,
    editMode,
    onTitleChange,
    onSubtitleChange,
    onDatesChange,
    onBodyChange,
}: {
    title: string;
    dates?: string;
    subtitle?: string;
    body?: any;
    editMode?: boolean;
    onTitleChange?: (value: string) => void;
    onSubtitleChange?: (value: string) => void;
    onDatesChange?: (value: string) => void;
    onBodyChange?: (value: string) => void;
}) {
    return (
        <div className="grid grid-cols-12 gap-4">
            <div className="col-span-1 pt-1">
                <div className="w-2.5 h-2.5 bg-[#f25a4b] border border-black/50" />
            </div>
            <div className="col-span-11">
                <div className="flex items-start justify-between gap-4">
                    <div className="font-semibold text-[13px]">
                        {editMode ? (
                            <>
                                <EditableText value={String(title || '')} onChange={(v) => onTitleChange && onTitleChange(v)} editMode={!!editMode} liveUpdate layoutSafe as="span" className="inline" />
                                {subtitle ? <span className="font-normal text-black/70"> — </span> : null}
                                <EditableText value={String(subtitle || '')} onChange={(v) => onSubtitleChange && onSubtitleChange(v)} editMode={!!editMode} liveUpdate layoutSafe as="span" className="inline font-normal text-black/70" />
                            </>
                        ) : (
                            <>
                                {title}
                                {subtitle ? <span className="font-normal text-black/70"> — {subtitle}</span> : null}
                            </>
                        )}
                    </div>
                    {dates ? (
                        editMode ? (
                            <EditableText value={String(dates)} onChange={(v) => onDatesChange && onDatesChange(v)} editMode={!!editMode} liveUpdate layoutSafe as="div" className="text-[11px] text-black/70 whitespace-nowrap" />
                        ) : (
                            <div className="text-[11px] text-black/70 whitespace-nowrap">{dates}</div>
                        )
                    ) : null}
                </div>
                {body ? (
                    <div className="mt-1.5">
                        {editMode ? (
                            <EditableText value={String(body)} onChange={(v) => onBodyChange && onBodyChange(v)} editMode={!!editMode} liveUpdate layoutSafe as="div" className="text-[11px] leading-relaxed text-black/80" multiline />
                        ) : (
                            <RenderMaybeBullets
                                text={body}
                                forceBullets
                                className="text-[11px] leading-relaxed text-black/80"
                            />
                        )}
                    </div>
                ) : null}
                <div className="h-px bg-black/20 mt-4" />
            </div>
        </div>
    );
}

function ContactRow({
    icon,
    label,
    value,
    editMode,
    onChange,
}: {
    icon?: React.ReactNode;
    label: string;
    value: string;
    editMode?: boolean;
    onChange?: (value: string) => void;
}) {
    return (
        <div className="grid grid-cols-[100px_1fr] gap-2 items-start leading-snug">
            <div className="flex items-center gap-2 text-black/80 font-semibold whitespace-nowrap">
                {icon ? <span className="text-black/60">{icon}</span> : null}
                <span>{label}</span>
            </div>
            <div className="text-black break-words">
                {editMode ? (
                    <EditableText value={String(value || '')} onChange={(v) => onChange && onChange(v)} editMode={!!editMode} liveUpdate layoutSafe as="div" className="text-black" />
                ) : (
                    value
                )}
            </div>
        </div>
    );
}

function LanguageBar({ label, editMode, onChange }: { label: string; editMode?: boolean; onChange?: (value: string) => void }) {
    const pct = Math.max(25, Math.min(100, 45 + (hash(label) % 56)));
    return (
        <div className="grid grid-cols-12 gap-3 items-center text-[11px]">
            <div className="col-span-4">
                {editMode ? (
                    <EditableText value={String(label || '')} onChange={(v) => onChange && onChange(v)} editMode={!!editMode} liveUpdate layoutSafe as="span" className="inline" />
                ) : (
                    label
                )}
            </div>
            <div className="col-span-8">
                <div className="h-1 bg-black/15">
                    <div className="h-1 bg-[#c94b3a]" style={{ width: `${pct}%` }} />
                </div>
            </div>
        </div>
    );
}

function StarDot({ filled }: { filled?: boolean }) {
    return <span className={`w-2.5 h-2.5 inline-block ${filled ? "bg-[#ffcc4d]" : "bg-black/20"}`} style={{ clipPath: "polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%)" }} />;
}

function normalizeList(value: any): string[] {
    if (Array.isArray(value)) {
        return value
            .map((item) => (typeof item === "string" ? item : item?.name || item?.label || item?.title || ""))
            .map((s) => String(s).trim())
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

function getInitials(name: string): string {
    const parts = String(name || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean);
    if (parts.length === 0) return "YN";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return `${parts[0][0]}/${parts[1][0]}`.toUpperCase();
}

function getHeroLetters(name: string): [string, string, string] {
    const clean = String(name || "").replace(/[^a-z]/gi, "").toUpperCase();
    const a = clean[0] || "R";
    const b = clean[1] || "E";
    const c = clean[2] || "S";
    return [a, b, c];
}

function hash(input: string): number {
    const s = String(input || "");
    let acc = 0;
    for (let i = 0; i < s.length; i++) acc = (acc * 31 + s.charCodeAt(i)) >>> 0;
    return acc;
}


