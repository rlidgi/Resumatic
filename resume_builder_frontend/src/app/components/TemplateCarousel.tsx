import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useResume } from './ResumeContext';
import { ResumeTemplate } from '../types/resume';
import { ChevronLeft, ChevronRight } from 'lucide-react';

/**
 * Same assets and layout as `templates/result.html` template carousel
 * (`#templateCarousel` + `.template-card`), so previews match the results page.
 */
const templates: { id: ResumeTemplate; name: string; image: string }[] = [
  { id: 'professional', name: 'Professional', image: '/static/images/professional.jpg' },
  { id: 'classic', name: 'Classic', image: '/static/images/classic.jpg' },
  { id: 'boldprofessional', name: 'Bold Professional', image: '/static/images/BoldProfessional.jpg' },
  { id: 'contemporary', name: 'Contemporary', image: '/static/images/traditional.jpg' },
  { id: 'modern', name: 'Modern', image: '/static/images/modern.jpg' },
  { id: 'creative', name: 'Creative', image: '/static/images/creative.jpg' },
  { id: 'executive', name: 'Executive', image: '/static/images/executive.jpg' },
  { id: 'stylish', name: 'Stylish', image: '/static/images/stylish.jpg' },
];

interface TemplateCarouselProps {
  onSelect: () => void;
}

export function TemplateCarousel({ onSelect }: TemplateCarouselProps) {
  const { selectedTemplate, setSelectedTemplate } = useResume();
  const carouselRef = useRef<HTMLDivElement | null>(null);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  const updateScrollState = useCallback(() => {
    const el = carouselRef.current;
    if (!el) return;
    const max = Math.max(0, el.scrollWidth - el.clientWidth);
    setAtStart(el.scrollLeft <= 1);
    setAtEnd(el.scrollLeft >= max - 1);
  }, []);

  useEffect(() => {
    const el = carouselRef.current;
    if (!el) return;
    updateScrollState();
    el.addEventListener('scroll', updateScrollState, { passive: true });
    window.addEventListener('resize', updateScrollState);
    return () => {
      el.removeEventListener('scroll', updateScrollState);
      window.removeEventListener('resize', updateScrollState);
    };
  }, [updateScrollState]);

  const getStep = useCallback(() => {
    const el = carouselRef.current;
    if (!el) return 400;
    const firstCard = el.querySelector('.template-card');
    if (firstCard) {
      const cardW = firstCard.getBoundingClientRect().width || 0;
      return Math.max(240, Math.round((cardW + 12) * 3));
    }
    return Math.round(el.clientWidth * 0.9);
  }, []);

  const scrollByAmount = useCallback(
    (delta: number) => {
      carouselRef.current?.scrollBy({ left: delta, behavior: 'smooth' });
    },
    []
  );

  const handleCarouselKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      scrollByAmount(-getStep());
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      scrollByAmount(getStep());
    }
  };

  return (
    <div className="flex flex-col items-center justify-start min-h-full bg-gray-50 p-8 overflow-auto">
      <div className="max-w-6xl w-full py-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Choose Your Resume Template</h1>
          <p className="text-lg text-gray-600 mb-2">
            Browse through our templates and pick the one that best suits your style
          </p>
          <p className="text-center text-xs text-gray-500 mb-3 sm:hidden">
            <ChevronLeft className="inline w-3 h-3 align-middle" aria-hidden />
            <span className="mx-1">Swipe to see more templates</span>
            <ChevronRight className="inline w-3 h-3 align-middle" aria-hidden />
          </p>
        </div>

        <div className="relative max-w-6xl mx-auto mb-12 bg-gray-100 rounded-xl">
          {/* Mobile swipe hints */}
          <div
            aria-hidden
            className="pointer-events-none sm:hidden absolute left-0 top-0 bottom-0 w-10 z-10 bg-gradient-to-r from-gray-100 to-transparent rounded-l-xl"
          />
          <div
            aria-hidden
            className="pointer-events-none sm:hidden absolute right-0 top-0 bottom-0 w-10 z-10 bg-gradient-to-l from-gray-100 to-transparent rounded-r-xl"
          />

          <button
            type="button"
            onClick={() => scrollByAmount(-getStep())}
            disabled={atStart}
            aria-label="Previous templates"
            className="hidden sm:flex items-center justify-center absolute left-0 top-1/2 -translate-y-1/2 z-20 w-10 h-10 rounded-full bg-white/95 shadow border border-gray-200 text-gray-700 hover:text-gray-900 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            type="button"
            onClick={() => scrollByAmount(getStep())}
            disabled={atEnd}
            aria-label="Next templates"
            className="hidden sm:flex items-center justify-center absolute right-0 top-1/2 -translate-y-1/2 z-20 w-10 h-10 rounded-full bg-white/95 shadow border border-gray-200 text-gray-700 hover:text-gray-900 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronRight className="w-5 h-5" />
          </button>

          <div
            aria-hidden
            className="pointer-events-none hidden sm:block absolute left-0 top-0 bottom-0 w-10 z-10 bg-gradient-to-r from-gray-100 to-transparent rounded-l-xl"
          />
          <div
            aria-hidden
            className="pointer-events-none hidden sm:block absolute right-0 top-0 bottom-0 w-10 z-10 bg-gradient-to-l from-gray-100 to-transparent rounded-r-xl"
          />

          <div
            ref={carouselRef}
            tabIndex={0}
            onKeyDown={handleCarouselKeyDown}
            className="no-scrollbar flex gap-3 overflow-x-auto py-24 px-10 scroll-smooth snap-x snap-mandatory outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 rounded-xl"
            role="list"
            aria-label="Resume templates"
          >
            {templates.map((template) => {
              const isSelected = template.id === selectedTemplate;
              return (
                <button
                  key={template.id}
                  type="button"
                  role="listitem"
                  data-template={template.id}
                  onClick={() => {
                    setSelectedTemplate(template.id);
                    onSelect();
                  }}
                  className={`template-card group flex-none w-44 sm:w-48 md:w-52 relative bg-white rounded-lg shadow hover:shadow-xl transition-all focus:outline-none focus:ring-1 overflow-hidden text-left transform-gpu origin-center hover:scale-[1.4] focus-visible:scale-[1.4] hover:z-10 focus-visible:z-10 snap-start ${
                    isSelected
                      ? 'border-2 border-blue-500 ring-2 ring-blue-500 ring-offset-2 z-10 scale-100'
                      : 'border border-transparent hover:border-blue-500 focus-visible:border-blue-500'
                  }`}
                >
                  <div className="p-3 pb-2">
                    <h4 className="font-semibold text-gray-800 text-sm text-left">
                      {template.name}
                      {isSelected ? <span className="ml-2 text-blue-600">✓</span> : null}
                    </h4>
                  </div>
                  <div className="w-full aspect-[3/4] bg-gray-50 p-2">
                    <img
                      src={template.image}
                      alt={`${template.name} template preview`}
                      className="h-full w-full object-contain rounded-md"
                      loading="lazy"
                      decoding="async"
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

      </div>
    </div>
  );
}
