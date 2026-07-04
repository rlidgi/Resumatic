import { ResumeData } from '../../types/resume';

interface ExecutiveTemplateProps {
  data: ResumeData;
}

export function ExecutiveTemplate({ data }: ExecutiveTemplateProps) {
  const fullName = `${data.firstName || 'YOUR'} ${data.lastName || 'NAME'}`.trim();
  const nameParts = fullName.split(/\s+/).filter(Boolean);
  const firstName = nameParts[0] || '';
  const lastName = nameParts.slice(1).join(' ');
  const occupation = String(data.occupation || '').trim();

  return (
    <div className="w-full h-full bg-white text-black overflow-auto">
      {/* Header */}
      <div className="border-b-2 p-3 text-center bg-[#e8ebf0] border-[#7b8ba8]">
        <h1 className="text-sm font-bold mb-0.5">
          <span className="text-slate-900">{firstName || 'YOUR'}</span>
          {lastName && <span className="text-slate-600"> {lastName}</span>}
        </h1>
        {occupation ? <p className="text-[7px] text-slate-700 font-medium mb-1">{occupation}</p> : null}
        <div className="flex justify-center flex-wrap gap-2 text-[7px] text-slate-600">
          {data.email && <span>{data.email}</span>}
          {data.email && data.phone && <span>•</span>}
          {data.phone && <span>{data.phone}</span>}
          {data.phone && data.address && <span>•</span>}
          {data.address && <span>{data.address}</span>}
        </div>
      </div>

      {/* Body */}
      <div className="pt-0 pb-3 px-3 space-y-1.5">
        {/* Summary */}
        {data.summary && (
          <Section title="Professional Summary" panelTone="secondary" panelIncludesHeader panelFullBleed>
            <p className="text-slate-700 leading-tight text-[7px]">{data.summary}</p>
          </Section>
        )}

        {/* Experience */}
        {data.experience.length > 0 && (
          <Section title="Professional Experience">
            {data.experience.map((exp) => (
              <div key={exp.id} className="mb-1 last:mb-0">
                <div className="flex justify-between items-start mb-1 gap-2">
                  <div>
                    <h4 className="font-bold text-slate-900 text-[7px]">{exp.position}</h4>
                    <p className="text-slate-700 font-medium text-[7px]">{exp.company}</p>
                  </div>
                  <span className="text-[7px] text-slate-600 font-medium whitespace-nowrap">
                    {exp.startDate} - {exp.current ? 'Present' : exp.endDate}
                  </span>
                </div>
                {exp.description && (
                  <div className="text-slate-700 leading-tight text-[7px]">
                    {exp.description.split('\n').map((line, idx) => (
                      <div key={idx}>{line}</div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </Section>
        )}

        {/* Education */}
        {data.education.length > 0 && (
          <Section title="Education">
            {data.education.map((edu) => (
              <div key={edu.id} className="mb-1.5 last:mb-0 flex justify-between items-start gap-2">
                <div>
                  <h4 className="font-bold text-slate-900 text-[7px]">{edu.degree}</h4>
                  <p className="text-slate-700 text-[7px]">{edu.institution}</p>
                </div>
                <span className="text-[7px] text-slate-600 font-medium whitespace-nowrap">
                  {edu.startDate} - {edu.endDate}
                </span>
              </div>
            ))}
          </Section>
        )}

        {/* Projects */}
        {data.projects.length > 0 && (
          <Section title="Projects">
            {data.projects.map((proj) => (
              <div key={proj.id} className="mb-1 last:mb-0">
                <div className="flex justify-between items-start mb-0.5 gap-2">
                  <h4 className="font-bold text-slate-900 text-[7px]">{proj.title}</h4>
                  {proj.link && (
                    <a
                      href={proj.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[7px] text-slate-700 underline underline-offset-2 hover:text-slate-900 whitespace-nowrap"
                    >
                      Link
                    </a>
                  )}
                </div>
                {proj.technologies && proj.technologies.length > 0 && (
                  <p className="text-[7px] text-slate-600 mb-1">{proj.technologies.join(', ')}</p>
                )}
                {proj.description && (
                  <p className="text-slate-700 leading-tight text-[7px]">{proj.description}</p>
                )}
              </div>
            ))}
          </Section>
        )}

        {/* Certifications */}
        {data.certifications && data.certifications.length > 0 && (
          <Section title="Certifications">
            <div className="space-y-1">
              {data.certifications.map((cert) => (
                <div key={cert.id} className="flex items-baseline justify-between gap-4">
                  <div className="min-w-0">
                    <div className="font-bold text-slate-900 text-[7px]">{cert.name}</div>
                    {(cert.issuer || cert.date) && (
                      <div className="text-[7px] text-slate-600">
                        {[cert.issuer, cert.date].filter(Boolean).join(' • ')}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Languages */}
        {data.languages.length > 0 && (
          <Section title="Languages">
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-slate-700 text-[7px]">
              {data.languages.map((lang) => (
                <span key={lang.id}>{lang.name} - {lang.proficiency}</span>
              ))}
            </div>
          </Section>
        )}

        {/* Skills */}
        {data.skills.length > 0 && (
          <Section title="Core Competencies">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {data.skills.map((skill, idx) => (
                <div key={idx} className="text-slate-700 font-medium text-[7px]">
                  • {skill}
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
  panelTone = 'none',
  panelIncludesHeader = false,
  panelFullBleed = false,
}: {
  title: string;
  children: React.ReactNode;
  panelTone?: 'none' | 'secondary' | 'secondary-dark';
  panelIncludesHeader?: boolean;
  panelFullBleed?: boolean;
}) {
  const panelColor = panelTone === 'secondary-dark'
    ? '#e8ebf0'
    : panelTone === 'secondary'
      ? '#f5f6f9'
      : 'transparent';

  const headerNode = (
    <h3 className="text-[7px] font-bold tracking-wider uppercase border-b-2 pb-1 mb-1.5 text-[#5c6e8c] border-[#7b8ba8]">
      {title}
    </h3>
  );

  const panelClassName = panelFullBleed
    ? '-mx-3 px-3 py-2 rounded-none'
    : 'rounded-md px-2 py-2';

  return (
    <div>
      {panelTone !== 'none' && panelIncludesHeader ? (
        <div className={panelClassName} style={{ backgroundColor: panelColor }}>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-[7px] font-bold tracking-wider uppercase whitespace-nowrap text-[#5c6e8c]">
              {title}
            </h3>
            <div className="h-px flex-1 bg-[#7b8ba8]" />
          </div>
          {children}
        </div>
      ) : (
        <>
          {headerNode}
          {panelTone === 'none' ? (
            children
          ) : (
            <div className={panelClassName} style={{ backgroundColor: panelColor }}>
              {children}
            </div>
          )}
        </>
      )}
    </div>
  );
}
