import React, { useState, useRef } from 'react';
import { Users, UploadCloud, FileText, X, Trash2 } from 'lucide-react';

interface Step2RostersProps {
  rosters: string[];
  onBrowse: () => void;
  onDropFiles: (files: FileList | File[]) => void;
  onRemoveRoster: (index: number) => void;
  onClearAll: () => void;
}

export const Step2Rosters: React.FC<Step2RostersProps> = ({
  rosters,
  onBrowse,
  onDropFiles,
  onRemoveRoster,
  onClearAll,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onDropFiles(e.dataTransfer.files);
    }
  };

  return (
    <section className="glass-card p-6 mb-6 animate-fade-in" id="cardStep2">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold text-sm">
            2
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              Student Class Rosters
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Select or drop class student lists from registrar.cvsu.edu.ph
            </p>
          </div>
        </div>

        {rosters.length > 0 && (
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full">
              {rosters.length} Roster{rosters.length > 1 ? 's' : ''} Loaded
            </span>
            <button
              onClick={onClearAll}
              className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
              title="Clear All Rosters"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Multi-file Dropzone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={onBrowse}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 ${
          isDragOver
            ? 'border-emerald-500 bg-emerald-500/5 scale-[1.01]'
            : 'border-[var(--border-subtle)] hover:border-emerald-500/50 hover:bg-[var(--surface-subtle)]'
        }`}
      >
        <div className="w-10 h-10 mx-auto mb-2 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
          <UploadCloud className="w-5 h-5" />
        </div>
        <p className="text-sm font-semibold text-[var(--text-primary)]">
          Drop multiple student lists here, or{' '}
          <span className="text-emerald-600 dark:text-emerald-400 underline">Browse Data</span>
        </p>
        <p className="text-xs text-[var(--text-muted)] mt-1">
          Supports .xlsx, .xls, and .csv lists. Multiple selection enabled.
        </p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".xlsx,.xls,.csv"
          className="hidden"
          onChange={(e) => e.target.files && onDropFiles(e.target.files)}
        />
      </div>

      {/* Roster Chips List */}
      {rosters.length > 0 && (
        <div className="mt-4 pt-4 border-t border-[var(--border-subtle)]">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-2">
            Selected Class Rosters
          </span>
          <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto p-1">
            {rosters.map((rosterPath, idx) => {
              const name = rosterPath.split(/[\/\\]/).pop() || rosterPath;
              return (
                <div
                  key={idx}
                  className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs font-medium text-[var(--text-primary)] group hover:border-emerald-500/40 transition-colors"
                >
                  <FileText className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  <span className="truncate max-w-[220px]" title={rosterPath}>
                    {name}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemoveRoster(idx);
                    }}
                    className="p-0.5 rounded text-[var(--text-muted)] hover:text-red-500 transition-colors"
                    title="Remove file"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
};
