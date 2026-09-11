import React, { useState } from 'react';
import { FileText, Trash2, X } from 'lucide-react';

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
  const [stripExtraCols, setStripExtraCols] = useState(true);

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
    <section className="glass-card" id="cardStep2">
      <div className="step-header">
        <div className="step-number">2</div>
        <div className="step-header-text">
          <div className="step-title">Select Student Rosters (.xlsx, .xls, or .csv)</div>
          <div className="step-sub">
            Class student rosters from{' '}
            <a
              href="https://registrar.cvsu.edu.ph/"
              target="_blank"
              rel="noreferrer"
              className="text-link"
              style={{ color: 'var(--accent-emerald)' }}
            >
              registrar.cvsu.edu.ph
            </a>
          </div>
        </div>
        <div className="step-desc">Class Lists</div>
      </div>

      {/* Auto-Strip Extra Columns Toggle */}
      <div className="setting-toggle-row" style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px' }}>
        <label className="toggle-switch">
          <input
            type="checkbox"
            id="toggleStripExtraCols"
            checked={stripExtraCols}
            onChange={(e) => setStripExtraCols(e.target.checked)}
          />
          <span className="toggle-slider" />
        </label>
        <div className="toggle-label-text">
          <strong>Auto-strip extra portal columns</strong>
          <div className="toggle-sub" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Detects and drops unneeded columns exported by the portal
          </div>
        </div>
      </div>

      {/* Rosters Dropzone */}
      <div
        id="rosterDropzone"
        className={`dropzone ${isDragOver ? 'drag-active' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={onBrowse}
      >
        <svg
          className="dropzone-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          <line x1="12" y1="11" x2="12" y2="17" />
          <line x1="9" y1="14" x2="15" y2="14" />
        </svg>

        <div className="dropzone-title">Student Roster Spreadsheets</div>
        <div id="rosterPrompt" className="dropzone-hint">
          {rosters.length > 0
            ? `${rosters.length} roster file${rosters.length !== 1 ? 's' : ''} loaded`
            : 'Click "Browse Roster Files" or drop enrollment sheets'}
        </div>

        <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
          <button
            className="btn-browse"
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onBrowse();
            }}
          >
            Browse Roster Files
          </button>

          {rosters.length > 0 && (
            <button
              className="nav-btn"
              id="btnClearRosters"
              type="button"
              style={{ padding: '4px 10px', fontSize: '11px' }}
              onClick={(e) => {
                e.stopPropagation();
                onClearAll();
              }}
            >
              Clear Rosters
            </button>
          )}
        </div>
      </div>

      {/* Roster Pre-flight List */}
      {rosters.length > 0 && (
        <div id="rosterListBox" className="roster-list-box" style={{ marginTop: '14px' }}>
          {rosters.map((rosterPath, idx) => {
            const name = rosterPath.split(/[/\\]/).pop() || rosterPath;
            return (
              <div key={idx} className="roster-row">
                <div className="roster-row-main">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                    <FileText className="w-4 h-4 text-emerald-500 shrink-0" />
                    <span className="roster-name selectable truncate" title={rosterPath}>
                      {name}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <button
                      type="button"
                      className="btn-remove-roster"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                        padding: '2px 4px',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemoveRoster(idx);
                      }}
                      title="Remove roster"
                    >
                      <X className="w-3.5 h-3.5 hover:text-red-500" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};
