import { ResumeData } from '../../types/resume';

interface CreativeTemplateProps {
  data: ResumeData;
}

export function CreativeTemplate({ data }: CreativeTemplateProps) {
  const occupation = String(data.occupation || '').trim();

  return (
    <div className="w-full h-full bg-white text-black overflow-auto relative">
      {/* Decorative elements */}
      <div className="absolute top-0 right-0 flex gap-0.5" aria-hidden="true">
        <div className="w-12 h-12 bg-[#00a99d]" />
        <div className="w-10 h-12 bg-[#f25a4b]" />
        <div className="w-14 h-12 bg-black" />
        <div className="w-8 h-12 bg-[#facc15]" />
      </div>

      {/* Left edge accent */}
      <div className="absolute left-0 top-0 bottom-0 w-2 bg-[#00a99d]" aria-hidden="true" />

      <div className="pl-6 pr-6 pt-2 pb-3">
        {/* Header */}
        <div className="mb-1 px-2 py-1.5">
          <div className="text-[7px] text-gray-700 mb-0.5">Hello! I&apos;m</div>
          <div className="text-sm font-bold text-black tracking-tight leading-tight">
            <span className="text-black">{data.firstName || 'Your'}</span>
            {' '}
            <span className="text-gray-500">{data.lastName || 'Name'}</span>
          </div>
          {occupation ? (
            <div className="text-xs italic text-gray-800 mt-0.5">
              {occupation}
            </div>
          ) : null}
        </div>

        {/* Summary - Full Width */}
        {data.summary && (
          <div className="mb-1.5 text-[7px] leading-tight text-gray-800 px-2">
            <p>{data.summary}</p>
          </div>
        )}

        <div className="grid grid-cols-12 gap-2">
          {/* Left Column: Contact, Skills */}
          <aside className="col-span-3 p-2">
            <section className="mb-1">
              <h3 className="font-bold text-[7px] uppercase tracking-wide mb-1 text-[#00a99d]">
                Contact
              </h3>
              <div className="h-px mb-1 bg-[#00a99d]" />
              <div className="space-y-1 text-[7px]">
                {data.phone && <div className="flex items-start gap-1.5"><span className="flex-shrink-0">📞</span><span className="break-all">{data.phone}</span></div>}
                {data.address && <div className="flex items-start gap-1.5"><span className="flex-shrink-0">📍</span><span className="break-words">{data.address}</span></div>}
                {data.email && <div className="flex items-start gap-1.5"><span className="flex-shrink-0">✉️</span><span className="break-all">{data.email}</span></div>}
                {data.website && <div className="flex items-start gap-1.5"><span className="flex-shrink-0">🌐</span><span className="break-all">{data.website}</span></div>}
              </div>
            </section>

            {data.skills.length > 0 && (
              <section className="mb-1">
                <h3 className="font-bold text-[7px] uppercase tracking-wide mb-1 text-[#00a99d]">
                  Skills
                </h3>
                <div className="h-px mb-1 bg-[#00a99d]" />
                <div className="space-y-1">
                  {data.skills.slice(0, 8).map((skill, idx) => (
                    <div key={idx} className="flex items-start gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full border mt-1 flex-shrink-0 border-[#00a99d]" />
                      <span className="text-[7px]">{skill}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </aside>

          {/* Right Column */}
          <main className="col-span-9">
            {/* Education */}
            {data.education.length > 0 && (
              <section className="mb-1">
                <h2 className="font-bold text-[7px] uppercase tracking-wide mb-1 text-[#00a99d]">
                  Education
                </h2>
                <div className="h-px mb-1 bg-[#00a99d]" />
                <div className="space-y-1">
                  {data.education.map((edu) => (
                    <div key={edu.id} className="flex gap-2">
                      <span className="w-1.5 h-1.5 rounded-full border mt-1 flex-shrink-0 border-[#00a99d]" />
                      <div>
                        <div className="font-semibold text-[7px]">{edu.degree}</div>
                        <div className="text-[7px] text-gray-700">{edu.institution}</div>
                        <div className="text-[7px] text-gray-600">
                          {edu.startDate} - {edu.endDate}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Experience */}
            {data.experience.length > 0 && (
              <section className="mb-1">
                <h2 className="font-bold text-[7px] uppercase tracking-wide mb-1 text-[#00a99d]">
                  Experience
                </h2>
                <div className="h-px mb-1 bg-[#00a99d]" />
                <div className="space-y-1.5">
                  {data.experience.map((exp) => (
                    <div key={exp.id} className="flex gap-2">
                      <span className="w-1.5 h-1.5 rounded-full border mt-1 flex-shrink-0 border-[#00a99d]" />
                      <div className="flex-1">
                        <div className="text-[7px] text-gray-600 mb-0.5">
                          {exp.startDate} - {exp.current ? 'Present' : exp.endDate}
                        </div>
                        <div className="font-semibold text-[7px]">
                          {exp.position} — {exp.company}
                        </div>
                        {exp.description && (
                          <div className="mt-1 text-[7px] leading-tight text-gray-800">
                            {exp.description.split('\n').map((line, idx) => (
                              <div key={idx}>{line}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Projects */}
            {data.projects.length > 0 && (
              <section className="mb-1">
                <h2 className="font-bold text-[7px] uppercase tracking-wide mb-1 text-[#00a99d]">
                  Projects
                </h2>
                <div className="h-px mb-1 bg-[#00a99d]" />
                <div className="space-y-1.5">
                  {data.projects.map((proj) => (
                    <div key={proj.id} className="flex gap-2">
                      <span className="w-1.5 h-1.5 rounded-full border mt-1 flex-shrink-0 border-[#00a99d]" />
                      <div className="flex-1">
                        <div className="font-semibold text-[7px]">
                          {proj.title}
                          {proj.link && (
                            <a href={proj.link} target="_blank" rel="noreferrer" className="text-[7px] text-gray-600 underline ml-1.5">
                              Link
                            </a>
                          )}
                        </div>
                        {proj.technologies && proj.technologies.length > 0 && (
                          <div className="text-[7px] text-gray-600 mt-0.5">
                            {proj.technologies.join(', ')}
                          </div>
                        )}
                        {proj.description && (
                          <div className="mt-1 text-[7px] leading-tight text-gray-800">
                            {proj.description}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Languages */}
            {data.languages.length > 0 && (
              <section className="mb-1">
                <h2 className="font-bold text-[7px] uppercase tracking-wide mb-1 text-[#00a99d]">
                  Languages
                </h2>
                <div className="h-px mb-1 bg-[#00a99d]" />
                <div className="space-y-1">
                  {data.languages.map((lang) => (
                    <div key={lang.id} className="flex gap-2">
                      <span className="w-1.5 h-1.5 rounded-full border mt-1 flex-shrink-0 border-[#00a99d]" />
                      <div className="text-[7px] leading-tight text-gray-800">
                        {lang.name} - {lang.proficiency}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
