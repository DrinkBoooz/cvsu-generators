import React from 'react';

export interface ProgressBarProps {
  percent: number;
  statusText?: string;
  currentStep?: number;
  totalSteps?: number;
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  percent,
  statusText,
  currentStep = 0,
  totalSteps = 0,
  className = '',
}) => {
  const boundedPct = Math.max(0, Math.min(100, Math.round(percent)));

  return (
    <div className={`hig-progress-wrapper ${className}`.trim()}>
      <div className="hig-progress-track">
        <div
          id="progressFill"
          className="hig-progress-fill"
          style={{ width: `${boundedPct}%` }}
        />
      </div>
      <div className="hig-progress-meta">
        <div className="hig-progress-status">
          <div className="hig-pulse-dot" />
          <span id="progressTaskLabel" className="hig-progress-task-text">
            {statusText || 'Processing documents...'}
          </span>
          {totalSteps > 0 && (
            <span className="hig-progress-steps">
              ({currentStep}/{totalSteps})
            </span>
          )}
        </div>
        <div id="progressPercent" className="hig-progress-percent">
          {boundedPct}%
        </div>
      </div>
    </div>
  );
};
