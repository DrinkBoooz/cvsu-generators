import React from 'react';
import { UserCheck, Landmark, Calendar } from 'lucide-react';
import { ParserConfig } from '../../../types/api';

interface TabDefaultsProps {
  config: ParserConfig;
  onChange: (updated: ParserConfig) => void;
}

export const TabDefaults: React.FC<TabDefaultsProps> = ({ config, onChange }) => {
  const schedCfg = config.schedule_config || {
    fallback_instructor: '',
    fallback_college: '',
    fallback_semester: '',
  };

  const handleFieldChange = (field: keyof typeof schedCfg, value: string) => {
    onChange({
      ...config,
      schedule_config: {
        ...schedCfg,
        [field]: value,
      },
    });
  };

  return (
    <div className="space-y-4 animate-fade-in">
      <p className="text-xs text-[var(--text-muted)]">
        Fallback metadata applied when an ingested schedule does not explicitly specify instructor, college, or semester.
      </p>

      <div className="space-y-3">
        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1 flex items-center space-x-1.5">
            <UserCheck className="w-3.5 h-3.5 text-emerald-500" />
            <span>Fallback Instructor Name</span>
          </label>
          <input
            type="text"
            value={schedCfg.fallback_instructor}
            onChange={(e) => handleFieldChange('fallback_instructor', e.target.value)}
            placeholder="e.g. DAN JOSEPH A. ORTEGA"
            className="w-full px-3.5 py-2 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 uppercase font-medium"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1 flex items-center space-x-1.5">
            <Landmark className="w-3.5 h-3.5 text-emerald-500" />
            <span>Fallback College Name</span>
          </label>
          <input
            type="text"
            value={schedCfg.fallback_college}
            onChange={(e) => handleFieldChange('fallback_college', e.target.value)}
            placeholder="e.g. COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY"
            className="w-full px-3.5 py-2 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 uppercase font-medium"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1 flex items-center space-x-1.5">
            <Calendar className="w-3.5 h-3.5 text-emerald-500" />
            <span>Fallback Semester & Academic Year</span>
          </label>
          <input
            type="text"
            value={schedCfg.fallback_semester}
            onChange={(e) => handleFieldChange('fallback_semester', e.target.value)}
            placeholder="e.g. First Semester, A.Y. 2026-2027"
            className="w-full px-3.5 py-2 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 font-medium"
          />
        </div>
      </div>
    </div>
  );
};
