import React, { useState } from 'react';
import { Calendar, FileSpreadsheet, ChevronDown, Check } from 'lucide-react';
import { ScheduleMetadata } from '../../types/api';

interface Step1ScheduleProps {
  schedulePath: string;
  metadata: ScheduleMetadata | null;
  onBrowse: () => void;
  onDropFile: (file: File) => void;
  onClear: () => void;
}

export const Step1Schedule: React.FC<Step1ScheduleProps> = ({
  schedulePath,
  metadata,
  onBrowse,
  onDropFile,
  onClear,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);

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
      onDropFile(e.dataTransfer.files[0]);
    }
  };

  const fileName = schedulePath ? schedulePath.split(/[/\\]/).pop() : '';
  const fileExt = fileName ? (fileName.split('.').pop() || 'XLS').toUpperCase() : 'XLS';

  // Compute initials
  const initials = metadata?.instructor
    ? metadata.instructor
        .split(' ')
        .filter(Boolean)
        .map(w => w[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'DO';

  return (
    <section className="glass-card" id="cardStep1">
      <div className="step-header">
        <div className="step-number">1</div>
        <div className="step-header-text">
          <div className="step-title">Select Instructor Schedule (.xls or .xlsx)</div>
          <div className="step-sub">Official master schedule spreadsheet from the faculty portal</div>
        </div>
        <div className="step-desc">Master Schedule</div>
      </div>

      {/* Schedule Dropzone */}
      <div
        id="scheduleDropzone"
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
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>

        <div className="dropzone-title">
          Instructor Schedule Spreadsheet
          {schedulePath && (
            <span id="scheduleFormatBadge" className="badge-version" style={{ marginLeft: '6px' }}>
              .{fileExt}
            </span>
          )}
        </div>

        <div id="schedulePrompt" className="dropzone-hint">
          {schedulePath ? fileName : 'Click "Browse File" or drop master schedule (.xls / .xlsx)'}
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
            Browse File
          </button>

          {schedulePath && (
            <button
              className="nav-btn"
              id="btnResetSchedule"
              type="button"
              style={{ padding: '4px 10px', fontSize: '11px' }}
              onClick={(e) => {
                e.stopPropagation();
                onClear();
              }}
            >
              Reset File
            </button>
          )}
        </div>

        {schedulePath && (
          <div id="scheduleFilename" className="dropzone-status selectable" style={{ marginTop: '8px' }}>
            {schedulePath}
          </div>
        )}
      </div>

      {/* Progressive Disclosure Details */}
      <details className="step-disclosure" id="disclosureStep1" style={{ marginTop: '12px' }}>
        <summary className="disclosure-summary">
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
          <span>Schedule Instructions &amp; Async Filtering Notes</span>
          <ChevronDown className="chevron-icon" width="12" height="12" />
        </summary>
        <div className="disclosure-content">
          <p className="step-instructions">
            Download your official schedule spreadsheet from the faculty portal. Click <strong>"Browse File"</strong> below to select your master schedule. The generator automatically extracts your instructor name, college header, semester, academic year, class times, days, and rooms.<br />
            <em>Note: Schedule blocks labeled as Async or Asynch are automatically filtered out so only in-person sessions receive attendance columns.</em>
          </p>
        </div>
      </details>

      {/* Instructor Profile Instant Banner */}
      {metadata && (
        <div id="instructorBanner" className="instructor-banner" style={{ marginTop: '16px' }}>
          <div className="instructor-info">
            <div id="instructorInitials" className="instructor-avatar">
              {initials}
            </div>
            <div>
              <div id="instructorName" className="instructor-name selectable">
                {metadata.instructor || 'Faculty Instructor'}
              </div>
              <div id="instructorCollege" className="instructor-meta selectable">
                College of Engineering and Information Technology
              </div>
            </div>
          </div>
          <div className="instructor-pills">
            <span id="instructorSemPill" className="meta-pill">
              {metadata.semester_ay || '1st Semester AY 2026-2027'}
            </span>
            <span id="instructorSlotsPill" className="meta-pill">
              {metadata.classes?.length || 0} Class Blocks
            </span>
          </div>
        </div>
      )}
    </section>
  );
};
