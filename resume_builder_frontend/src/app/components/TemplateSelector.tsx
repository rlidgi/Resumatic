import { useResume } from './ResumeContext';
import { ResumeTemplate } from '../types/resume';
import { Check } from 'lucide-react';

const templates: { id: ResumeTemplate; name: string; description: string }[] = [
  { id: 'modern', name: 'Modern', description: 'Clean design with green header' },
  { id: 'classic', name: 'Classic', description: 'Traditional two-column layout' },
  { id: 'creative', name: 'Creative', description: 'Bold and colorful design' },
  { id: 'boldprofessional', name: 'Bold Professional', description: 'Strong design with accent bars' },
  { id: 'clean', name: 'Clean', description: 'Two-column with skill bars' },
  { id: 'contemporary', name: 'Contemporary', description: 'Timeline-style layout' },
  { id: 'executive', name: 'Executive', description: 'Professional with border header' },
  { id: 'stylish', name: 'Stylish', description: 'Elegant two-column design' },
];

export function TemplateSelector() {
  const { selectedTemplate, setSelectedTemplate } = useResume();

  return (
    <div className="p-6 bg-white border-b border-gray-200">
      <h3 className="text-lg font-semibold mb-4">Choose Template</h3>
      <div className="grid grid-cols-3 gap-3">
        {templates.map((template) => (
          <button
            key={template.id}
            onClick={() => setSelectedTemplate(template.id)}
            className={`p-4 border-2 rounded-lg text-left transition-all ${
              selectedTemplate === template.id
                ? 'border-blue-600 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="font-semibold text-sm">{template.name}</div>
                <div className="text-xs text-gray-600 mt-1">{template.description}</div>
              </div>
              {selectedTemplate === template.id && (
                <Check className="w-5 h-5 text-blue-600" />
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
