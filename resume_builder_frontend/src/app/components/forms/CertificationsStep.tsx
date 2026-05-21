import { useState } from 'react';
import { useResume } from '../ResumeContext';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Button } from '../ui/button';
import { Certification } from '../../types/resume';
import { Trash2, Plus } from 'lucide-react';

export function CertificationsStep() {
  const { resumeData, updateResumeData } = useResume();
  const certifications = resumeData.certifications || [];
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Certification>>({});

  const startNew = () => {
    setEditingId('new');
    setFormData({
      name: '',
      issuer: '',
      date: '',
    });
  };

  const saveCertification = () => {
    if (!formData.name || !formData.issuer) return;

    const certification: Certification = {
      id: editingId === 'new' ? Date.now().toString() : editingId!,
      name: formData.name || '',
      issuer: formData.issuer || '',
      date: formData.date || '',
    };

    if (editingId === 'new') {
      updateResumeData({ certifications: [...certifications, certification] });
    } else {
      updateResumeData({
        certifications: certifications.map((cert) =>
          cert.id === editingId ? certification : cert,
        ),
      });
    }

    setEditingId(null);
    setFormData({});
  };

  const deleteCertification = (id: string) => {
    updateResumeData({
      certifications: certifications.filter((cert) => cert.id !== id),
    });
  };

  const editCertification = (cert: Certification) => {
    setEditingId(cert.id);
    setFormData(cert);
  };

  return (
    <div className="space-y-6">
      {certifications.length > 0 && !editingId && (
        <div className="space-y-3">
          {certifications.map((cert) => (
            <div key={cert.id} className="p-4 border border-gray-200 rounded-lg">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold">{cert.name}</h3>
                  <p className="text-sm text-gray-600">{cert.issuer}</p>
                  {cert.date ? (
                    <p className="text-sm text-gray-500 mt-1">{cert.date}</p>
                  ) : null}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => editCertification(cert)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => deleteCertification(cert.id)}
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
          Add Certification
        </Button>
      )}

      {editingId && (
        <div className="space-y-4 p-4 border border-gray-200 rounded-lg">
          <div className="space-y-2">
            <Label>Certification Name</Label>
            <Input
              value={formData.name || ''}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="bg-gray-50 border-gray-200"
              placeholder="e.g., AWS Certified Solutions Architect"
            />
          </div>

          <div className="space-y-2">
            <Label>Issuer</Label>
            <Input
              value={formData.issuer || ''}
              onChange={(e) => setFormData({ ...formData, issuer: e.target.value })}
              className="bg-gray-50 border-gray-200"
              placeholder="e.g., Amazon Web Services"
            />
          </div>

          <div className="space-y-2">
            <Label>Date (Optional)</Label>
            <Input
              value={formData.date || ''}
              onChange={(e) => setFormData({ ...formData, date: e.target.value })}
              className="bg-gray-50 border-gray-200"
              placeholder="e.g., 2025"
            />
          </div>

          <div className="flex gap-2">
            <Button onClick={saveCertification} className="bg-blue-600 hover:bg-blue-700">
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
