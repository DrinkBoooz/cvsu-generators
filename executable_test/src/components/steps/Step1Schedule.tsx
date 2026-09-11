import React, { useState, useRef } from 'react';
import { Calendar, UploadCloud, FileSpreadsheet, CheckCircle, X } from 'lucide-react';
import { ScheduleMetadata } from '../../types/api';

interface Step1ScheduleProps {
  schedulePath: string;
  metadata: ScheduleMetadata | null;
  onBrowse: () => void;
  onDropFile: (file: File) => void;
  onClear: () => void;
}

export const Step1Schedule: React.FC<Step1ScheduleProps> = ({
  schedulePath,
  metadata,
  onBrowse,
  onDropFile,
  onClear,
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
      onDropFile(e.dataTransfer.files[0]);
    }
  };

  const fileName = schedulePath ? schedulePath.split(/[\/\\]/).pop() : '';

  return (
    <section className="glass-card p-6 mb-6 animate-fade-in" id="cardStep1">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold text-sm">
            1
          </div>
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)]">
              Instructor Master Schedule
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              Ingest your raw timetable spreadsheet (.xls or .xlsx)
            </p>
          </div>
        </div>

        {schedulePath && (
          <button
            onClick={onClear}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
            title="Clear Schedule"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Dropzone / Loaded State */}
      {!schedulePath ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={onBrowse}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200 ${
            isDragOver
              ? 'border-emerald-500 bg-emerald-500/5 scale-[1.01]'
              : 'border-[var(--border-subtle)] hover:border-emerald-500/50 hover:bg-[var(--surface-subtle)]'
          }`}
        >
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
            <UploadCloud className="w-6 h-6" />
          </div>
          <p className="text-sm font-semibold text-[var(--text-primary)]">
            Drop master schedule here, or{' '}
            <span className="text-emerald-600 dark:text-emerald-400 underline">Browse File</span>
          </p>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Supports official CvSU portal format (.xls, .xlsx)
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".xls,.xlsx"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && onDropFile(e.target.files[0])}
          />
        </div>
      ) : (
        <div className="space-y-4">
          {/* File Selected Badge */}
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
            <div className="flex items-center space-x-3 overflow-hidden">
              <FileSpreadsheet className="w-5 h-5 text-emerald-500 shrink-0" />
              <div className="truncate">
                <p className="text-sm font-semibold text-[var(--text-primary)] truncate">
                  {fileName}
                </p>
                <p className="text-[11px] text-[var(--text-muted)] truncate">{schedulePath}</p>
              </div>
            </div>
            <span className="shrink-0 flex items-center space-x-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full">
              <CheckCircle className="w-3.5 h-3.5" />
              <span>Loaded</span>
            </span>
          </div>

          {/* Extracted Metadata Grid */}
          {metadata && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)]">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block">
                  Instructor
                </span>
                <span className="text-xs font-semibold text-[var(--text-primary)] truncate block mt-0.5">
                  {metadata.instructor || 'Unknown'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)]">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block">
                  Semester & AY
                </span>
                <span className="text-xs font-semibold text-[var(--text-primary)] truncate block mt-0.5">
                  {metadata.semester_ay || 'Unknown'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)]">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block">
                  Detected Classes
                </span>
                <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 truncate block mt-0.5">
                  {metadata.classes?.length || 0} Assigned Sections
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
};
