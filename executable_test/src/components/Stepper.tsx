import React from 'react';
import { Calendar, Users, CheckCircle2, Rocket } from 'lucide-react';

interface StepperProps {
  currentStep: number;
}

export const Stepper: React.FC<StepperProps> = ({ currentStep }) => {
  const steps = [
    { id: 1, label: 'Schedule', desc: 'Ingest .xls / .xlsx', icon: Calendar },
    { id: 2, label: 'Rosters', desc: 'Add Class Rosters', icon: Users },
    { id: 3, label: 'Review', desc: 'Subject Types & Map', icon: CheckCircle2 },
    { id: 4, label: 'Generate', desc: 'Dispatch Pipeline', icon: Rocket },
  ];

  return (
    <div className="w-full py-6 px-4 sm:px-6">
      <div className="max-w-4xl mx-auto flex items-center justify-between relative">
        {/* Background Line */}
        <div className="absolute top-1/2 left-0 right-0 h-0.5 -translate-y-1/2 bg-[var(--border-subtle)] z-0" />

        {steps.map((step) => {
          const Icon = step.icon;
          const isDone = currentStep > step.id;
          const isActive = currentStep === step.id;

          return (
            <div key={step.id} className="relative z-10 flex flex-col items-center group">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-300 ${
                  isDone
                    ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/25'
                    : isActive
                    ? 'bg-gradient-to-tr from-emerald-600 to-emerald-400 text-white ring-4 ring-emerald-500/20 shadow-lg shadow-emerald-500/30'
                    : 'bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-[var(--text-muted)]'
                }`}
              >
                <Icon className="w-5 h-5" />
              </div>
              <div className="mt-2 text-center">
                <span
                  className={`text-xs font-semibold block ${
                    isActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-[var(--text-primary)]'
                  }`}
                >
                  {step.label}
                </span>
                <span className="text-[10px] text-[var(--text-muted)] hidden sm:block">
                  {step.desc}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
