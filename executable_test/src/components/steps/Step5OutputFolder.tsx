import React from 'react';
import { Folder, FolderOpen } from 'lucide-react';

interface Step5OutputFolderProps {
  outputPath: string;
  onBrowse: () => void;
  onOpenFolder?: () => void;
}

export const Step5OutputFolder: React.FC<Step5OutputFolderProps> = ({
  outputPath,
  onBrowse,
  onOpenFolder,
}) => {
  return (
    <section className="glass-card" id="cardStep5">
      <div className="step-header">
        <div className="step-number">5</div>
        <div className="step-header-text">
          <div className="step-title">Choose Target Output Folder</div>
          <div className="step-sub">Destination directory for compiled document packages</div>
        </div>
        <div className="step-desc">Destination Directory</div>
      </div>

      <p className="step-instructions">
        Click <strong>"Browse Path"</strong> and select any destination folder on your computer where the files should be saved.
      </p>

      <div className="input-with-action" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <input
          type="text"
          id="outputDisplay"
          className="text-input selectable"
          style={{ flex: 1 }}
          placeholder="Select destination folder for generated files..."
          value={outputPath}
          readOnly
        />
        <button className="btn-browse" type="button" onClick={onBrowse}>
          Browse Path
        </button>
        {outputPath && onOpenFolder && (
          <button
            className="nav-btn"
            id="btnOpenOutput"
            type="button"
            onClick={onOpenFolder}
            title="Open Target Folder"
          >
            Open Folder
          </button>
        )}
      </div>

      {outputPath && (
        <div
          id="outputPathStatus"
          style={{
            fontSize: '12px',
            marginTop: '6px',
            fontWeight: 600,
            color: 'var(--accent-emerald)',
          }}
        >
          ✓ Ready to generate files in: {outputPath}
        </div>
      )}
    </section>
  );
};
