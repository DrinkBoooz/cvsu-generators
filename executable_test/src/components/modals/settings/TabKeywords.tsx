import React, { useState } from 'react';
import { Plus, X, Tag } from 'lucide-react';
import { ParserConfig } from '../../../types/api';

interface TabKeywordsProps {
  config: ParserConfig;
  onChange: (updated: ParserConfig) => void;
}

export const TabKeywords: React.FC<TabKeywordsProps> = ({ config, onChange }) => {
  const [newNameToken, setNewNameToken] = useState('');
  const [newIdToken, setNewIdToken] = useState('');

  const nameTokens = config.roster_keywords?.name_tokens || [];
  const idTokens = config.roster_keywords?.id_tokens || [];

  const handleAddNameToken = () => {
    if (!newNameToken.trim()) return;
    const clean = newNameToken.toLowerCase().trim();
    if (!nameTokens.includes(clean)) {
      onChange({
        ...config,
        roster_keywords: {
          ...config.roster_keywords,
          name_tokens: [...nameTokens, clean],
        },
      });
    }
    setNewNameToken('');
  };

  const handleRemoveNameToken = (token: string) => {
    onChange({
      ...config,
      roster_keywords: {
        ...config.roster_keywords,
        name_tokens: nameTokens.filter(t => t !== token),
      },
    });
  };

  const handleAddIdToken = () => {
    if (!newIdToken.trim()) return;
    const clean = newIdToken.toLowerCase().trim();
    if (!idTokens.includes(clean)) {
      onChange({
        ...config,
        roster_keywords: {
          ...config.roster_keywords,
          id_tokens: [...idTokens, clean],
        },
      });
    }
    setNewIdToken('');
  };

  const handleRemoveIdToken = (token: string) => {
    onChange({
      ...config,
      roster_keywords: {
        ...config.roster_keywords,
        id_tokens: idTokens.filter(t => t !== token),
      },
    });
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <p className="text-xs text-[var(--text-muted)]">
        Keywords used by the roster parser to automatically discover student name and student number columns.
      </p>

      {/* Name Column Tokens */}
      <div className="space-y-2">
        <label className="text-xs font-bold text-[var(--text-primary)] flex items-center space-x-1.5">
          <Tag className="w-3.5 h-3.5 text-emerald-500" />
          <span>Student Name Column Keywords</span>
        </label>
        <div className="flex items-center space-x-2">
          <input
            type="text"
            placeholder="Add name token (e.g. learner name)..."
            value={newNameToken}
            onChange={(e) => setNewNameToken(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddNameToken()}
            className="flex-1 px-3.5 py-1.5 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={handleAddNameToken}
            className="px-3.5 py-1.5 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition-colors shrink-0"
          >
            Add
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5 p-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-elevated)]">
          {nameTokens.map((tok) => (
            <span
              key={tok}
              className="flex items-center space-x-1 px-2.5 py-1 rounded-md bg-[var(--surface-subtle)] text-[11px] font-medium text-[var(--text-primary)]"
            >
              <span>{tok}</span>
              <button
                onClick={() => handleRemoveNameToken(tok)}
                className="text-[var(--text-muted)] hover:text-red-500"
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      </div>

      {/* ID Column Tokens */}
      <div className="space-y-2">
        <label className="text-xs font-bold text-[var(--text-primary)] flex items-center space-x-1.5">
          <Tag className="w-3.5 h-3.5 text-emerald-500" />
          <span>Student ID / Number Column Keywords</span>
        </label>
        <div className="flex items-center space-x-2">
          <input
            type="text"
            placeholder="Add ID token (e.g. matricula)..."
            value={newIdToken}
            onChange={(e) => setNewIdToken(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddIdToken()}
            className="flex-1 px-3.5 py-1.5 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500"
          />
          <button
            onClick={handleAddIdToken}
            className="px-3.5 py-1.5 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 transition-colors shrink-0"
          >
            Add
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5 p-3 rounded-xl border border-[var(--border-subtle)] bg-[var(--surface-elevated)]">
          {idTokens.map((tok) => (
            <span
              key={tok}
              className="flex items-center space-x-1 px-2.5 py-1 rounded-md bg-[var(--surface-subtle)] text-[11px] font-medium text-[var(--text-primary)]"
            >
              <span>{tok}</span>
              <button
                onClick={() => handleRemoveIdToken(tok)}
                className="text-[var(--text-muted)] hover:text-red-500"
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
