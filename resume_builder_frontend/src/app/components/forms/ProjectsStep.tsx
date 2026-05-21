import { useState } from 'react';
import { useResume } from '../ResumeContext';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { Project } from '../../types/resume';
import { Trash2, Plus, Sparkles } from 'lucide-react';
import { formatDescriptionBullets } from '../../utils/formatDescriptionBullets';
import { rewriteWithAi } from '../../utils/aiAssist';
import { toast } from 'sonner';

export function ProjectsStep() {
  const { resumeData, updateResumeData } = useResume();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Project>>({});
  const [techInput, setTechInput] = useState('');
  const [isAiLoading, setIsAiLoading] = useState(false);

  const startNew = () => {
    setEditingId('new');
    setFormData({
      title: '',
      description: '',
      technologies: [],
      link: '',
    });
  };

  const saveProject = () => {
    if (!formData.title) return;

    const project: Project = {
      id: editingId === 'new' ? Date.now().toString() : editingId!,
      title: formData.title || '',
      description: formatDescriptionBullets(formData.description || ''),
      technologies: formData.technologies || [],
      link: formData.link,
    };

    if (editingId === 'new') {
      updateResumeData({ projects: [...resumeData.projects, project] });
    } else {
      updateResumeData({
        projects: resumeData.projects.map(proj =>
          proj.id === editingId ? project : proj
        ),
      });
    }

    setEditingId(null);
    setFormData({});
  };

  const deleteProject = (id: string) => {
    updateResumeData({
      projects: resumeData.projects.filter(proj => proj.id !== id),
    });
  };

  const editProject = (proj: Project) => {
    setEditingId(proj.id);
    setFormData(proj);
  };

  const handleAiAssist = async () => {
    if (isAiLoading) return;
    try {
      setIsAiLoading(true);
      const rewritten = await rewriteWithAi('project_description', formData.description || '', {
        title: formData.title || '',
        technologies: (formData.technologies || []).join(', '),
        link: formData.link || '',
      });
      setFormData({ ...formData, description: rewritten });
      toast.success('Description improved with AI.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'AI assistance failed.');
    } finally {
      setIsAiLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {resumeData.projects.length > 0 && !editingId && (
        <div className="space-y-3">
          {resumeData.projects.map((proj) => (
            <div key={proj.id} className="p-4 border border-gray-200 rounded-lg">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold">{proj.title}</h3>
                  <p className="text-sm text-gray-600 mt-1">{proj.description}</p>
                  {proj.technologies && proj.technologies.length > 0 && (
                    <p className="text-sm text-gray-500 mt-1">
                      {proj.technologies.join(', ')}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => editProject(proj)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => deleteProject(proj.id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!editingId && (
        <Button onClick={startNew} className="w-full" variant="outline">
          <Plus className="w-4 h-4 mr-2" />
          Add Project
        </Button>
      )}

      {editingId && (
        <div className="space-y-4 p-4 border border-gray-200 rounded-lg">
          <div className="space-y-2">
            <Label>Project Title</Label>
            <Input
              value={formData.title || ''}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="bg-gray-50 border-gray-200"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label>Description</Label>
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
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="bg-gray-50 border-gray-200 min-h-[100px]"
              placeholder="Describe what the project does and your role..."
            />
            <p className="text-xs text-gray-500">Each statement will be formatted as a bullet point.</p>
          </div>

          <div className="space-y-2">
            <Label>Technologies (comma-separated)</Label>
            <Input
              value={formData.technologies?.join(', ') || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  technologies: e.target.value.split(',').map(t => t.trim()).filter(Boolean),
                })
              }
              className="bg-gray-50 border-gray-200"
              placeholder="e.g., React, TypeScript, Node.js"
            />
          </div>

          <div className="space-y-2">
            <Label>Link (Optional)</Label>
            <Input
              value={formData.link || ''}
              onChange={(e) => setFormData({ ...formData, link: e.target.value })}
              className="bg-gray-50 border-gray-200"
              placeholder="https://..."
            />
          </div>

          <div className="flex gap-2">
            <Button onClick={saveProject} className="bg-blue-600 hover:bg-blue-700">
              Save
            </Button>
            <Button onClick={() => setEditingId(null)} variant="outline">
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
