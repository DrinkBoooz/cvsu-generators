import React, { useState } from 'react';
import { X, Check, Search, FileText } from 'lucide-react';
import { ClassValidation, RosterConfigMap } from '../../types/api';

interface RosterMappingModalProps {
  isOpen: boolean;
  onClose: () => void;
  validations: ClassValidation[];
  availableRosters: string[];
  classConfigs: RosterConfigMap;
  onSaveMapping: (updatedConfigs: RosterConfigMap) => void;
}

export const RosterMappingModal: React.FC<RosterMappingModalProps> = ({
  isOpen,
  onClose,
  validations,
  availableRosters,
  classConfigs,
  onSaveMapping,
}) => {
  if (!isOpen) return null;

  const [search, setSearch] = useState('');
  const [localConfigs, setLocalConfigs] = useState<RosterConfigMap>(() => ({ ...classConfigs }));

  const handleSelectRoster = (key: string, rosterPath: string) => {
    setLocalConfigs(prev => ({
      ...prev,
      [key]: {
        has_lab: prev[key]?.has_lab ?? false,
        manual_roster_path: rosterPath || undefined,
      },
    }));
  };

  const handleSave = () => {
    onSaveMapping(localConfigs);
    onClose();
  };

  const filteredValidations = validations.filter(v =>
    v.course_section.toLowerCase().includes(search.toLowerCase()) ||
    v.subject.toLowerCase().includes(search.toLowerCase()) ||
    v.schedule_code.includes(search)
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--modal-overlay)] backdrop-blur-sm animate-fade-in">
      <div className="glass-card w-full max-w-3xl max-h-[85vh] flex flex-col bg-[var(--surface-elevated)] shadow-2xl border border-[var(--border-subtle)] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[var(--border-subtle)]">
          <div>
            <h3 className="text-base font-bold text-[var(--text-primary)]">
              Manual Section-to-Roster Mapping
            </h3>
            <p className="text-xs text-[var(--text-muted)]">
              Explicitly pair or re-assign class sections with uploaded roster spreadsheets
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-[var(--border-subtle)] bg-[var(--surface-subtle)]">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder="Search by section, code, or subject..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3.5 py-2 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 transition-colors"
            />
          </div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="space-y-3">
            {filteredValidations.map((v, idx) => {
              const key = `${v.course_section}_${v.schedule_code}`;
              const currentRoster = localConfigs[key]?.manual_roster_path ?? v.roster_path;

              return (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)] flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-sm text-[var(--text-primary)]">
                        {v.course_section}
                      </span>
                      <span className="text-[11px] font-mono text-[var(--text-muted)] px-2 py-0.5 rounded bg-[var(--surface-elevated)] border border-[var(--border-subtle)]">
                        {v.schedule_code}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] truncate mt-1">
                      {v.subject}
                    </p>
                  </div>

                  <div className="w-full sm:w-72">
                    <select
                      value={currentRoster || ''}
                      onChange={(e) => handleSelectRoster(key, e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 truncate"
                    >
                      <option value="">-- Auto-Detect / Unpaired --</option>
                      {availableRosters.map((rPath, rIdx) => {
                        const name = rPath.split(/[\/\\]/).pop() || rPath;
                        return (
                          <option key={rIdx} value={rPath}>
                            {name}
                          </option>
                        );
                      })}
                    </select>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-3 p-4 border-t border-[var(--border-subtle)] bg-[var(--surface-subtle)]">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-elevated)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-500/20 transition-colors"
          >
            <Check className="w-4 h-4" />
            <span>Apply Mapping</span>
          </button>
        </div>
      </div>
    </div>
  );
};
