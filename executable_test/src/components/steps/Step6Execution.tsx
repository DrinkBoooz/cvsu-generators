import React from 'react';
import { Play, X } from 'lucide-react';
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
    <section className="glass-card execution-card" id="cardStep6" style={{ marginTop: '20px' }}>
      <div className="step-header">
        <div className="step-number">6</div>
        <div className="step-header-text">
          <div className="step-title">Initialize Workflow</div>
          <div className="step-sub">Automated document compilation &amp; verification</div>
        </div>
        <div className="step-desc">Automated Generation</div>
      </div>

      <p className="step-instructions">
        Click the green <strong>"Initialize Workflow"</strong> button. Processing typically takes only a few seconds!
      </p>

      {/* Primary Generation Button */}
      {!isGenerating && (
        <button
          id="processBtn"
          className="btn-primary-action"
          type="button"
          disabled={!canGenerate}
          onClick={onStart}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          <span id="processBtnLabel">
            {estimate ? `Initialize Workflow (~${estimate.total_files} files)` : 'Initialize Workflow'}
          </span>
        </button>
      )}

      {/* Progress Telemetry */}
      {isGenerating && (
        <div id="progressContainer" className="progress-container" style={{ marginTop: '16px' }}>
          <div className="progress-track">
            <div
              id="progressFill"
              className="progress-fill"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="progress-meta">
            <div className="progress-task">
              <div className="pulse-dot" />
              <span id="progressTaskLabel">
                {progressStatus || 'Generating document packages...'}
              </span>
              {totalSteps > 0 && (
                <span className="progress-stopwatch" style={{ marginLeft: '6px' }}>
                  ({currentStep}/{totalSteps})
                </span>
              )}
            </div>
            <div id="progressPercent" style={{ color: 'var(--accent-emerald)', fontWeight: 700 }}>
              {progressPercent}%
            </div>
          </div>
          <div style={{ textAlign: 'center', marginTop: '12px' }}>
            <button
              className="btn-cancel-gen"
              id="btnCancelGeneration"
              type="button"
              onClick={onCancel}
            >
              <X className="w-3.5 h-3.5" />
              Cancel Generation
            </button>
          </div>
        </div>
      )}
    </section>
  );
};
