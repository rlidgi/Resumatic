import { ResumeData } from '../../types/resume';

interface MinimalTemplateProps {
  data: ResumeData;
}

export function MinimalTemplate({ data }: MinimalTemplateProps) {
  const occupation = String(data.occupation || '').trim();

  return (
    <div className="w-full h-full bg-white text-black overflow-auto p-4">
      {/* Header */}
      <div className="border-b-2 border-gray-300 pb-3 mb-3">
        <h1 className="text-xl font-bold uppercase tracking-tight">
          <span className="text-black">{data.firstName || 'Your'}</span>
          {' '}
          <span className="text-gray-500">{data.lastName || 'Name'}</span>
        </h1>
        {occupation ? (
          <div className="text-[9px] text-gray-700 font-medium mt-1">
            {occupation}
          </div>
        ) : null}

        {/* Contact */}
        <div className="flex flex-wrap gap-2 mt-2 text-[8px] text-gray-600">
          {data.email && <span>{data.email}</span>}
          {data.email && data.phone && <span>•</span>}
          {data.phone && <span>{data.phone}</span>}
          {data.phone && data.address && <span>•</span>}
          {data.address && <span>{data.address}</span>}
        </div>
      </div>

      {/* Summary */}
      {data.summary && (
        <section className="mb-3">
          <h2 className="text-[10px] font-bold tracking-wider uppercase border-b-2 border-gray-300 pb-1 mb-1.5 text-gray-900">
            Professional Summary
          </h2>
          <p className="text-[9px] leading-tight text-gray-700">{data.summary}</p>
        </section>
      )}

      {/* Experience */}
      {data.experience.length > 0 && (
        <section className="mb-3">
          <h2 className="text-[10px] font-bold tracking-wider uppercase border-b-2 border-gray-300 pb-1 mb-1.5 text-gray-900">
            Professional Experience
          </h2>
          {data.experience.map((exp) => (
            <div key={exp.id} className="mb-2 last:mb-0">
              <div className="flex justify-between items-start mb-1 gap-3">
                <div>
                  <h4 className="font-bold text-gray-900 text-[9px]">{exp.position}</h4>
                  <p className="text-gray-700 font-medium text-[9px]">{exp.company}</p>
                </div>
                <span className="text-[8px] text-gray-600 font-medium whitespace-nowrap">
                  {exp.startDate} - {exp.current ? 'Present' : exp.endDate}
                </span>
              </div>
              {exp.description && (
                <p className="text-[9px] leading-tight text-gray-700">
                  {exp.description.split('\n').map((line, idx) => (
                    <span key={idx}>{line}<br /></span>
                  ))}
                </p>
              )}
            </div>
          ))}
        </section>
      )}

      {/* Education */}
      {data.education.length > 0 && (
        <section className="mb-3">
          <h2 className="text-[10px] font-bold tracking-wider uppercase border-b-2 border-gray-300 pb-1 mb-1.5 text-gray-900">
            Education
          </h2>
          {data.education.map((edu) => (
            <div key={edu.id} className="mb-1.5 last:mb-0 flex justify-between items-start gap-3">
              <div>
                <h4 className="font-bold text-gray-900 text-[9px]">{edu.degree}</h4>
                <p className="text-gray-700 text-[9px]">{edu.institution}</p>
              </div>
              <span className="text-[8px] text-gray-600 font-medium whitespace-nowrap">
                {edu.startDate} - {edu.endDate}
              </span>
            </div>
          ))}
        </section>
      )}

      {/* Projects */}
      {data.projects.length > 0 && (
        <section className="mb-3">
          <h2 className="text-[10px] font-bold tracking-wider uppercase border-b-2 border-gray-300 pb-1 mb-1.5 text-gray-900">
            Projects
          </h2>
          {data.projects.map((proj) => (
            <div key={proj.id} className="mb-2 last:mb-0">
              <div className="flex justify-between items-start mb-0.5 gap-3">
                <h4 className="font-bold text-gray-900 text-[9px]">{proj.title}</h4>
                {proj.link && (
                  <a
                    href={proj.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[8px] text-gray-700 underline underline-offset-2 hover:text-gray-900 whitespace-nowrap"
                  >
                    Link
                  </a>
                )}
              </div>
              {proj.technologies && proj.technologies.length > 0 && (
                <p className="text-[8px] text-gray-600 mb-1">{proj.technologies.join(', ')}</p>
              )}
              {proj.description && (
                <p className="text-[9px] leading-tight text-gray-700">{proj.description}</p>
              )}
            </div>
          ))}
        </section>
      )}

      {/* Skills */}
      {data.skills.length > 0 && (
        <section className="mb-3">
          <h2 className="text-[10px] font-bold tracking-wider uppercase border-b-2 border-gray-300 pb-1 mb-1.5 text-gray-900">
            Core Competencies
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {data.skills.map((skill, index) => (
              <div key={index} className="text-gray-700 font-medium text-[9px]">
                • {skill}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Languages */}
      {data.languages.length > 0 && (
        <section className="mb-3">
          <h2 className="text-[10px] font-bold tracking-wider uppercase border-b-2 border-gray-300 pb-1 mb-1.5 text-gray-900">
            Languages
          </h2>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-gray-700 text-[9px]">
            {data.languages.map((lang) => (
              <span key={lang.id}>{lang.name} - {lang.proficiency}</span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
