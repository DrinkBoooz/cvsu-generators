import React from 'react';
import { Folder, FolderOpen, CheckCircle } from 'lucide-react';

interface Step5OutputFolderProps {
  outputDir: string;
  onBrowse: () => void;
}

export const Step5OutputFolder: React.FC<Step5OutputFolderProps> = ({ outputDir, onBrowse }) => {
  return (
    <section className="glass-card p-6 mb-6 animate-fade-in" id="cardStep5">
      <div className="flex items-center space-x-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold text-sm">
          5
        </div>
        <div>
          <h2 className="text-base font-bold text-[var(--text-primary)]">
            Target Destination Folder
          </h2>
          <p className="text-xs text-[var(--text-muted)]">
            Designate where categorized student forms and grade sheets will be saved
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center space-y-2 sm:space-y-0 sm:space-x-3">
        <div className="flex-1 flex items-center space-x-3 px-3.5 py-2.5 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] overflow-hidden">
          <Folder className="w-4 h-4 text-emerald-500 shrink-0" />
          <span
            className="text-xs font-mono text-[var(--text-primary)] truncate"
            title={outputDir || 'No destination selected'}
          >
            {outputDir || 'Please select an output folder...'}
          </span>
        </div>

        <button
          onClick={onBrowse}
          className="flex items-center justify-center space-x-2 px-4 py-2.5 rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)] hover:border-emerald-500/50 text-xs font-semibold text-[var(--text-primary)] transition-colors shrink-0"
          id="btnBrowseOutput"
        >
          <FolderOpen className="w-4 h-4 text-emerald-500" />
          <span>Browse Path</span>
        </button>
      </div>
    </section>
  );
};
