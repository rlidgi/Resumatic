import { useResume } from '../ResumeContext';
import { Textarea } from '../ui/textarea';
import { Label } from '../ui/label';

export function SummaryStep() {
  const { resumeData, updateResumeData } = useResume();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold mb-2">Professional Summary</h2>
        <p className="text-gray-600 text-sm">
          Write a brief overview of your professional background, skills, and career goals.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="summary" className="text-gray-600">Summary</Label>
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
