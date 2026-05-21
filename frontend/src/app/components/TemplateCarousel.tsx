import { useState } from 'react';
import { useResume } from './ResumeContext';
import { ResumeTemplate } from '../types/resume';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './ui/button';

const templates: { id: ResumeTemplate; name: string; image: string }[] = [
  { id: 'modern', name: 'Modern', image: '/src/imports/modern.jpg' },
  { id: 'classic', name: 'Classic', image: '/src/imports/classic.jpg' },
  { id: 'creative', name: 'Creative', image: '/src/imports/creative.jpg' },
  { id: 'boldprofessional', name: 'Bold Professional', image: '/src/imports/BoldProfessional.jpg' },
  { id: 'contemporary', name: 'Contemporary', image: '/src/imports/traditional.jpg' },
  { id: 'executive', name: 'Executive', image: '/src/imports/executive.jpg' },
  { id: 'stylish', name: 'Stylish', image: '/src/imports/stylish.jpg' },
  { id: 'professional', name: 'Professional', image: '/src/imports/professional-1.jpg' },
];

interface TemplateCarouselProps {
  onSelect: () => void;
}

export function TemplateCarousel({ onSelect }: TemplateCarouselProps) {
  const { selectedTemplate, setSelectedTemplate } = useResume();
  const [currentIndex, setCurrentIndex] = useState(0);

  const handlePrevious = () => {
    setCurrentIndex((prev) => (prev === 0 ? templates.length - 1 : prev - 1));
  };

  const handleNext = () => {
    setCurrentIndex((prev) => (prev === templates.length - 1 ? 0 : prev + 1));
  };

  const handleSelect = (templateId: ResumeTemplate) => {
    setSelectedTemplate(templateId);
  };

  const handleContinue = () => {
    if (selectedTemplate) {
      onSelect();
    }
  };

  const visibleTemplates = [
    templates[(currentIndex - 1 + templates.length) % templates.length],
    templates[currentIndex],
    templates[(currentIndex + 1) % templates.length],
  ];

  return (
    <div className="flex h-full min-h-0 flex-col items-center justify-start overflow-y-auto bg-gray-50 p-8">
      <div className="max-w-6xl w-full py-8">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Choose Your Resume Template</h1>
          <p className="text-lg text-gray-600 mb-2">Browse through our templates and pick the one that best suits your style</p>
          <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
            <span>Use the</span>
            <div className="inline-flex items-center gap-1 px-2 py-1 bg-white rounded-md border border-gray-300">
              <ChevronLeft className="w-3 h-3" />
              <ChevronRight className="w-3 h-3" />
            </div>
            <span>arrows to browse templates</span>
          </div>
        </div>

        <div className="relative flex items-center justify-center gap-6 mb-12 py-8">
          {/* Previous Button */}
          <button
            onClick={handlePrevious}
            className="absolute left-0 z-10 p-3 bg-white rounded-full shadow-lg hover:bg-gray-50 transition-colors"
            aria-label="Previous template"
          >
            <ChevronLeft className="w-6 h-6 text-gray-700" />
          </button>

          {/* Template Cards */}
          <div className="flex items-center gap-6">
            {visibleTemplates.map((template, idx) => {
              const isCenter = idx === 1;
              const isSelected = template.id === selectedTemplate;

              return (
                <div
                  key={template.id}
                  onClick={() => handleSelect(template.id)}
                  className={`cursor-pointer transition-all duration-300 ${isCenter
                      ? 'scale-110 z-10'
                      : 'scale-90 opacity-50 hover:opacity-75'
                    }`}
                >
                  <div
                    className={`bg-white rounded-lg shadow-xl overflow-hidden transition-all ${isSelected ? 'ring-4 ring-blue-500' : 'ring-2 ring-gray-200 hover:ring-blue-300'
                      }`}
                  >
                    <div className="aspect-[210/297] w-64">
                      <img
                        src={template.image}
                        alt={template.name}
                        className="w-full h-full object-contain"
                      />
                    </div>
                    <div className={`p-4 text-center ${isSelected ? 'bg-blue-50' : ''}`}>
                      <h3 className={`font-semibold ${isSelected ? 'text-blue-700' : 'text-gray-900'}`}>
                        {template.name}
                        {isSelected && <span className="ml-2 text-blue-600">✓</span>}
                      </h3>
                      {isCenter && !isSelected && (
                        <p className="text-xs text-gray-500 mt-1">Click to select</p>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Next Button */}
          <button
            onClick={handleNext}
            className="absolute right-0 z-10 p-3 bg-white rounded-full shadow-lg hover:bg-gray-50 transition-colors"
            aria-label="Next template"
          >
            <ChevronRight className="w-6 h-6 text-gray-700" />
          </button>
        </div>

        {/* Dots Indicator */}
        <div className="flex justify-center gap-2 mb-8">
          {templates.map((template, idx) => (
            <button
              key={template.id}
              onClick={() => setCurrentIndex(idx)}
              className={`w-2 h-2 rounded-full transition-all ${idx === currentIndex
                  ? 'bg-blue-600 w-8'
                  : 'bg-gray-300 hover:bg-gray-400'
                }`}
              aria-label={`Go to ${template.name}`}
            />
          ))}
        </div>

        {/* Continue Button */}
        <div className="flex justify-center">
          <Button
            onClick={handleContinue}
            disabled={!selectedTemplate}
            size="lg"
            className="px-12 py-6 text-lg"
          >
            Continue
          </Button>
        </div>
      </div>
    </div>
  );
}
