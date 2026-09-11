import React from 'react';
import { CalendarRange, Info } from 'lucide-react';

interface Step4DateBoundariesProps {
  startDate: string;
  endDate: string;
  onStartDateChange: (val: string) => void;
  onEndDateChange: (val: string) => void;
}

export const Step4DateBoundaries: React.FC<Step4DateBoundariesProps> = ({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
}) => {
  return (
    <section className="glass-card p-6 mb-6 animate-fade-in" id="cardStep4">
      <div className="flex items-center space-x-3 mb-4">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold text-sm">
          4
        </div>
        <div>
          <h2 className="text-base font-bold text-[var(--text-primary)]">
            Semester Date Boundaries (Optional)
          </h2>
          <p className="text-xs text-[var(--text-muted)]">
            Restrict attendance sheet meeting columns to specific dates
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
            Start Date
          </label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="w-full px-3.5 py-2 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
            End Date
          </label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            className="w-full px-3.5 py-2 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-emerald-500 transition-colors"
          />
        </div>
      </div>

      <div className="mt-3 flex items-start space-x-2 text-[11px] text-[var(--text-muted)] p-2.5 rounded-lg bg-[var(--surface-subtle)]">
        <Info className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
        <span>
          Leave empty to generate for standard university academic calendar (August–December for 1st Semester; January–May for 2nd Semester).
        </span>
      </div>
    </section>
  );
};
