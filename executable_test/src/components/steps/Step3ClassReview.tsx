import React from 'react';
import { CheckCircle2, AlertCircle, Layers, SlidersHorizontal } from 'lucide-react';
import { ClassValidation, RosterConfigMap } from '../../types/api';

interface Step3ClassReviewProps {
  validations: ClassValidation[];
  classConfigs: RosterConfigMap;
  onToggleLab: (key: string, hasLab: boolean) => void;
  onOpenMappingModal: () => void;
}

export const Step3ClassReview: React.FC<Step3ClassReviewProps> = ({
  validations,
  classConfigs,
  onToggleLab,
  onOpenMappingModal,
}) => {
  if (validations.length === 0) return null;

  return (
    <section className="glass-card p-6 mb-6 animate-fade-in" id="cardStep3">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold text-sm">
            3
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              Class Review & Subject Types
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Confirm lecture vs. laboratory grade sheets and smart roster pairing
            </p>
          </div>
        </div>

        <button
          onClick={onOpenMappingModal}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[var(--surface-subtle)] border border-[var(--border-subtle)] hover:border-emerald-500/50 text-[var(--text-primary)] transition-colors"
          id="btnOpenMappingModal"
        >
          <SlidersHorizontal className="w-3.5 h-3.5 text-emerald-500" />
          <span>Manual Section Mapping</span>
        </button>
      </div>

      {/* Classes Table */}
      <div className="overflow-x-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-elevated)]">
        <table className="settings-data-table text-left text-xs">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              <th className="py-3 px-4">Section</th>
              <th className="py-3 px-4">Code</th>
              <th className="py-3 px-4">Subject Title</th>
              <th className="py-3 px-4">Paired Roster</th>
              <th className="py-3 px-4 text-center">Grading Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-subtle)] text-[var(--text-primary)]">
            {validations.map((v, idx) => {
              const key = `${v.course_section}_${v.schedule_code}`;
              const hasLab = classConfigs[key]?.has_lab ?? v.has_lab;
              const isPaired = v.status === 'paired';

              return (
                <tr key={idx} className="hover:bg-[var(--surface-subtle)] transition-colors">
                  <td className="py-3 px-4 font-bold">{v.course_section}</td>
                  <td className="py-3 px-4 font-mono text-[var(--text-muted)]">{v.schedule_code}</td>
                  <td className="py-3 px-4 truncate max-w-[200px]" title={v.subject}>
                    {v.subject}
                  </td>
                  <td className="py-3 px-4">
                    {isPaired ? (
                      <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>{v.student_count} Students</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                        <AlertCircle className="w-3 h-3" />
                        <span>Missing Roster</span>
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-center">
                    <div className="inline-flex items-center rounded-lg p-0.5 bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
                      <button
                        onClick={() => onToggleLab(key, false)}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all ${
                          !hasLab
                            ? 'bg-[var(--surface-elevated)] text-emerald-600 dark:text-emerald-400 shadow-sm'
                            : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                        }`}
                      >
                        Lecture
                      </button>
                      <button
                        onClick={() => onToggleLab(key, true)}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all ${
                          hasLab
                            ? 'bg-[var(--surface-elevated)] text-emerald-600 dark:text-emerald-400 shadow-sm'
                            : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                        }`}
                      >
                        Lec & Lab
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
};
