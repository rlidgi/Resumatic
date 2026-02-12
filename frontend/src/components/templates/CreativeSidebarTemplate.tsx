import React from 'react';
import { Briefcase, GraduationCap, Sparkles, Code, Award, Layers } from 'lucide-react';
import { RenderMaybeBullets } from './RenderMaybeBullets';
import { EditableText } from './EditableSection';
import { useEditableResume } from './useEditableResume';

interface CreativeSidebarTemplateProps {
    content: string;
    editMode?: boolean;
    onContentChange?: (changes: any) => void;
}

export default function CreativeSidebarTemplate({ content, editMode = false, onContentChange }: CreativeSidebarTemplateProps) {
    const { sections, updateField, updateArrayItem, updateListFromText } = useEditableResume(content, onContentChange);

    return (
        <div className="bg-gradient-to-br from-purple-50 via-pink-50 to-white rounded-lg shadow-xl overflow-hidden max-w-4xl mx-auto">
            {/* Sidebar */}
            <div className="flex flex-col md:flex-row">
                <div className="bg-gradient-to-br from-purple-600 to-pink-600 text-white p-6 md:w-[280px] md:flex-shrink-0">
                    <div className="mb-6">
                        <div className="w-20 h-20 bg-white/20 backdrop-blur-sm rounded-2xl flex items-center justify-center mb-3 mx-auto">
                            <span className="text-3xl font-bold">{sections.name?.[0] || 'A'}</span>
                        </div>
                        {editMode ? (
                            <EditableText
                                value={String(sections.name || 'Your Name')}
                                onChange={(v) => updateField('name', v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                as="h1"
                                className="text-xl font-bold text-center"
                            />
                        ) : (
                            <h1 className="text-xl font-bold text-center">{sections.name || 'Your Name'}</h1>
                        )}
                        {editMode ? (
                            <EditableText
                                value={String(sections.title || 'Creative Professional')}
                                onChange={(v) => updateField('title', v)}
                                editMode={editMode}
                                liveUpdate
                                layoutSafe
                                as="div"
                                className="text-center text-purple-100 mt-1.5 text-sm"
                            />
                        ) : (
                            <p className="text-center text-purple-100 mt-1.5 text-sm">{sections.title || 'Creative Professional'}</p>
                        )}
                    </div>

                    <div className="space-y-5">
                        <ContactSection title="Contact">
                            {editMode ? (
                                <>
                                    <EditableText
                                        value={String(sections.email || '')}
                                        onChange={(v) => updateField('email', v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        as="div"
                                        className="text-xs text-purple-100"
                                    />
                                    <EditableText
                                        value={String(sections.phone || '')}
                                        onChange={(v) => updateField('phone', v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        as="div"
                                        className="text-xs text-purple-100"
                                    />
                                    <EditableText
                                        value={String(sections.location || '')}
                                        onChange={(v) => updateField('location', v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        as="div"
                                        className="text-xs text-purple-100"
                                    />
                                </>
                            ) : (
                                <>
                                    {sections.email && <p className="text-xs text-purple-100">{sections.email}</p>}
                                    {sections.phone && <p className="text-xs text-purple-100">{sections.phone}</p>}
                                    {sections.location && <p className="text-xs text-purple-100">{sections.location}</p>}
                                </>
                            )}
                        </ContactSection>

                        {sections.skills && sections.skills.length > 0 && (
                            <ContactSection title="Skills">
                                {editMode ? (
                                    <EditableText
                                        value={(Array.isArray(sections.skills) ? sections.skills : []).map(String).join('\n')}
                                        onChange={(v) => updateListFromText('skills', v)}
                                        editMode={editMode}
                                        liveUpdate
                                        layoutSafe
                                        as="div"
                                        multiline
                                        className="text-xs text-purple-100 whitespace-pre-wrap"
                                    />
                                ) : (
                                    <div className="space-y-2">
                                        {sections.skills.map((skill: string, idx: number) => (
                                            <div key={idx} className="bg-white/20 backdrop-blur-sm px-2.5 py-1 rounded-lg text-xs">
                                                {skill}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </ContactSection>
                        )}
                    </div>
                </div>

                {/* Main Content */}
                <div className="p-6 space-y-6 flex-1">
                    {sections.summary && (
                        <div>
                            <div className="flex items-center gap-2 mb-2.5">
                                <Sparkles className="w-4 h-4 text-purple-600" />
                                <h2 className="text-lg font-bold text-slate-900">About Me</h2>
                            </div>
                            {editMode ? (
                                <EditableText
                                    value={String(sections.summary || '')}
                                    onChange={(v) => updateField('summary', v)}
                                    editMode={editMode}
                                    liveUpdate
                                    layoutSafe
                                    as="div"
                                    multiline
                                    className="text-slate-700 leading-snug text-sm"
                                />
                            ) : (
                                <p className="text-slate-700 leading-snug text-sm">{sections.summary}</p>
                            )}
                        </div>
                    )}

                    {sections.experience && sections.experience.length > 0 && (
                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <Briefcase className="w-4 h-4 text-purple-600" />
                                <h2 className="text-lg font-bold text-slate-900">Experience</h2>
                            </div>
                            <div className="space-y-4">
                                {sections.experience.map((exp: any, idx: number) => (
                                    <div key={idx} className="bg-white rounded-xl p-4 border-l-4 border-purple-500 shadow-sm">
                                        {editMode ? (
                                            <EditableText
                                                value={String(exp.title || '')}
                                                onChange={(v) => updateArrayItem('experience', idx, 'title', v)}
                                                editMode={editMode}
                                                liveUpdate
                                                layoutSafe
                                                as="div"
                                                className="font-bold text-slate-900 text-base"
                                            />
                                        ) : (
                                            <h4 className="font-bold text-slate-900 text-base">{exp.title}</h4>
                                        )}
                                        {editMode ? (
                                            <div className="text-purple-600 font-medium text-xs">
                                                <EditableText
                                                    value={String(exp.company || '')}
                                                    onChange={(v) => updateArrayItem('experience', idx, 'company', v)}
                                                    editMode={editMode}
                                                    liveUpdate
                                                    layoutSafe
                                                    as="span"
                                                />
                                                <span> • </span>
                                                <EditableText
                                                    value={String(exp.duration || '')}
                                                    onChange={(v) => updateArrayItem('experience', idx, 'duration', v)}
                                                    editMode={editMode}
                                                    liveUpdate
                                                    layoutSafe
                                                    as="span"
                                                />
                                            </div>
                                        ) : (
                                            <p className="text-purple-600 font-medium text-xs">{exp.company} • {exp.duration}</p>
                                        )}
                                        <div className="mt-1.5">
                                            {editMode ? (
                                                <EditableText
                                                    value={String(exp.description || '')}
                                                    onChange={(v) => updateArrayItem('experience', idx, 'description', v)}
                                                    editMode={editMode}
                                                    liveUpdate
                                                    layoutSafe
                                                    as="div"
                                                    multiline
                                                    className="text-slate-700 leading-snug text-sm"
                                                />
                                            ) : (
                                                <RenderMaybeBullets
                                                    text={exp.description}
                                                    forceBullets
                                                    className="text-slate-700 leading-snug text-sm"
                                                />
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {sections.projects && sections.projects.length > 0 && (
                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <Code className="w-4 h-4 text-purple-600" />
                                <h2 className="text-lg font-bold text-slate-900">Key Projects</h2>
                            </div>
                            <div className="space-y-3">
                                {sections.projects.map((proj: any, idx: number) => (
                                    <div key={idx} className="bg-white rounded-xl p-4 border-l-4 border-pink-500 shadow-sm">
                                        <div className="flex justify-between items-start mb-1.5 gap-3">
                                            {editMode ? (
                                                <EditableText
                                                    value={String(proj.title || proj.name || '')}
                                                    onChange={(v) => updateArrayItem('projects', idx, 'title', v)}
                                                    editMode={editMode}
                                                    liveUpdate
                                                    layoutSafe
                                                    as="div"
                                                    className="font-bold text-slate-900 text-base"
                                                />
                                            ) : (
                                                <h4 className="font-bold text-slate-900 text-base">{proj.title}</h4>
                                            )}
                                            {proj.link && (
                                                <a href={proj.link} target="_blank" rel="noopener noreferrer" className="text-[10px] text-purple-600 hover:underline whitespace-nowrap">
                                                    View Project
                                                </a>
                                            )}
                                        </div>
                                        {editMode ? (
                                            <EditableText
                                                value={String(proj.description || '')}
                                                onChange={(v) => updateArrayItem('projects', idx, 'description', v)}
                                                editMode={editMode}
                                                liveUpdate
                                                layoutSafe
                                                as="div"
                                                multiline
                                                className="text-slate-700 text-xs mb-1.5"
                                            />
                                        ) : (
                                            <p className="text-slate-700 text-xs mb-1.5">{proj.description}</p>
                                        )}
                                        {proj.technologies && (
                                            <div className="flex flex-wrap gap-1 mt-2">
                                                {proj.technologies.split(',').map((tech: string, i: number) => (
                                                    <span key={i} className="text-[10px] px-1.5 py-0.5 bg-purple-50 text-purple-700 border border-purple-200 rounded">
                                                        {tech.trim()}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Dynamic Custom Sections */}
                    {sections.custom_sections && sections.custom_sections.length > 0 && sections.custom_sections.map((section: any, idx: number) => (
                        <div key={idx}>
                            <div className="flex items-center gap-2 mb-3">
                                <Layers className="w-4 h-4 text-purple-600" />
                                <h2 className="text-lg font-bold text-slate-900">{section.heading}</h2>
                            </div>
                            <div className="space-y-3">
                                {section.items.map((item: any, i: number) => (
                                    <div key={i} className="bg-white rounded-xl p-4 border-l-4 border-purple-400 shadow-sm">
                                        <div className="flex justify-between items-baseline mb-1">
                                            <h4 className="font-bold text-slate-900 text-sm">{item.title}</h4>
                                            {item.date && <span className="text-[10px] text-purple-600 whitespace-nowrap">{item.date}</span>}
                                        </div>
                                        {item.subtitle && <p className="text-purple-600 text-xs mb-1">{item.subtitle}</p>}
                                        <p className="text-slate-700 text-xs leading-snug">{item.content}</p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}

                    {sections.certifications && sections.certifications.length > 0 && (
                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <Award className="w-4 h-4 text-purple-600" />
                                <h2 className="text-lg font-bold text-slate-900">Certifications</h2>
                            </div>
                            <div className="grid sm:grid-cols-2 gap-4">
                                {sections.certifications.map((cert: any, idx: number) => (
                                    <div key={idx} className="bg-white rounded-xl p-3 shadow-sm border-l-4 border-pink-400">
                                        <div className="flex items-start gap-3">
                                            <Award className="w-3.5 h-3.5 text-purple-600 mt-0.5 shrink-0" />
                                            <div>
                                                <h4 className="font-semibold text-slate-900 text-xs">{cert.name}</h4>
                                                <p className="text-[10px] text-purple-600">{cert.issuer} • {cert.year}</p>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {sections.education && sections.education.length > 0 && (
                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <GraduationCap className="w-4 h-4 text-purple-600" />
                                <h2 className="text-lg font-bold text-slate-900">Education</h2>
                            </div>
                            <div className="space-y-2.5">
                                {sections.education.map((edu: any, idx: number) => (
                                    <div key={idx} className="bg-white rounded-xl p-3 shadow-sm">
                                        {editMode ? (
                                            <EditableText
                                                value={String(edu.degree || '')}
                                                onChange={(v) => updateArrayItem('education', idx, 'degree', v)}
                                                editMode={editMode}
                                                liveUpdate
                                                layoutSafe
                                                as="div"
                                                className="font-bold text-slate-900 text-sm"
                                            />
                                        ) : (
                                            <h4 className="font-bold text-slate-900 text-sm">{edu.degree}</h4>
                                        )}
                                        {editMode ? (
                                            <div className="text-purple-600 text-xs">
                                                <EditableText
                                                    value={String(edu.institution || '')}
                                                    onChange={(v) => updateArrayItem('education', idx, 'institution', v)}
                                                    editMode={editMode}
                                                    liveUpdate
                                                    layoutSafe
                                                    as="span"
                                                />
                                                <span> • </span>
                                                <EditableText
                                                    value={String(edu.year || '')}
                                                    onChange={(v) => updateArrayItem('education', idx, 'year', v)}
                                                    editMode={editMode}
                                                    liveUpdate
                                                    layoutSafe
                                                    as="span"
                                                />
                                            </div>
                                        ) : (
                                            <p className="text-purple-600 text-xs">{edu.institution} • {edu.year}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

function ContactSection({ title, children }: { title: string, children: React.ReactNode }) {
    return (
        <div>
            <h3 className="text-purple-200 font-semibold mb-3 uppercase tracking-wider text-xs">{title}</h3>
            {children}
        </div>
    );
}
