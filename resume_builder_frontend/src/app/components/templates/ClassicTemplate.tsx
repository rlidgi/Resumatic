import { ResumeData } from '../../types/resume';

interface ClassicTemplateProps {
  data: ResumeData;
}

export function ClassicTemplate({ data }: ClassicTemplateProps) {
  const occupation = String(data.occupation || '').trim();

  return (
    <div className="w-full h-full bg-white text-gray-800 overflow-auto">
      {/* Header */}
      <div className="bg-[#e8ddd5] px-2 py-1.5 text-center border-b-4 border-rose-800">
        <h1 className="text-sm font-bold uppercase tracking-tight">
          <span className="text-slate-800">{data.firstName || 'First'}</span>
          {' '}
          <span className="text-rose-800">{data.lastName || 'Last'}</span>
        </h1>
        {occupation ? (
          <div className="text-[7px] font-normal uppercase tracking-wide mt-1 text-slate-700">
            {occupation}
          </div>
        ) : null}

        {/* Contact Info */}
        <div className="mt-1 pt-2 border-t border-rose-800/30">
          <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-[7px] text-slate-700">
            {data.address && <span>{data.address}</span>}
            {data.phone && <span>{data.phone}</span>}
            {data.email && <span>{data.email}</span>}
            {data.website && <span>{data.website}</span>}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-0">
        {/* Left Column */}
        <aside className="col-span-4 bg-[#f5f0ed] px-2 py-1.5 border-r border-rose-800">
          {/* Education */}
          {data.education.length > 0 && (
            <section className="mb-1.5">
              <h3 className="text-[7px] font-semibold uppercase tracking-wide text-center mb-1 text-rose-800">
                - Education -
              </h3>
              <div className="h-px mb-1.5 bg-rose-800" />
              <div className="space-y-1">
                {data.education.map((edu) => (
                  <div key={edu.id}>
                    <div className="font-semibold text-[7px] text-gray-900">{edu.degree}</div>
                    <div className="text-[7px] text-gray-600">{edu.institution}</div>
                    <div className="text-[7px] text-gray-500">
                      {edu.startDate} - {edu.endDate}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Skills */}
          {data.skills.length > 0 && (
            <section className="mb-1.5">
              <h3 className="text-[7px] font-semibold uppercase tracking-wide text-center mb-1 text-rose-800">
                - Skills -
              </h3>
              <div className="h-px mb-1.5 bg-rose-800" />
              <div className="space-y-1">
                {data.skills.map((skill, index) => (
                  <div key={index} className="text-[7px] text-gray-700">{skill}</div>
                ))}
              </div>
            </section>
          )}

          {/* Languages */}
          {data.languages.length > 0 && (
            <section className="mb-1.5">
              <h3 className="text-[7px] font-semibold uppercase tracking-wide text-center mb-1 text-rose-800">
                - Languages -
              </h3>
              <div className="h-px mb-1.5 bg-rose-800" />
              <div className="space-y-1">
                {data.languages.map((lang) => (
                  <div key={lang.id} className="text-[7px] text-gray-700">
                    {lang.name} - {lang.proficiency}
                  </div>
                ))}
              </div>
            </section>
          )}
        </aside>

        {/* Right Column */}
        <main className="col-span-8 px-2 py-1.5">
          {/* Summary */}
          {data.summary && (
            <section className="mb-1.5">
              <h2 className="text-[7px] font-semibold uppercase tracking-wide mb-1 text-rose-800">
                Professional Statement
              </h2>
              <div className="h-px mb-1.5 bg-rose-800" />
              <p className="text-[7px] leading-tight text-gray-700">{data.summary}</p>
            </section>
          )}

          {/* Experience */}
          {data.experience.length > 0 && (
            <section className="mb-1.5">
              <h2 className="text-[7px] font-semibold uppercase tracking-wide mb-1 text-rose-800">
                Work Experience
              </h2>
              <div className="h-px mb-1.5 bg-rose-800" />
              <div className="space-y-1.5">
                {data.experience.map((exp) => (
                  <div key={exp.id}>
                    <div className="font-semibold text-[7px] text-gray-900">
                      {exp.position} | {exp.company}
                    </div>
                    <div className="text-[7px] text-gray-500 mb-1">
                      {exp.startDate} - {exp.current ? 'Present' : exp.endDate}
                    </div>
                    {exp.description && (
                      <div className="text-[7px] leading-tight text-gray-700">
                        {exp.description.split('\n').map((line, idx) => (
                          <div key={idx}>{line}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Projects */}
          {data.projects.length > 0 && (
            <section className="mb-1.5">
              <h2 className="text-[7px] font-semibold uppercase tracking-wide mb-1 text-rose-800">
                Projects
              </h2>
              <div className="h-px mb-1.5 bg-rose-800" />
              <div className="space-y-1.5">
                {data.projects.map((proj) => (
                  <div key={proj.id}>
                    <div className="font-semibold text-[7px] text-gray-900">
                      {proj.title}
                    </div>
                    {proj.technologies && (
                      <div className="text-[7px] text-gray-600 mt-0.5">{proj.technologies.join(', ')}</div>
                    )}
                    {proj.description && (
                      <div className="text-[7px] leading-tight text-gray-700 mt-1">{proj.description}</div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
