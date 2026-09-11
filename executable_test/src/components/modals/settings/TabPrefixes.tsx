import React, { useState } from 'react';
import { Plus, Trash2, Search } from 'lucide-react';
import { ParserConfig, PrefixMetadata } from '../../../types/api';

interface TabPrefixesProps {
  config: ParserConfig;
  onChange: (updated: ParserConfig) => void;
}

export const TabPrefixes: React.FC<TabPrefixesProps> = ({ config, onChange }) => {
  const [search, setSearch] = useState('');
  const [newPrefix, setNewPrefix] = useState('');
  const [newName, setNewName] = useState('');
  const [newDept, setNewDept] = useState('');
  const [newDeptCode, setNewDeptCode] = useState('');
  const [newIcon, setNewIcon] = useState('📚');

  const prefixes = Object.entries(config.ceit_prefix_map || {});

  const handleAdd = () => {
    if (!newPrefix.trim() || !newDeptCode.trim()) return;
    const cleanPrefix = newPrefix.toUpperCase().trim();
    const updatedMap = {
      ...config.ceit_prefix_map,
      [cleanPrefix]: {
        name: newName.trim() || cleanPrefix,
        dept: newDept.trim() || `Department of ${newDeptCode.trim()}`,
        dept_code: newDeptCode.toUpperCase().trim(),
        icon: newIcon.trim() || '📚',
        badge: `${newIcon.trim() || '📚'} ${newDeptCode.toUpperCase().trim()}`,
      },
    };
    onChange({ ...config, ceit_prefix_map: updatedMap });
    setNewPrefix('');
    setNewName('');
    setNewDept('');
    setNewDeptCode('');
  };

  const handleDelete = (prefixKey: string) => {
    const updatedMap = { ...config.ceit_prefix_map };
    delete updatedMap[prefixKey];
    onChange({ ...config, ceit_prefix_map: updatedMap });
  };

  const filtered = prefixes.filter(([k, v]) =>
    k.toLowerCase().includes(search.toLowerCase()) ||
    v.name.toLowerCase().includes(search.toLowerCase()) ||
    v.dept_code.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Search & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="Search prefixes or departments..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3.5 py-2 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>
        <span className="text-xs font-semibold text-[var(--text-muted)]">
          {prefixes.length} Prefixes Registered
        </span>
      </div>

      {/* Add New Prefix Row */}
      <div className="p-3.5 rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)] grid grid-cols-2 sm:grid-cols-6 gap-2 items-center">
        <input
          type="text"
          placeholder="Icon (e.g. 💻)"
          value={newIcon}
          onChange={(e) => setNewIcon(e.target.value)}
          className="px-2 py-1.5 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-center text-[var(--text-primary)]"
        />
        <input
          type="text"
          placeholder="Prefix (COSC)"
          value={newPrefix}
          onChange={(e) => setNewPrefix(e.target.value)}
          className="px-2 py-1.5 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs font-bold uppercase text-[var(--text-primary)]"
        />
        <input
          type="text"
          placeholder="Name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="px-2 py-1.5 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] sm:col-span-2"
        />
        <input
          type="text"
          placeholder="Dept Code (DIT)"
          value={newDeptCode}
          onChange={(e) => setNewDeptCode(e.target.value)}
          className="px-2 py-1.5 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs font-bold uppercase text-[var(--text-primary)]"
        />
        <button
          onClick={handleAdd}
          className="flex items-center justify-center space-x-1 py-1.5 px-3 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add</span>
        </button>
      </div>

      {/* Data Table */}
      <div className="max-h-[350px] overflow-y-auto rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-elevated)]">
        <table className="settings-data-table text-left text-xs">
          <thead>
            <tr className="border-b border-[var(--border-subtle)] text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
              <th className="py-2.5 px-3">Prefix</th>
              <th className="py-2.5 px-3">Subject Name</th>
              <th className="py-2.5 px-3">Department</th>
              <th className="py-2.5 px-3 text-center">Badge</th>
              <th className="py-2.5 px-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-subtle)] text-[var(--text-primary)]">
            {filtered.map(([prefix, meta]) => (
              <tr key={prefix} className="hover:bg-[var(--surface-subtle)] transition-colors">
                <td className="py-2 px-3 font-bold font-mono">{prefix}</td>
                <td className="py-2 px-3 truncate max-w-[150px]">{meta.name}</td>
                <td className="py-2 px-3 text-[var(--text-muted)] truncate max-w-[180px]">
                  {meta.dept}
                </td>
                <td className="py-2 px-3 text-center">
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
                    {meta.badge || `${meta.icon} ${meta.dept_code}`}
                  </span>
                </td>
                <td className="py-2 px-3 text-right">
                  <button
                    onClick={() => handleDelete(prefix)}
                    className="p-1 rounded text-[var(--text-muted)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
                    title="Delete Prefix"
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
