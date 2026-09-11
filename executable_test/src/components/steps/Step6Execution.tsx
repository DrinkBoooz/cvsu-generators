import React from 'react';
import { Play, XCircle, FileText, CheckCircle2, Clock } from 'lucide-react';
import { FileEstimate } from '../../types/api';

interface Step6ExecutionProps {
  isGenerating: boolean;
  progressPercent: number;
  progressStatus: string;
  currentStep: number;
  totalSteps: number;
  estimate: FileEstimate | null;
  canGenerate: boolean;
  onStart: () => void;
  onCancel: () => void;
}

export const Step6Execution: React.FC<Step6ExecutionProps> = ({
  isGenerating,
  progressPercent,
  progressStatus,
  currentStep,
  totalSteps,
  estimate,
  canGenerate,
  onStart,
  onCancel,
}) => {
  return (
    <section className="glass-card p-6 mb-8 animate-fade-in" id="cardStep6">
      {/* File Estimation Header */}
      {estimate && (
        <div className="mb-6 p-4 rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] block">
                Batch Generation Scope
              </span>
              <p className="text-sm font-bold text-[var(--text-primary)]">
                Ready to generate ~{estimate.total_files} documents across {estimate.sections_count} sections
              </p>
            </div>
            <div className="flex items-center space-x-2 text-xs font-semibold text-[var(--text-secondary)]">
              <span className="px-2 py-1 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)]">
                {estimate.ceit_forms_count} Academic Forms
              </span>
              <span className="px-2 py-1 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)]">
                {estimate.attendance_sheets_count} Attendance
              </span>
              <span className="px-2 py-1 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)]">
                {estimate.grade_sheets_count} Grade Sheets
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Progress Telemetry */}
      {isGenerating && (
        <div className="mb-6 space-y-2 animate-fade-in">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-emerald-600 dark:text-emerald-400 flex items-center space-x-1.5">
              <Clock className="w-3.5 h-3.5 animate-spin" />
              <span>{progressStatus || 'Processing documents...'}</span>
            </span>
            <span className="font-mono font-bold text-[var(--text-primary)]">
              {progressPercent}% ({currentStep}/{totalSteps})
            </span>
          </div>

          <div className="w-full h-2.5 rounded-full bg-[var(--surface-subtle)] border border-[var(--border-subtle)] overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full transition-all duration-300 shadow-sm"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Primary Actions */}
      <div className="flex items-center space-x-3">
        {!isGenerating ? (
          <button
            onClick={onStart}
            disabled={!canGenerate}
            className={`flex-1 flex items-center justify-center space-x-2 py-3.5 px-6 rounded-xl font-bold text-sm text-white shadow-lg transition-all duration-200 ${
              canGenerate
                ? 'bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 shadow-emerald-500/25 cursor-pointer hover:scale-[1.008]'
                : 'bg-slate-400 dark:bg-slate-700 opacity-50 cursor-not-allowed shadow-none'
            }`}
            id="btnGenerate"
          >
            <Play className="w-4 h-4 fill-white" />
            <span>Initialize Workflow</span>
          </button>
        ) : (
          <button
            onClick={onCancel}
            className="flex-1 flex items-center justify-center space-x-2 py-3.5 px-6 rounded-xl font-bold text-sm text-red-600 dark:text-red-400 bg-red-500/10 border border-red-500/20 hover:bg-red-500/20 transition-colors"
            id="btnCancel"
          >
            <XCircle className="w-4 h-4" />
            <span>Cancel Generation</span>
          </button>
        )}
      </div>
    </section>
  );
};
