import { useResume } from '../ResumeContext';
import { Textarea } from '../ui/textarea';
import { Label } from '../ui/label';
import { Button } from '../ui/button';
import { useState } from 'react';
import { rewriteWithAi } from '../../utils/aiAssist';
import { Sparkles } from 'lucide-react';
import { toast } from 'sonner';

export function SummaryStep() {
  const { resumeData, updateResumeData } = useResume();
  const [isAiLoading, setIsAiLoading] = useState(false);

  const handleAiAssist = async () => {
    if (isAiLoading) return;
    try {
      setIsAiLoading(true);
      const rewritten = await rewriteWithAi('summary', resumeData.summary, {});
      updateResumeData({ summary: rewritten });
      toast.success('Summary improved with AI.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'AI assistance failed.');
    } finally {
      setIsAiLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="summary" className="text-gray-600">Summary</Label>
          <Button
            type="button"
            size="sm"
            onClick={handleAiAssist}
            disabled={isAiLoading}
            className="bg-violet-600 text-white hover:bg-violet-700 border-violet-600"
          >
            <Sparkles className="w-4 h-4 mr-1.5" />
            {isAiLoading ? 'Assisting…' : 'Assist with AI'}
          </Button>
        </div>
        <Textarea
          id="summary"
          value={resumeData.summary}
          onChange={(e) => updateResumeData({ summary: e.target.value })}
          className="bg-gray-50 border-gray-200 min-h-[200px]"
          placeholder="Proactive, customer-orientated retail professional with over 4 years of experience in reputable shops..."
        />
        <p className="text-xs text-gray-500">
          {resumeData.summary.length} characters
        </p>
      </div>
    </div>
  );
}
