import React, { useState } from 'react';

export interface DropzoneProps {
  id: string;
  title: string;
  hint: string;
  acceptedFormatsText?: string;
  currentPath?: string;
  currentFileName?: string;
  fileBadge?: string;
  onBrowse: () => void;
  onDropFiles: (files: FileList | File[]) => void;
  onClear?: () => void;
  icon?: React.ReactNode;
  className?: string;
}

export const Dropzone: React.FC<DropzoneProps> = ({
  id,
  title,
  hint,
  acceptedFormatsText,
  currentPath,
  currentFileName,
  fileBadge,
  onBrowse,
  onDropFiles,
  onClear,
  icon,
  className = '',
}) => {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onDropFiles(e.dataTransfer.files);
    }
  };

  const hasFile = Boolean(currentPath || currentFileName);

  return (
    <div
      id={id}
      className={`hig-dropzone ${isDragOver ? 'hig-drag-active' : ''} ${hasFile ? 'hig-has-file' : ''} ${className}`.trim()}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={onBrowse}
      tabIndex={0}
      role="button"
      aria-label={`${title}. ${hasFile ? (currentFileName || currentPath) : hint}`}
      onKeyDown={(e) => {
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          onBrowse();
        }
      }}
    >
      <div className="hig-dropzone-icon-container">
        {icon || (
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        )}
      </div>

      <div className="hig-dropzone-content">
        <div className="hig-dropzone-header">
          <span className="hig-dropzone-title">{title}</span>
          {fileBadge && (
            <span className="hig-badge-format">{fileBadge}</span>
          )}
        </div>

        <div className="hig-dropzone-hint">
          {hasFile ? (currentFileName || currentPath) : hint}
        </div>

        {acceptedFormatsText && !hasFile && (
          <div className="hig-dropzone-formats">{acceptedFormatsText}</div>
        )}
      </div>

      <div className="hig-dropzone-actions" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="hig-btn hig-btn-secondary hig-btn-sm"
          onClick={onBrowse}
        >
          Browse
        </button>

        {hasFile && onClear && (
          <button
            type="button"
            className="hig-btn hig-btn-ghost hig-btn-sm hig-btn-destructive"
            onClick={onClear}
            title="Clear selection"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
};
