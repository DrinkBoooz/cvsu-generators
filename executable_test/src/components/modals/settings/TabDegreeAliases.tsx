import React, { useState } from 'react';
import { Plus, Trash2, ArrowRight } from 'lucide-react';
import { ParserConfig } from '../../../types/api';

interface TabDegreeAliasesProps {
  config: ParserConfig;
  onChange: (updated: ParserConfig) => void;
}

export const TabDegreeAliases: React.FC<TabDegreeAliasesProps> = ({ config, onChange }) => {
  const [alias, setAlias] = useState('');
  const [official, setOfficial] = useState('');

  const aliases = Object.entries(config.program_aliases || {});

  const handleAdd = () => {
    if (!alias.trim() || !official.trim()) return;
    const updated = {
      ...config.program_aliases,
      [alias.trim()]: official.trim(),
    };
    onChange({ ...config, program_aliases: updated });
    setAlias('');
    setOfficial('');
  };

  const handleDelete = (key: string) => {
    const updated = { ...config.program_aliases };
    delete updated[key];
    onChange({ ...config, program_aliases: updated });
  };

  return (
    <div className="space-y-4 animate-fade-in">
      <p className="text-xs text-[var(--text-muted)]">
        Maps informal or shortened section codes (e.g. <code>CS 1-4</code>) to their official degree names (e.g. <code>BSCS 1-4</code>).
      </p>

      {/* Add Row */}
      <div className="p-3.5 rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)] flex items-center space-x-2">
        <input
          type="text"
          placeholder="Informal Alias (e.g. CS 1-1)"
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          className="flex-1 px-3 py-1.5 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)]"
        />
        <ArrowRight className="w-4 h-4 text-[var(--text-muted)] shrink-0" />
        <input
          type="text"
          placeholder="Official Degree (e.g. BSCS 1-1)"
          value={official}
          onChange={(e) => setOfficial(e.target.value)}
          className="flex-1 px-3 py-1.5 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs font-bold text-[var(--text-primary)]"
        />
        <button
          onClick={handleAdd}
          className="flex items-center space-x-1 py-1.5 px-3 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition-colors shrink-0"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add</span>
        </button>
      </div>

      {/* Table */}
      <div className="max-h-[350px] overflow-y-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-elevated)]">
        <table className="settings-data-table text-left text-xs">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              <th className="py-2.5 px-4">Informal Section Name</th>
              <th className="py-2.5 px-4">Mapped Official Section</th>
              <th className="py-2.5 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-subtle)] text-[var(--text-primary)]">
            {aliases.map(([k, v]) => (
              <tr key={k} className="hover:bg-[var(--surface-subtle)] transition-colors">
                <td className="py-2.5 px-4 font-mono font-medium">{k}</td>
                <td className="py-2.5 px-4 font-bold text-emerald-600 dark:text-emerald-400">{v}</td>
                <td className="py-2.5 px-4 text-right">
                  <button
                    onClick={() => handleDelete(k)}
                    className="p-1 rounded text-[var(--text-muted)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
