import React from 'react';
import { X, BookOpen, AlertCircle, FileSpreadsheet, CheckCircle } from 'lucide-react';

interface HelpDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HelpDrawer: React.FC<HelpDrawerProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-[var(--modal-overlay)] backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-md h-full bg-[var(--surface-elevated)] border-l border-[var(--border-subtle)] shadow-2xl flex flex-col overflow-hidden animate-slide-in-right">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[var(--border-subtle)]">
          <div className="flex items-center space-x-2">
            <BookOpen className="w-5 h-5 text-emerald-500" />
            <h3 className="text-base font-bold text-[var(--text-primary)]">
              Operational Guidelines
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6 text-xs text-[var(--text-secondary)]">
          {/* Section 1: Schedule Ingestion */}
          <div>
            <h4 className="font-bold text-[var(--text-primary)] text-sm mb-1">
              1. Master Schedule File
            </h4>
            <p>
              Download your official timetable spreadsheet from the faculty portal (.xls or .xlsx). The generator parses instructor name, college title, semester/AY, and timetable coordinates.
            </p>
            <p className="mt-1 text-[var(--text-muted)]">
              <em>Note:</em> Any timeslots labeled <code>Async</code> or <code>Asynch</code> are filtered out so only physical meetings appear on attendance sheets.
            </p>
          </div>

          {/* Section 2: Student Rosters */}
          <div>
            <h4 className="font-bold text-[var(--text-primary)] text-sm mb-1">
              2. Student Roster Requirements
            </h4>
            <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-800 dark:text-amber-300 space-y-2">
              <div className="flex items-center space-x-2 font-bold text-xs">
                <AlertCircle className="w-4 h-4 shrink-0 text-amber-500" />
                <span>Crucial File Naming Schema:</span>
              </div>
              <code className="block p-2 rounded bg-black/5 dark:bg-black/20 text-[11px] font-mono break-all">
                &#123;Course/Sec&#125; List of Students for &#123;ScheduleCode&#125;-&#123;Subject&#125;.xlsx
              </code>
              <p className="text-[11px]">
                Example: <code>BSCS1-4 List of Students for 202612040-DCIT 21A...xlsx</code>
              </p>
            </div>
            <p className="mt-2 text-[var(--text-muted)]">
              The roster parser requires <strong>Name</strong> and <strong>Student number</strong> columns. Extra portal columns are stripped automatically.
            </p>
          </div>

          {/* Section 3: Generated Output Categories */}
          <div>
            <h4 className="font-bold text-[var(--text-primary)] text-sm mb-2">
              3. Categorized Document Output Tree
            </h4>
            <div className="p-3 rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)] font-mono text-[11px] text-[var(--text-primary)] space-y-1">
              <p>&lt;Target Output Folder&gt;/</p>
              <p className="pl-3">└── BSCS 1-4/</p>
              <p className="pl-6 text-emerald-600 dark:text-emerald-400">├── Attendance/ (Monthly sheets)</p>
              <p className="pl-6 text-emerald-600 dark:text-emerald-400">├── CEIT_Forms/ (7 academic forms)</p>
              <p className="pl-6 text-emerald-600 dark:text-emerald-400">└── BSCS1-4_202612040_GRADING_SHEET.xlsx</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
