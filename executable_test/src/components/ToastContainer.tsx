import React from 'react';
import { CheckCircle2, AlertTriangle, AlertCircle, Info, X } from 'lucide-react';
import { ToastMessage } from '../types/api';

interface ToastContainerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col space-y-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => {
        const isSuccess = toast.type === 'success';
        const isWarning = toast.type === 'warning';
        const isError = toast.type === 'error';

        const Icon = isSuccess
          ? CheckCircle2
          : isWarning
          ? AlertTriangle
          : isError
          ? AlertCircle
          : Info;

        const borderClass = isSuccess
          ? 'border-emerald-500/40 bg-emerald-500/10'
          : isWarning
          ? 'border-amber-500/40 bg-amber-500/10'
          : isError
          ? 'border-red-500/40 bg-red-500/10'
          : 'border-blue-500/40 bg-blue-500/10';

        const iconClass = isSuccess
          ? 'text-emerald-500'
          : isWarning
          ? 'text-amber-500'
          : isError
          ? 'text-red-500'
          : 'text-blue-500';

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto p-4 rounded-xl shadow-xl backdrop-blur-md border ${borderClass} bg-[var(--surface-elevated)] flex items-start space-x-3 animate-fade-in`}
          >
            <Icon className={`w-5 h-5 ${iconClass} shrink-0 mt-0.5`} />
            <div className="flex-1 min-w-0">
              <h5 className="text-xs font-bold text-[var(--text-primary)]">{toast.title}</h5>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5 break-words">{toast.message}</p>
            </div>
            <button
              onClick={() => onDismiss(toast.id)}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-0.5"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
};
