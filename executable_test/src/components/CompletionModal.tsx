import React from 'react';
import { CheckCircle2, FolderOpen, X } from 'lucide-react';
import { GenerationSummary } from '../types/api';

interface CompletionModalProps {
  summary: GenerationSummary | null;
  onClose: () => void;
}

export const CompletionModal: React.FC<CompletionModalProps> = ({ summary, onClose }) => {
  if (!summary) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--modal-overlay)] backdrop-blur-sm animate-fade-in">
      <div className="glass-card w-full max-w-md p-6 bg-[var(--surface-elevated)] shadow-2xl border border-emerald-500/40 text-center space-y-4">
        <div className="w-14 h-14 mx-auto rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <CheckCircle2 className="w-8 h-8" />
        </div>

        <div>
          <h3 className="text-lg font-bold text-[var(--text-primary)]">
            Generation Complete!
          </h3>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Successfully processed {summary.sections_processed} class section{summary.sections_processed > 1 ? 's' : ''} and generated {summary.total_documents} academic documents.
          </p>
        </div>

        <div className="p-3 rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)] text-left">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block">
            Target Output Folder
          </span>
          <p className="text-xs font-mono text-[var(--text-primary)] truncate mt-0.5" title={summary.output_directory}>
            {summary.output_directory}
          </p>
        </div>

        <div className="flex items-center space-x-2 pt-2">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 px-4 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-500/20 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
