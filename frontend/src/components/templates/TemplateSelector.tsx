import React from 'react';
import { Check } from 'lucide-react';

type TemplateSelectorProps = {
    selectedTemplate: string;
    onSelect: (templateId: string) => void;
};

export default function TemplateSelector({ selectedTemplate, onSelect }: TemplateSelectorProps) {
    const canonicalSelectedTemplate = (() => {
        const template = (selectedTemplate || '').trim();
        const key = template.toLowerCase();
        switch (key) {
            case 'lavenderclassic':
            case 'lavender-classic':
            case 'lavender_classic':
                return 'elegant';
            case 'popart':
            case 'pop-art':
            case 'pop_art':
                return 'creative';
            case 'orangeheader':
            case 'orange-header':
            case 'orange_header':
                return 'boldProfessional';
            case 'boldprofessional':
            case 'bold-professional':
            case 'bold_professional':
                return 'boldProfessional';
            case 'bluelineclassic':
            case 'blue-line-classic':
            case 'blue_line_classic':
                return 'traditional';
            case 'cleansidebar':
            case 'clean-sidebar':
            case 'clean_sidebar':
                return 'modern';
            case 'timelineblue':
            case 'timeline-blue':
            case 'timeline_blue':
                return 'executive';
            default:
                return template;
        }
    })();

    const templates = [
        {
            id: 'professional',
            name: 'Professional',
            description: 'Traditional layout perfect for corporate roles',
            preview: (
                <div className="bg-white p-4 rounded-lg border border-slate-300 h-32">
                    <div className="border-b-2 border-slate-800 pb-2 mb-2">
                        <div className="h-2.5 bg-slate-800 rounded w-20 mb-1" />
                        <div className="h-1.5 bg-slate-600 rounded w-16" />
                    </div>
                    <div className="space-y-1.5">
                        <div className="h-1.5 bg-slate-300 rounded w-full" />
                        <div className="h-1.5 bg-slate-300 rounded w-4/5" />
                        <div className="h-1.5 bg-slate-300 rounded w-3/4" />
                    </div>
                </div>
            )
        },
        {
            id: 'minimal',
            name: 'Minimal',
            description: 'Simple and elegant with maximum whitespace',
            preview: (
                <div className="bg-white p-4 rounded-lg border border-slate-100 h-32">
                    <div className="text-center mb-3">
                        <div className="h-2 bg-slate-700 rounded w-16 mx-auto mb-1" />
                        <div className="h-1 bg-slate-400 rounded w-12 mx-auto" />
                    </div>
                    <div className="space-y-2">
                        <div className="h-1 bg-slate-200 rounded w-full" />
                        <div className="h-1 bg-slate-200 rounded w-5/6 mx-auto" />
                    </div>
                </div>
            )
        },
        {
            id: 'elegant',
            name: 'Elegant',
            description: 'Soft pastel sidebar with elegant serif typography',
            preview: (
                <div className="bg-[#f6f1fb] p-4 rounded-lg border border-purple-200 h-32 overflow-hidden">
                    <div className="grid grid-cols-12 gap-2 h-full">
                        <div className="col-span-4 bg-[#b8a4dc] rounded-md p-2 flex flex-col gap-2">
                            <div className="w-6 h-6 bg-[#6b4c9a] rounded-sm" />
                            <div className="h-2 bg-white/90 rounded w-10" />
                            <div className="space-y-1 mt-1">
                                <div className="h-1.5 bg-white/70 rounded w-full" />
                                <div className="h-1.5 bg-white/70 rounded w-4/5" />
                                <div className="h-1.5 bg-white/70 rounded w-3/4" />
                            </div>
                        </div>
                        <div className="col-span-8 bg-[#f6f1fb] rounded-md p-2">
                            <div className="h-1.5 bg-purple-200 rounded w-20 mb-2" />
                            <div className="space-y-1.5">
                                <div className="h-1.5 bg-purple-100 rounded w-full" />
                                <div className="h-1.5 bg-purple-100 rounded w-5/6" />
                                <div className="h-1.5 bg-purple-100 rounded w-4/6" />
                            </div>
                        </div>
                    </div>
                </div>
            )
        },
        {
            id: 'creative',
            name: 'Creative',
            description: 'Bold editorial grid with vibrant blocks and accents',
            preview: (
                <div className="bg-[#f6efe4] p-4 rounded-lg border border-emerald-200 h-32 overflow-hidden">
                    <div className="grid grid-cols-12 gap-2 h-full">
                        <div className="col-span-4 rounded-md overflow-hidden border border-black/10">
                            <div className="grid grid-cols-3">
                                <div className="h-8 bg-[#f25a4b]" />
                                <div className="h-8 bg-[#ffcc4d]" />
                                <div className="h-8 bg-[#00a99d]" />
                            </div>
                            <div className="h-full bg-[#00a99d]" />
                        </div>
                        <div className="col-span-8 rounded-md border border-black/10 bg-[#f6efe4] p-2">
                            <div className="h-2 bg-black/30 rounded w-24 mb-2" />
                            <div className="space-y-1">
                                <div className="h-1.5 bg-black/15 rounded w-full" />
                                <div className="h-1.5 bg-black/15 rounded w-5/6" />
                                <div className="h-1.5 bg-black/15 rounded w-4/6" />
                            </div>
                        </div>
                    </div>
                </div>
            )
        },
        {
            id: 'boldProfessional',
            name: 'Bold Professional',
            description: 'Bold header with strong accents and clean section rules',
            preview: (
                <div className="bg-white p-4 rounded-lg border border-orange-200 h-32 overflow-hidden">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 border-2 border-black grid place-items-center text-[10px] font-bold">DR</div>
                        <div className="h-2 bg-black rounded w-16" />
                        <div className="h-2 bg-[#f36b1c] rounded w-20" />
                    </div>
                    <div className="mt-2 h-3 bg-black rounded" />
                    <div className="mt-3 space-y-1.5">
                        <div className="h-1.5 bg-black/15 rounded w-full" />
                        <div className="h-1.5 bg-black/15 rounded w-5/6" />
                        <div className="h-1.5 bg-black/15 rounded w-4/6" />
                    </div>
                </div>
            )
        },
        {
            id: 'traditional',
            name: 'Contemporary',
            description: 'Classic serif with clean section rules and spacing',
            preview: (
                <div className="bg-white p-4 rounded-lg border border-slate-200 h-32 overflow-hidden">
                    <div className="text-center">
                        <div className="h-2 bg-[#243c6b] rounded w-24 mx-auto" />
                        <div className="mt-2 h-1.5 bg-slate-300 rounded w-40 mx-auto" />
                    </div>
                    <div className="mt-3">
                        <div className="flex items-center gap-2">
                            <div className="h-1.5 bg-[#243c6b] rounded w-16" />
                            <div className="h-px bg-[#243c6b]/60 flex-1" />
                        </div>
                        <div className="mt-2 space-y-1.5">
                            <div className="h-1.5 bg-slate-200 rounded w-full" />
                            <div className="h-1.5 bg-slate-200 rounded w-5/6" />
                            <div className="h-1.5 bg-slate-200 rounded w-3/4" />
                        </div>
                    </div>
                </div>
            )
        },
        {
            id: 'modern',
            name: 'Modern',
            description: 'Modern two-column layout with a tidy sidebar',
            preview: (
                <div className="bg-white p-4 rounded-lg border border-slate-200 h-32 overflow-hidden">
                    <div className="h-2 bg-slate-800 rounded w-24 mb-1" />
                    <div className="h-1.5 bg-slate-300 rounded w-40" />
                    <div className="mt-3 grid grid-cols-12 gap-2 h-[70px]">
                        <div className="col-span-7 space-y-2">
                            <div className="h-1.5 bg-slate-200 rounded w-full" />
                            <div className="h-1.5 bg-slate-200 rounded w-5/6" />
                            <div className="h-1.5 bg-slate-200 rounded w-4/6" />
                        </div>
                        <div className="col-span-5 space-y-2">
                            <div className="h-1.5 bg-slate-200 rounded w-full" />
                            <div className="h-1.5 bg-slate-200 rounded w-4/6" />
                            <div className="h-1.5 bg-slate-200 rounded w-5/6" />
                        </div>
                    </div>
                </div>
            )
        },
        {
            id: 'executive',
            name: 'Executive',
            description: 'Clean header with timeline styling and section labels',
            preview: (
                <div className="bg-white p-4 rounded-lg border border-slate-200 h-32 overflow-hidden">
                    <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full border border-slate-300 text-slate-700 grid place-items-center text-xs font-semibold">
                            JC
                        </div>
                        <div className="h-2 bg-sky-300 rounded w-20" />
                    </div>
                    <div className="mt-3 grid grid-cols-12 gap-2 h-[76px]">
                        <div className="col-span-4 space-y-2">
                            <div className="h-1.5 bg-sky-200 rounded w-10" />
                            <div className="h-1.5 bg-sky-200 rounded w-8" />
                            <div className="h-1.5 bg-sky-200 rounded w-9" />
                        </div>
                        <div className="col-span-1 relative">
                            <div className="absolute left-1/2 top-0 bottom-0 w-px bg-slate-200 -translate-x-1/2" />
                            <div className="absolute left-1/2 top-1 w-2 h-2 rounded-full bg-white border-2 border-slate-300 -translate-x-1/2" />
                        </div>
                        <div className="col-span-7 space-y-2">
                            <div className="h-1.5 bg-slate-200 rounded w-full" />
                            <div className="h-1.5 bg-slate-200 rounded w-5/6" />
                            <div className="h-1.5 bg-slate-200 rounded w-2/3" />
                        </div>
                    </div>
                </div>
            )
        },
    ];

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {templates.map((template) => (
                <div
                    key={template.id}
                    className={`cursor-pointer transition-all duration-200 hover:shadow-md ${canonicalSelectedTemplate === template.id
                        ? 'ring-2 ring-blue-500 shadow-md'
                        : 'hover:shadow-sm'
                        }`}
                    onClick={() => onSelect(template.id)}
                >
                    <div className="p-4">
                        <div className="flex items-center justify-between mb-2">
                            <h3 className="font-semibold text-slate-800">{template.name}</h3>
                            {canonicalSelectedTemplate === template.id && (
                                <Check className="w-5 h-5 text-blue-500" />
                            )}
                        </div>
                        <p className="text-sm text-slate-600 mb-3">{template.description}</p>
                        {template.preview}
                    </div>
                </div>
            ))}
        </div>
    );
}

