import React, { useState } from 'react';
import { CheckCircle2, AlertCircle, Layers, Check, Search, BookOpen } from 'lucide-react';
import { DetectedClass } from '../../types/api';

interface Step3ClassReviewProps {
  detectedClasses: DetectedClass[];
  selectedClassIds: string[];
  onToggleClassSelection: (classId: string) => void;
  onSelectAllClasses?: (select: boolean) => void;
  typeOverrides: Record<string, string>;
  onTypeOverrideChange: (classId: string, type: 'lecture_lab' | 'lecture_only') => void;
  engines: { attendance: boolean; ceit: boolean; grades: boolean };
  onToggleEngine: (engine: 'attendance' | 'ceit' | 'grades') => void;
  onOpenMappingModal?: () => void;
}

export const Step3ClassReview: React.FC<Step3ClassReviewProps> = ({
  detectedClasses,
  selectedClassIds,
  onToggleClassSelection,
  onSelectAllClasses,
  typeOverrides,
  onTypeOverrideChange,
  engines,
  onToggleEngine,
  onOpenMappingModal,
}) => {
  const [filterType, setFilterType] = useState<'all' | 'lab' | 'lec'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filtered = detectedClasses.filter((cls) => {
    const classId = cls.id || `${cls.course_sec}_${cls.schedule_code}`;
    const activeType = typeOverrides[classId] || cls.detected_type;
    const isLab = activeType === 'lecture_lab';

    if (filterType === 'lab' && !isLab) return false;
    if (filterType === 'lec' && isLab) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchSec = cls.course_sec.toLowerCase().includes(q);
      const matchSub = cls.subject_name.toLowerCase().includes(q);
      const matchCode = cls.schedule_code.toLowerCase().includes(q);
      if (!matchSec && !matchSub && !matchCode) return false;
    }

    return true;
  });

  return (
    <section className="glass-card" id="cardStep3">
      <div className="step-header">
        <div className="step-number">3</div>
        <div className="step-header-text">
          <div className="step-title">Confirm Detected Classes &amp; Subject Types</div>
          <div className="step-sub">Select packages to compile &amp; confirm grading templates</div>
        </div>
        <div className="step-desc">Templates &amp; Packages</div>
      </div>

      {/* Document Engine Toggles */}
      <label className="form-label" style={{ marginBottom: '8px', display: 'block' }}>
        Document Packages to Compile
      </label>
      <div
        className="engine-selector"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '10px',
          marginBottom: '16px',
        }}
      >
        <div
          className={`engine-chip ${engines.attendance ? 'active' : ''}`}
          id="chipAttendance"
          onClick={() => onToggleEngine('attendance')}
          style={{
            padding: '12px',
            borderRadius: '10px',
            border: '1px solid var(--border-subtle)',
            background: engines.attendance ? 'rgba(16, 185, 129, 0.1)' : 'var(--surface-subtle)',
            borderColor: engines.attendance ? 'var(--accent-emerald)' : 'var(--border-subtle)',
            cursor: 'pointer',
            transition: 'all 0.18s ease',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="checkbox"
              id="checkAttendance"
              className="engine-checkbox"
              checked={engines.attendance}
              readOnly
            />
            <div>
              <div style={{ fontWeight: 700, fontSize: '12.5px', color: 'var(--text-primary)' }}>
                Attendance Sheets
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Monthly logs (.docx)</div>
            </div>
          </div>
        </div>

        <div
          className={`engine-chip ${engines.ceit ? 'active' : ''}`}
          id="chipCeit"
          onClick={() => onToggleEngine('ceit')}
          style={{
            padding: '12px',
            borderRadius: '10px',
            border: '1px solid var(--border-subtle)',
            background: engines.ceit ? 'rgba(16, 185, 129, 0.1)' : 'var(--surface-subtle)',
            borderColor: engines.ceit ? 'var(--accent-emerald)' : 'var(--border-subtle)',
            cursor: 'pointer',
            transition: 'all 0.18s ease',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="checkbox"
              id="checkCeit"
              className="engine-checkbox"
              checked={engines.ceit}
              readOnly
            />
            <div>
              <div style={{ fontWeight: 700, fontSize: '12.5px', color: 'var(--text-primary)' }}>
                CEIT Dept Forms
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>7 Forms (.docx)</div>
            </div>
          </div>
        </div>

        <div
          className={`engine-chip ${engines.grades ? 'active' : ''}`}
          id="chipGrades"
          onClick={() => onToggleEngine('grades')}
          style={{
            padding: '12px',
            borderRadius: '10px',
            border: '1px solid var(--border-subtle)',
            background: engines.grades ? 'rgba(16, 185, 129, 0.1)' : 'var(--surface-subtle)',
            borderColor: engines.grades ? 'var(--accent-emerald)' : 'var(--border-subtle)',
            cursor: 'pointer',
            transition: 'all 0.18s ease',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              type="checkbox"
              id="checkGrades"
              className="engine-checkbox"
              checked={engines.grades}
              readOnly
            />
            <div>
              <div style={{ fontWeight: 700, fontSize: '12.5px', color: 'var(--text-primary)' }}>
                Grading Sheets
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Registrar Grade (.xlsx)</div>
            </div>
          </div>
        </div>
      </div>

      {/* Detected Classes Section */}
      <div id="classesSection">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <label className="form-label" style={{ margin: 0 }}>
              Detected Timetable Classes
            </label>
            <span id="classesCountDisplay" className="badge-version" style={{ fontSize: '11px' }}>
              {detectedClasses.length}
            </span>
          </div>

          {detectedClasses.length > 0 && onSelectAllClasses && (
            <div style={{ display: 'flex', gap: '8px', fontSize: '11.5px' }}>
              <button
                type="button"
                className="text-link"
                onClick={() => onSelectAllClasses(true)}
                style={{ color: 'var(--accent-emerald)', cursor: 'pointer', background: 'none', border: 'none' }}
              >
                Select All
              </button>
              <span style={{ color: 'var(--border-subtle)' }}>|</span>
              <button
                type="button"
                className="text-link"
                onClick={() => onSelectAllClasses(false)}
                style={{ color: 'var(--text-muted)', cursor: 'pointer', background: 'none', border: 'none' }}
              >
                Deselect All
              </button>
            </div>
          )}
        </div>

        {detectedClasses.length === 0 ? (
          <div
            style={{
              padding: '24px',
              textAlign: 'center',
              border: '1px dashed var(--border-subtle)',
              borderRadius: '10px',
              color: 'var(--text-secondary)',
              fontSize: '12.5px',
            }}
          >
            <BookOpen className="w-6 h-6 mx-auto mb-2 text-muted" style={{ opacity: 0.6 }} />
            <div>Upload your Master Schedule and Student Rosters to automatically detect classes.</div>
          </div>
        ) : (
          <>
            {detectedClasses.length > 3 && (
              <div style={{ marginBottom: '10px' }}>
                <input
                  type="text"
                  className="text-input"
                  placeholder="Filter detected classes by code or title..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ width: '100%', fontSize: '12px' }}
                />
              </div>
            )}

            <div id="classesListContainer" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filtered.map((cls) => {
                const classId = cls.id || `${cls.course_sec}_${cls.schedule_code}`;
                const isSelected = selectedClassIds.includes(classId);
                const activeType = typeOverrides[classId] || cls.detected_type;
                const isLab = activeType === 'lecture_lab';

                return (
                  <div
                    key={classId}
                    id={`card_${classId}`}
                    className="class-card"
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '12px',
                      borderRadius: '10px',
                      border: '1px solid var(--border-subtle)',
                      background: 'var(--surface-elevated)',
                    }}
                  >
                    <input
                      type="checkbox"
                      className="class-select-check item-class-check"
                      checked={isSelected}
                      onChange={() => onToggleClassSelection(classId)}
                      style={{ cursor: 'pointer' }}
                    />

                    <div className="class-details" style={{ flex: 1, minWidth: 0 }}>
                      <div className="class-header-row" style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span className="course-badge">{cls.course_sec}</span>
                        <span className="sched-badge">Sched: {cls.schedule_code}</span>
                        {cls.ceit_metadata && (
                          <span className="badge-ceit-pill" title={cls.ceit_metadata.department_name}>
                            {cls.ceit_metadata.prefix}
                          </span>
                        )}
                      </div>
                      <div className="subject-title truncate" style={{ marginTop: '3px', fontWeight: 600, fontSize: '12.5px' }}>
                        {cls.subject_name}
                      </div>
                      <div className="sched-schedule-line" style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        {cls.schedule_desc}
                      </div>
                    </div>

                    <div style={{ flexShrink: 0 }}>
                      <select
                        className="type-dropdown class-type-select"
                        value={isLab ? 'lecture_lab' : 'lecture_only'}
                        onChange={(e) =>
                          onTypeOverrideChange(classId, e.target.value as 'lecture_lab' | 'lecture_only')
                        }
                        style={{ fontSize: '11.5px', padding: '4px 8px', borderRadius: '6px' }}
                      >
                        <option value="lecture_lab">Lecture and Lab</option>
                        <option value="lecture_only">Lecture only</option>
                      </select>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </section>
  );
};
