import React from 'react';
import { Play, X, CheckCircle, Clock } from 'lucide-react';

interface BottomActionBarProps {
  hasSchedule: boolean;
  rosterCount: number;
  hasOutput: boolean;
  classCount: number;
  isGenerating: boolean;
  progressPercent: number;
  progressMessage: string;
  onGenerate: () => void;
  onCancel: () => void;
}

export const BottomActionBar: React.FC<BottomActionBarProps> = ({
  hasSchedule,
  rosterCount,
  hasOutput,
  classCount,
  isGenerating,
  progressPercent,
  progressMessage,
  onGenerate,
  onCancel,
}) => {
  const isReady = hasSchedule && rosterCount > 0 && classCount > 0 && hasOutput;

  let hintText = 'Drop or browse your master schedule (.xls / .xlsx) to begin';
  if (!hasSchedule) {
    hintText = 'Select master schedule spreadsheet to parse assigned classes';
  } else if (rosterCount === 0) {
    hintText = 'Upload class rosters (.xlsx / .csv) to pair with schedules';
  } else if (!hasOutput) {
    hintText = 'Confirm output destination directory for generated forms';
  } else if (isGenerating) {
    hintText = progressMessage || 'Generating document packages...';
  } else {
    hintText = `Ready to compile packages for ${classCount} assigned classes`;
  }

  return (
    <div className="bottom-action-bar" id="bottomActionBar">
      <div className="bottom-action-content">
        <div className="action-status-block">
          <div className="action-pills-row">
            <span className={`summary-pill ${hasSchedule ? 'ready' : ''}`} id="actionPillSchedule">
              <span className="pill-dot" />
              {hasSchedule ? 'Schedule Loaded' : 'No Schedule'}
            </span>

            <span className={`summary-pill ${rosterCount > 0 ? 'ready' : ''}`} id="actionPillRosters">
              <span className="pill-dot" />
              {rosterCount} Roster{rosterCount !== 1 ? 's' : ''}
            </span>

            <span className={`summary-pill ${hasOutput ? 'ready' : ''}`} id="actionPillOutput">
              <span className="pill-dot" />
              {hasOutput ? 'Output Ready' : 'Output Not Set'}
            </span>

            {classCount > 0 && (
              <span className="summary-pill ready">
                <span className="pill-dot" />
                ~{classCount * 9} Estimated Files
              </span>
            )}
          </div>

          <div className="action-bar-hint" id="actionBarHint">
            {hintText}
          </div>
        </div>

        <div className="action-bar-controls">
          {isGenerating ? (
            <button
              id="btnDockCancel"
              className="btn-cancel-gen"
              type="button"
              onClick={onCancel}
              style={{ padding: '8px 16px', fontSize: '13px' }}
            >
              <X className="w-4 h-4" />
              Cancel Generation
            </button>
          ) : (
            <button
              id="btnDockProcess"
              className={`btn-dock-action ${isReady ? 'ready-pulse' : ''}`}
              type="button"
              disabled={!isReady || isGenerating}
              onClick={onGenerate}
            >
              <Play className="w-4 h-4 fill-current" />
              <span id="btnDockProcessLabel">Initialize Workflow</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
