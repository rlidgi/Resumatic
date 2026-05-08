import { ResumeData } from '../../types/resume';

interface ContemporaryTemplateProps {
  data: ResumeData;
}

export function ContemporaryTemplate({ data }: ContemporaryTemplateProps) {
  const name = `${data.firstName || 'Your'} ${data.lastName || 'Name'}`.trim();
  const initials = getInitials(name);

  return (
    <div className="w-full h-full bg-white text-black overflow-auto p-4">
      {/* Header */}
      <div className="grid grid-cols-[100px_16px_1fr] gap-x-1 items-start">
        <div />
        <div />
        <div className="flex items-start gap-2 min-w-0">
          <div className="w-8 h-8 flex-shrink-0 rounded-full border-2 border-[#6b7fa3] text-slate-700 flex items-center justify-center font-semibold text-xs">
            {initials}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-light leading-tight text-[#4a6fa5]">{name}</div>
            <div className="mt-0.5 text-[7px] text-slate-500 flex flex-wrap items-center gap-x-2 gap-y-0.5">
              {data.phone && <span>{data.phone}</span>}
              {data.phone && data.email && <span className="text-slate-300">|</span>}
              {data.email && <span>E: {data.email}</span>}
              {(data.phone || data.email) && data.address && <span className="text-slate-300">|</span>}
              {data.address && <span>{data.address}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Body with Timeline */}
      <div className="mt-4">
        <div className="relative">
          <div
            className="absolute top-0 bottom-0 w-px z-0 pointer-events-none bg-[#4a6fa5]/40"
            style={{ left: "calc(100px + 4px + 8px)" }}
          />

          <div className="space-y-4">
            {/* Summary */}
            {data.summary && (
              <TimelineSection label="SUMMARY">
                <div className="text-[7px] text-slate-600 leading-tight">
                  {data.summary.split('\n').map((line, idx) => (
                    <div key={idx}>{line}</div>
                  ))}
                </div>
              </TimelineSection>
            )}

            {/* Skills */}
            {data.skills.length > 0 && (
              <TimelineSection label="SKILLS">
                <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-[7px] text-slate-700">
                  {data.skills.slice(0, 12).map((s, idx) => (
                    <div key={idx} className="flex items-start gap-1.5">
                      <span className="mt-[4px] w-1 h-1 rounded-full bg-slate-400" />
                      <span>{s}</span>
                    </div>
                  ))}
                </div>
              </TimelineSection>
            )}

            {/* Languages */}
            {data.languages.length > 0 && (
              <TimelineSection label="LANGUAGES">
                <div className="text-[7px] text-slate-700">
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                    {data.languages.map((l) => (
                      <span key={l.id}>{l.name} - {l.proficiency}</span>
                    ))}
                  </div>
                </div>
              </TimelineSection>
            )}

            {/* Certifications */}
            {data.certifications && data.certifications.length > 0 && (
              <TimelineSection label="CERTIFICATIONS">
                <div className="space-y-1 text-[7px] text-slate-700">
                  {data.certifications.map((c) => (
                    <div key={c.id}>
                      <div className="font-semibold text-slate-800">{c.name}</div>
                      <div className="text-slate-500">
                        {[c.issuer, c.date].filter(Boolean).join(' • ')}
                      </div>
                    </div>
                  ))}
                </div>
              </TimelineSection>
            )}

            {/* Experience */}
            {data.experience.length > 0 && (
              <TimelineSection label="EXPERIENCE">
                <div className="space-y-1.5">
                  {data.experience.slice(0, 4).map((exp) => (
                    <div key={exp.id}>
                      <div className="flex items-baseline justify-between gap-2">
                        <div className="text-[7px] font-bold text-slate-800 uppercase tracking-[0.14em]">
                          {exp.position}
                        </div>
                        <div className="text-[7px] text-slate-500">
                          {exp.startDate} - {exp.current ? 'Present' : exp.endDate}
                        </div>
                      </div>
                      <div className="mt-0.5 text-[7px] text-slate-600">
                        {exp.company}{exp.location && `, ${exp.location}`}
                      </div>
                      {exp.description && (
                        <div className="mt-1 text-[7px] leading-tight text-slate-600">
                          {exp.description.split('\n').map((line, idx) => (
                            <div key={idx}>{line}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </TimelineSection>
            )}

            {/* Projects */}
            {data.projects.length > 0 && (
              <TimelineSection label="PROJECTS">
                <div className="space-y-1">
                  {data.projects.slice(0, 4).map((proj) => (
                    <div key={proj.id}>
                      <div className="flex items-baseline justify-between gap-2">
                        <div className="text-[7px] font-bold text-slate-800 uppercase tracking-[0.14em]">
                          {proj.title}
                        </div>
                        {proj.link && (
                          <a
                            href={proj.link}
                            target="_blank"
                            rel="noreferrer"
                            className="text-[7px] text-slate-500 hover:text-slate-700 underline underline-offset-2"
                          >
                            Link
                          </a>
                        )}
                      </div>
                      {proj.technologies && proj.technologies.length > 0 && (
                        <div className="mt-0.5 text-[7px] text-slate-500">{proj.technologies.join(', ')}</div>
                      )}
                      {proj.description && (
                        <div className="mt-1 text-[7px] leading-tight text-slate-600">
                          {proj.description}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </TimelineSection>
            )}

            {/* Education */}
            {data.education.length > 0 && (
              <TimelineSection label="EDUCATION">
                <div className="space-y-1">
                  {data.education.slice(0, 3).map((edu) => (
                    <div key={edu.id} className="flex items-baseline justify-between gap-2">
                      <div>
                        <div className="text-[7px] font-bold text-slate-800">{edu.degree}</div>
                        <div className="text-[7px] text-slate-600">{edu.institution}</div>
                      </div>
                      <div className="text-[7px] text-slate-500">
                        {edu.startDate} - {edu.endDate}
                      </div>
                    </div>
                  ))}
                </div>
              </TimelineSection>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function TimelineSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[100px_16px_1fr] gap-x-1">
      <div className="pt-0.5 text-[7px] font-bold tracking-[0.18em] text-[#4a6fa5] leading-tight">
        {label}
      </div>
      <div className="pt-1 flex justify-center">
        <span className="relative z-10 w-2 h-2 rounded-full bg-white border-2 border-[#6b7fa3]" />
      </div>
      <div>{children}</div>
    </div>
  );
}

function getInitials(fullName: string): string {
  const cleaned = String(fullName || "").trim().replace(/\s+/g, " ");
  if (!cleaned) return "JD";
  const parts = cleaned.split(" ").filter(Boolean);
  const first = parts[0]?.[0] || "J";
  const last = (parts.length > 1 ? parts[parts.length - 1]?.[0] : parts[0]?.[1]) || "D";
  return `${String(first).toUpperCase()}${String(last).toUpperCase()}`;
}
