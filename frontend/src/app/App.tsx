import { useState } from 'react';
import { ResumeProvider } from './components/ResumeContext';
import { ResumeForm } from './components/ResumeForm';
import { ResumePreview } from './components/ResumePreview';
import { TemplateCarousel } from './components/TemplateCarousel';
import { Globe, Lightbulb } from 'lucide-react';
import { Button } from './components/ui/button';

export default function App() {
  const [templateSelected, setTemplateSelected] = useState(false);

  return (
    <ResumeProvider>
      {!templateSelected ? (
        <TemplateCarousel onSelect={() => setTemplateSelected(true)} />
      ) : (
        <div className="size-full flex flex-col bg-white">
          {/* Top Bar */}
          <div className="border-b border-gray-200 px-6 py-3 flex items-center gap-4">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <span>Resume language</span>
              <Globe className="w-4 h-4" />
              <span>en-US</span>
            </div>
            <Button variant="ghost" size="sm" className="text-teal-600 hover:text-teal-700">
              <Lightbulb className="w-4 h-4 mr-2" />
              Tips
            </Button>
          </div>

          {/* Main Content */}
          <div className="flex-1 flex overflow-hidden">
            {/* Left Panel - Form */}
            <div className="w-1/2 border-r border-gray-200 overflow-hidden">
              <ResumeForm />
            </div>

            {/* Right Panel - Preview */}
            <div className="w-1/2 overflow-hidden">
              <ResumePreview />
            </div>
          </div>
        </div>
      )}
    </ResumeProvider>
  );
}