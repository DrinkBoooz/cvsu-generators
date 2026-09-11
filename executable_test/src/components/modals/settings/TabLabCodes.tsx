import React, { useState } from 'react';
import { Plus, X, FlaskConical } from 'lucide-react';
import { ParserConfig } from '../../../types/api';

interface TabLabCodesProps {
  config: ParserConfig;
  onChange: (updated: ParserConfig) => void;
}

export const TabLabCodes: React.FC<TabLabCodesProps> = ({ config, onChange }) => {
  const [newCode, setNewCode] = useState('');
  const labCodes = config.known_lab_subjects || [];

  const handleAdd = () => {
    if (!newCode.trim()) return;
    const clean = newCode.toUpperCase().trim().replace(/[^A-Z0-9]/g, '');
    if (!labCodes.includes(clean)) {
      onChange({
        ...config,
        known_lab_subjects: [...labCodes, clean].sort(),
      });
    }
    setNewCode('');
  };

  const handleRemove = (code: string) => {
    onChange({
      ...config,
      known_lab_subjects: labCodes.filter(c => c !== code),
    });
  };

  return (
    <div className="space-y-4 animate-fade-in">
      <p className="text-xs text-[var(--text-muted)]">
        Subjects configured here automatically use <code>GRADING_LECTURE_LAB_TEMPLATE.xlsx</code> (Lecture + Lab tabs).
      </p>

      {/* Input */}
      <div className="flex items-center space-x-2">
        <input
          type="text"
          placeholder="Add subject code (e.g. COSC50, DCIT25)..."
          value={newCode}
          onChange={(e) => setNewCode(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          className="flex-1 px-3.5 py-2 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 uppercase font-mono"
        />
        <button
          onClick={handleAdd}
          className="flex items-center space-x-1 px-4 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition-colors shrink-0"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add Code</span>
        </button>
      </div>

      {/* Chips */}
      <div className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-elevated)] max-h-[350px] overflow-y-auto">
        <div className="flex flex-wrap gap-2">
          {labCodes.map((code) => (
            <span
              key={code}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[var(--surface-subtle)] border border-[var(--border-subtle)] text-xs font-mono font-bold text-[var(--text-primary)] group hover:border-emerald-500/40 transition-colors"
            >
              <FlaskConical className="w-3.5 h-3.5 text-emerald-500" />
              <span>{code}</span>
              <button
                onClick={() => handleRemove(code)}
                className="text-[var(--text-muted)] hover:text-red-500 transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};
