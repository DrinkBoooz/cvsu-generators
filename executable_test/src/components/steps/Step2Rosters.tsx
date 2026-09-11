import React, { useState } from 'react';
import { FileText, Trash2, X, Search, Sliders, CheckCircle2, AlertTriangle, AlertCircle } from 'lucide-react';
import { RosterValidationReport } from '../../types/api';
import { Toggle } from '../../design-system/components/Toggle';

interface Step2RostersProps {
  rosters: string[];
  validations?: RosterValidationReport[];
  onBrowse: () => void;
  onDropFiles: (files: FileList | File[]) => void;
  onRemoveRoster: (index: number) => void;
  onClearAll: () => void;
  onOpenMappingModal?: (filename: string) => void;
}

export const Step2Rosters: React.FC<Step2RostersProps> = ({
  rosters,
  validations = [],
  onBrowse,
  onDropFiles,
  onRemoveRoster,
  onClearAll,
  onOpenMappingModal,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [stripExtraCols, setStripExtraCols] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

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

  const filteredRosters = rosters.filter((rosterPath) => {
    if (!searchQuery.trim()) return true;
    const name = rosterPath.split(/[/\\]/).pop() || rosterPath;
    return name.toLowerCase().includes(searchQuery.toLowerCase());
  });

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
      <div style={{ marginBottom: '14px' }}>
        <Toggle
          id="toggleStripExtraCols"
          checked={stripExtraCols}
          onChange={setStripExtraCols}
          label="Auto-strip extra portal columns"
          description="Detects and isolates Name and Student Number columns safely"
        />
      </div>

      {/* Rosters Dropzone with correct ID for Python native bridge */}
      <div
        id="rostersDropzone"
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
          {rosters.length > 3 && (
            <div style={{ padding: '4px 0 10px 0' }}>
              <input
                type="text"
                className="text-input"
                placeholder="Filter loaded rosters..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ width: '100%', fontSize: '12px' }}
              />
            </div>
          )}

          <div id="rosterRowsContainer">
            {filteredRosters.map((rosterPath, idx) => {
              const filename = rosterPath.split(/[/\\]/).pop() || rosterPath;
              const rep = validations.find((v) => v.filename === filename);

              let statusBadge = (
                <span className="badge-status badge-valid" style={{ fontSize: '11px', padding: '2px 8px' }}>
                  Ready
                </span>
              );

              if (rep) {
                if (rep.issue === 'incomplete_filename') {
                  statusBadge = (
                    <span className="badge-status badge-warning" title={rep.message || 'Incomplete details'}>
                      ⚠️ Incomplete Details
                    </span>
                  );
                } else if (rep.status === 'warning') {
                  statusBadge = (
                    <span className="badge-status badge-valid" title="Auto-Cleaned safely">
                      🛡️ Auto-Cleaned
                    </span>
                  );
                } else if (rep.status === 'error') {
                  statusBadge = (
                    <span className="badge-status badge-error" title={rep.message || 'Unrecognized format'}>
                      Invalid Format
                    </span>
                  );
                }
              }

              return (
                <div key={idx} className="roster-row" style={{ marginTop: '6px' }}>
                  <div className="roster-row-main" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                      <FileText className="w-4 h-4 text-emerald-500 shrink-0" />
                      <span className="roster-name selectable truncate" title={rosterPath} style={{ fontSize: '12.5px', fontWeight: 500 }}>
                        {filename}
                      </span>
                      {rep?.ceit_metadata && (
                        <span className="badge-ceit-pill" style={{ fontSize: '10px', padding: '1px 6px' }}>
                          {rep.ceit_metadata.prefix}
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                      {statusBadge}
                      {onOpenMappingModal && (
                        <button
                          type="button"
                          className="btn-map-columns"
                          onClick={() => onOpenMappingModal(filename)}
                          title="Configure class details and column mapping"
                        >
                          ⚙️ Map
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn-remove-roster"
                        onClick={(e) => {
                          e.stopPropagation();
                          onRemoveRoster(idx);
                        }}
                        title="Remove file"
                      >
                        <X className="w-3.5 h-3.5 hover:text-red-500" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
};
