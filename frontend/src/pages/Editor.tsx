import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
    Download,
    Plus,
    Trash2,
    FileJson,
    ChevronDown,
    Upload,
    Wand2,
} from 'lucide-react';
import { useResumeStore } from '../store/resumeStore';
import ResumePreview from '../components/ResumePreview';
import { exportToJSON, exportToPDF, exportToCSV } from '../utils/exportUtils';
import { importResume, extractResumeDataFromText } from '../utils/importUtils';

export default function Editor() {
    const resume = useResumeStore((state) => state.resume);
    const {
        updatePersonal,
        importParsed,
        addSkill,
        removeSkill,
        addExperience,
        updateExperience,
        removeExperience,
        addEducation,
        updateEducation,
        removeEducation,
        addProject,
        updateProject,
        removeProject,
        addCertification,
        updateCertification,
        removeCertification,
        setTemplate,
        loadFromLocalStorage,
        saveToLocalStorage,
    } = useResumeStore((state) => ({
        updatePersonal: state.updatePersonal,
        importParsed: state.importParsed,
        addSkill: state.addSkill,
        removeSkill: state.removeSkill,
        addExperience: state.addExperience,
        updateExperience: state.updateExperience,
        removeExperience: state.removeExperience,
        addEducation: state.addEducation,
        updateEducation: state.updateEducation,
        removeEducation: state.removeEducation,
        addProject: state.addProject,
        updateProject: state.updateProject,
        removeProject: state.removeProject,
        addCertification: state.addCertification,
        updateCertification: state.updateCertification,
        removeCertification: state.removeCertification,
        setTemplate: state.setTemplate,
        loadFromLocalStorage: state.loadFromLocalStorage,
        saveToLocalStorage: state.saveToLocalStorage,
    }));

    const [newSkill, setNewSkill] = useState('');
    const [importError, setImportError] = useState('');
    const [importLoading, setImportLoading] = useState(false);
    const [expandedSections, setExpandedSections] = useState({
        personal: true,
        skills: true,
        experience: true,
        education: true,
        projects: false,
        certifications: false,
    });
    const [aiLoading, setAiLoading] = useState<{ [key: string]: boolean }>({});
    const [aiMsg, setAiMsg] = useState<{ [key: string]: string }>({});

    useEffect(() => {
        loadFromLocalStorage();
        const raw = localStorage.getItem('revisedResumeRaw');
        if (raw) {
            try {
                const parsed = extractResumeDataFromText(raw);
                importParsed(parsed);
            } finally {
                localStorage.removeItem('revisedResumeRaw');
            }
        }
    }, []);

    useEffect(() => {
        saveToLocalStorage();
    }, [resume]);

    const toggleSection = (section: keyof typeof expandedSections) => {
        setExpandedSections((prev) => ({
            ...prev,
            [section]: !prev[section],
        }));
    };

    const improveTextWithAI = async (
        text: string,
        context: { section: string; role?: string; company?: string },
    ): Promise<string> => {
        try {
            const resp = await fetch('/api/ai/rewrite', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, ...context }),
            });
            const data = await resp.json();
            return (data && data.improvedText) || text;
        } catch (e) {
            return text;
        }
    };

    const handleExport = (format: 'pdf' | 'json' | 'csv') => {
        if (format === 'pdf') {
            exportToPDF('resume-preview', resume);
        } else if (format === 'json') {
            exportToJSON(resume);
        } else if (format === 'csv') {
            exportToCSV(resume);
        }
    };

    const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        setImportError('');
        setImportLoading(true);

        try {
            const data = await importResume(file);
            importParsed(data);
            setImportError('');
        } catch (error) {
            setImportError(
                error instanceof Error ? error.message : 'Failed to import resume'
            );
        } finally {
            setImportLoading(false);
            event.target.value = '';
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
            {/* Header */}
            <nav className="sticky top-0 z-50 bg-white/95 backdrop-blur border-b border-slate-200">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
                        <h1 className="text-2xl font-bold text-slate-900">Templates</h1>
                        <div className="flex flex-wrap gap-2">
                            <select
                                value={resume.template}
                                onChange={(e) => setTemplate(e.target.value as any)}
                                className="px-3 py-2 border border-slate-300 rounded-lg text-sm hover:border-slate-400 transition-colors"
                            >
                                <option value="classic">Classic</option>
                                <option value="professional">Professional</option>
                                <option value="elegant">Elegant</option>
                                <option value="creative">Creative</option>
                                <option value="boldProfessional">Bold Professional</option>
                                <option value="traditional">Traditional</option>
                                <option value="modern">Modern</option>
                                <option value="executive">Executive</option>
                            </select>

                            <div className="relative group">
                                <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 transition-colors text-sm">
                                    <Download className="w-4 h-4" />
                                    Export
                                    <ChevronDown className="w-4 h-4" />
                                </button>
                                <div className="absolute right-0 mt-1 w-40 bg-white rounded-lg shadow-lg border border-slate-200 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all">
                                    <button
                                        onClick={() => handleExport('pdf')}
                                        className="block w-full text-left px-4 py-2 hover:bg-slate-50 text-sm text-slate-700 first:rounded-t-lg"
                                    >
                                        PDF
                                    </button>
                                    <button
                                        onClick={() => handleExport('json')}
                                        className="block w-full text-left px-4 py-2 hover:bg-slate-50 text-sm text-slate-700 flex items-center gap-2"
                                    >
                                        <FileJson className="w-4 h-4" />
                                        JSON
                                    </button>
                                    <button
                                        onClick={() => handleExport('csv')}
                                        className="block w-full text-left px-4 py-2 hover:bg-slate-50 text-sm text-slate-700 last:rounded-b-lg"
                                    >
                                        CSV
                                    </button>
                                </div>
                            </div>

                            <label className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2 transition-colors text-sm cursor-pointer">
                                <Upload className="w-4 h-4" />
                                Import
                                <input
                                    type="file"
                                    accept=".pdf,.json,.docx"
                                    onChange={handleImport}
                                    disabled={importLoading}
                                    className="hidden"
                                />
                            </label>
                        </div>
                    </div>

                    {importError && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700"
                        >
                            {importError}
                        </motion.div>
                    )}

                    {importLoading && (
                        <motion.div
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700"
                        >
                            Importing resume...
                        </motion.div>
                    )}
                </div>
            </nav>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Editor Panel */}
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="space-y-4"
                    >
                        {/* Personal Information */}
                        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
                            <button
                                onClick={() => toggleSection('personal')}
                                className="w-full px-6 py-4 flex justify-between items-center hover:bg-slate-50 transition-colors border-b border-slate-200"
                            >
                                <h2 className="text-lg font-semibold text-slate-900">Personal Information</h2>
                                <ChevronDown
                                    className={`w-5 h-5 transition-transform ${expandedSections.personal ? 'rotate-180' : ''
                                        }`}
                                />
                            </button>
                            {expandedSections.personal && (
                                <div className="p-6 space-y-4">
                                    <input
                                        type="text"
                                        placeholder="Full Name"
                                        value={resume.name}
                                        onChange={(e) => updatePersonal({ name: e.target.value })}
                                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <input
                                        type="email"
                                        placeholder="Email"
                                        value={resume.email}
                                        onChange={(e) => updatePersonal({ email: e.target.value })}
                                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <input
                                        type="tel"
                                        placeholder="Phone"
                                        value={resume.phone}
                                        onChange={(e) => updatePersonal({ phone: e.target.value })}
                                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <input
                                        type="text"
                                        placeholder="Location"
                                        value={resume.location}
                                        onChange={(e) => updatePersonal({ location: e.target.value })}
                                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <input
                                        type="url"
                                        placeholder="Website (optional)"
                                        value={resume.website}
                                        onChange={(e) => updatePersonal({ website: e.target.value })}
                                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <textarea
                                        placeholder="Professional Summary"
                                        value={resume.summary}
                                        onChange={(e) => updatePersonal({ summary: e.target.value })}
                                        rows={4}
                                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                            )}
                        </div>

                        {/* Skills */}
                        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
                            <button
                                onClick={() => toggleSection('skills')}
                                className="w-full px-6 py-4 flex justify-between items-center hover:bg-slate-50 transition-colors border-b border-slate-200"
                            >
                                <h2 className="text-lg font-semibold text-slate-900">Skills</h2>
                                <ChevronDown
                                    className={`w-5 h-5 transition-transform ${expandedSections.skills ? 'rotate-180' : ''
                                        }`}
                                />
                            </button>
                            {expandedSections.skills && (
                                <div className="p-6 space-y-4">
                                    <div className="flex flex-wrap gap-2 mb-4">
                                        {resume.skills.map((skill) => (
                                            <motion.div
                                                key={skill}
                                                initial={{ scale: 0 }}
                                                animate={{ scale: 1 }}
                                                exit={{ scale: 0 }}
                                                className="flex items-center gap-2 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm"
                                            >
                                                {skill}
                                                <button
                                                    onClick={() => removeSkill(skill)}
                                                    className="ml-1 hover:text-blue-900"
                                                >
                                                    ×
                                                </button>
                                            </motion.div>
                                        ))}
                                    </div>
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            placeholder="Add a skill"
                                            value={newSkill}
                                            onChange={(e) => setNewSkill(e.target.value)}
                                            onKeyPress={(e) => {
                                                if (e.key === 'Enter' && newSkill.trim()) {
                                                    addSkill(newSkill.trim());
                                                    setNewSkill('');
                                                }
                                            }}
                                            className="flex-1 px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                        <button
                                            onClick={() => {
                                                if (newSkill.trim()) {
                                                    addSkill(newSkill.trim());
                                                    setNewSkill('');
                                                }
                                            }}
                                            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                                        >
                                            <Plus className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Experience */}
                        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
                            <button
                                onClick={() => toggleSection('experience')}
                                className="w-full px-6 py-4 flex justify-between items-center hover:bg-slate-50 transition-colors border-b border-slate-200"
                            >
                                <h2 className="text-lg font-semibold text-slate-900">Experience</h2>
                                <ChevronDown
                                    className={`w-5 h-5 transition-transform ${expandedSections.experience ? 'rotate-180' : ''
                                        }`}
                                />
                            </button>
                            {expandedSections.experience && (
                                <div className="p-6 space-y-4">
                                    {resume.experience.map((exp, idx) => (
                                        <motion.div
                                            key={exp.id}
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="p-4 border border-slate-200 rounded-lg space-y-3"
                                        >
                                            <div className="flex justify-between items-start">
                                                <span className="text-sm font-semibold text-slate-600">Experience {idx + 1}</span>
                                                <button
                                                    onClick={() => removeExperience(exp.id)}
                                                    className="text-red-600 hover:text-red-700"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                            <input
                                                type="text"
                                                placeholder="Company"
                                                value={exp.company}
                                                onChange={(e) => updateExperience(exp.id, { company: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <input
                                                type="text"
                                                placeholder="Position"
                                                value={exp.position}
                                                onChange={(e) => updateExperience(exp.id, { position: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <div className="grid grid-cols-2 gap-2">
                                                <input
                                                    type="month"
                                                    placeholder="Start Date"
                                                    value={exp.startDate}
                                                    onChange={(e) => updateExperience(exp.id, { startDate: e.target.value })}
                                                    className="px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                />
                                                <input
                                                    type="month"
                                                    placeholder="End Date"
                                                    value={exp.endDate}
                                                    disabled={exp.currentlyWorking}
                                                    onChange={(e) => updateExperience(exp.id, { endDate: e.target.value })}
                                                    className="px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100"
                                                />
                                            </div>
                                            <label className="flex items-center gap-2 text-sm">
                                                <input
                                                    type="checkbox"
                                                    checked={exp.currentlyWorking}
                                                    onChange={(e) => updateExperience(exp.id, { currentlyWorking: e.target.checked })}
                                                    className="rounded"
                                                />
                                                Currently working
                                            </label>
                                            <textarea
                                                placeholder="Description"
                                                value={exp.description}
                                                onChange={(e) => updateExperience(exp.id, { description: e.target.value })}
                                                rows={3}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <div className="flex justify-end mt-2">
                                                <button
                                                    onClick={async () => {
                                                        setAiLoading((m) => ({ ...m, [exp.id]: true }));
                                                        const improved = await improveTextWithAI(exp.description, {
                                                            section: 'experience',
                                                            role: exp.position,
                                                            company: exp.company,
                                                        });
                                                        updateExperience(exp.id, { description: improved });
                                                        setAiLoading((m) => ({ ...m, [exp.id]: false }));
                                                        setAiMsg((m) => ({ ...m, [exp.id]: improved !== exp.description ? 'Improved' : 'No change' }));
                                                    }}
                                                    disabled={aiLoading[exp.id] || !exp.description.trim()}
                                                    className="px-3 py-1 text-xs rounded bg-orange-200 text-black hover:bg-orange-300 disabled:opacity-50 border border-orange-300"
                                                >
                                                    {aiLoading[exp.id] ? 'Improving…' : (<><Wand2 className="inline w-3 h-3 mr-1" />Enhance with AI</>)}
                                                </button>
                                                {aiMsg[exp.id] && (
                                                    <span className="ml-2 text-xs text-slate-500">{aiMsg[exp.id]}</span>
                                                )}
                                            </div>
                                        </motion.div>
                                    ))}
                                    <button
                                        onClick={addExperience}
                                        className="w-full px-4 py-2 border-2 border-dashed border-slate-300 rounded-lg text-slate-600 hover:border-blue-400 hover:text-blue-600 transition-colors flex items-center justify-center gap-2"
                                    >
                                        <Plus className="w-4 h-4" />
                                        Add Experience
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Education */}
                        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
                            <button
                                onClick={() => toggleSection('education')}
                                className="w-full px-6 py-4 flex justify-between items-center hover:bg-slate-50 transition-colors border-b border-slate-200"
                            >
                                <h2 className="text-lg font-semibold text-slate-900">Education</h2>
                                <ChevronDown
                                    className={`w-5 h-5 transition-transform ${expandedSections.education ? 'rotate-180' : ''
                                        }`}
                                />
                            </button>
                            {expandedSections.education && (
                                <div className="p-6 space-y-4">
                                    {resume.education.map((edu, idx) => (
                                        <motion.div
                                            key={edu.id}
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="p-4 border border-slate-200 rounded-lg space-y-3"
                                        >
                                            <div className="flex justify-between items-start">
                                                <span className="text-sm font-semibold text-slate-600">Education {idx + 1}</span>
                                                <button
                                                    onClick={() => removeEducation(edu.id)}
                                                    className="text-red-600 hover:text-red-700"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                            <input
                                                type="text"
                                                placeholder="School/University"
                                                value={edu.school}
                                                onChange={(e) => updateEducation(edu.id, { school: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <input
                                                type="text"
                                                placeholder="Degree"
                                                value={edu.degree}
                                                onChange={(e) => updateEducation(edu.id, { degree: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <input
                                                type="text"
                                                placeholder="Field of Study"
                                                value={edu.field}
                                                onChange={(e) => updateEducation(edu.id, { field: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <input
                                                type="month"
                                                placeholder="Graduation Date"
                                                value={edu.graduationDate}
                                                onChange={(e) => updateEducation(edu.id, { graduationDate: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                        </motion.div>
                                    ))}
                                    <button
                                        onClick={addEducation}
                                        className="w-full px-4 py-2 border-2 border-dashed border-slate-300 rounded-lg text-slate-600 hover:border-blue-400 hover:text-blue-600 transition-colors flex items-center justify-center gap-2"
                                    >
                                        <Plus className="w-4 h-4" />
                                        Add Education
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Projects */}
                        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
                            <button
                                onClick={() => toggleSection('projects')}
                                className="w-full px-6 py-4 flex justify-between items-center hover:bg-slate-50 transition-colors border-b border-slate-200"
                            >
                                <h2 className="text-lg font-semibold text-slate-900">Projects</h2>
                                <ChevronDown
                                    className={`w-5 h-5 transition-transform ${expandedSections.projects ? 'rotate-180' : ''
                                        }`}
                                />
                            </button>
                            {expandedSections.projects && (
                                <div className="p-6 space-y-4">
                                    {resume.projects.map((proj, idx) => (
                                        <motion.div
                                            key={proj.id}
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="p-4 border border-slate-200 rounded-lg space-y-3"
                                        >
                                            <div className="flex justify-between items-start">
                                                <span className="text-sm font-semibold text-slate-600">Project {idx + 1}</span>
                                                <button
                                                    onClick={() => removeProject(proj.id)}
                                                    className="text-red-600 hover:text-red-700"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                            <input
                                                type="text"
                                                placeholder="Project Title"
                                                value={proj.title}
                                                onChange={(e) => updateProject(proj.id, { title: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <textarea
                                                placeholder="Description"
                                                value={proj.description}
                                                onChange={(e) => updateProject(proj.id, { description: e.target.value })}
                                                rows={2}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <div className="flex justify-end mt-2">
                                                <button
                                                    onClick={async () => {
                                                        setAiLoading((m) => ({ ...m, [proj.id]: true }));
                                                        const improved = await improveTextWithAI(proj.description, {
                                                            section: 'projects',
                                                            role: proj.title,
                                                            company: '',
                                                        });
                                                        updateProject(proj.id, { description: improved });
                                                        setAiLoading((m) => ({ ...m, [proj.id]: false }));
                                                        setAiMsg((m) => ({ ...m, [proj.id]: improved !== proj.description ? 'Improved' : 'No change' }));
                                                    }}
                                                    disabled={aiLoading[proj.id] || !proj.description.trim()}
                                                    className="px-3 py-1 text-xs rounded bg-orange-200 text-black hover:bg-orange-300 disabled:opacity-50 border border-orange-300"
                                                >
                                                    {aiLoading[proj.id] ? 'Improving…' : (<><Wand2 className="inline w-3 h-3 mr-1" />Enhance with AI</>)}
                                                </button>
                                                {aiMsg[proj.id] && (
                                                    <span className="ml-2 text-xs text-slate-500">{aiMsg[proj.id]}</span>
                                                )}
                                            </div>
                                            <input
                                                type="text"
                                                placeholder="Technologies (comma separated)"
                                                value={proj.technologies.join(', ')}
                                                onChange={(e) => updateProject(proj.id, { technologies: e.target.value.split(',').map(t => t.trim()) })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <input
                                                type="url"
                                                placeholder="Project Link (optional)"
                                                value={proj.link}
                                                onChange={(e) => updateProject(proj.id, { link: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                        </motion.div>
                                    ))}
                                    <button
                                        onClick={addProject}
                                        className="w-full px-4 py-2 border-2 border-dashed border-slate-300 rounded-lg text-slate-600 hover:border-blue-400 hover:text-blue-600 transition-colors flex items-center justify-center gap-2"
                                    >
                                        <Plus className="w-4 h-4" />
                                        Add Project
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Certifications */}
                        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
                            <button
                                onClick={() => toggleSection('certifications')}
                                className="w-full px-6 py-4 flex justify-between items-center hover:bg-slate-50 transition-colors border-b border-slate-200"
                            >
                                <h2 className="text-lg font-semibold text-slate-900">Certifications</h2>
                                <ChevronDown
                                    className={`w-5 h-5 transition-transform ${expandedSections.certifications ? 'rotate-180' : ''
                                        }`}
                                />
                            </button>
                            {expandedSections.certifications && (
                                <div className="p-6 space-y-4">
                                    {resume.certifications.map((cert, idx) => (
                                        <motion.div
                                            key={cert.id}
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="p-4 border border-slate-200 rounded-lg space-y-3"
                                        >
                                            <div className="flex justify-between items-start">
                                                <span className="text-sm font-semibold text-slate-600">Certification {idx + 1}</span>
                                                <button
                                                    onClick={() => removeCertification(cert.id)}
                                                    className="text-red-600 hover:text-red-700"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                            <input
                                                type="text"
                                                placeholder="Certification Title"
                                                value={cert.title}
                                                onChange={(e) => updateCertification(cert.id, { title: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <input
                                                type="text"
                                                placeholder="Issuer"
                                                value={cert.issuer}
                                                onChange={(e) => updateCertification(cert.id, { issuer: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <input
                                                type="month"
                                                placeholder="Issue Date"
                                                value={cert.issueDate}
                                                onChange={(e) => updateCertification(cert.id, { issueDate: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <input
                                                type="month"
                                                placeholder="Expiration Date (optional)"
                                                value={cert.expirationDate}
                                                onChange={(e) => updateCertification(cert.id, { expirationDate: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                            <input
                                                type="text"
                                                placeholder="Credential ID (optional)"
                                                value={cert.credentialId}
                                                onChange={(e) => updateCertification(cert.id, { credentialId: e.target.value })}
                                                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                        </motion.div>
                                    ))}
                                    <button
                                        onClick={addCertification}
                                        className="w-full px-4 py-2 border-2 border-dashed border-slate-300 rounded-lg text-slate-600 hover:border-blue-400 hover:text-blue-600 transition-colors flex items-center justify-center gap-2"
                                    >
                                        <Plus className="w-4 h-4" />
                                        Add Certification
                                    </button>
                                </div>
                            )}
                        </div>
                    </motion.div>

                    {/* Preview Panel */}
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="sticky top-24 h-fit max-h-[calc(100vh-6rem)] overflow-y-auto"
                    >
                        <ResumePreview resume={resume} />
                    </motion.div>
                </div>
            </div>
        </div>
    );
}
