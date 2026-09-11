import React, { useState } from 'react';
import { CheckCircle2, AlertCircle, SlidersHorizontal, Layers, Check } from 'lucide-react';
import { ClassValidation, RosterConfigMap } from '../../types/api';

interface Step3ClassReviewProps {
  validations: ClassValidation[];
  classConfigs: RosterConfigMap;
  onToggleLab: (key: string, hasLab: boolean) => void;
  onOpenMappingModal: () => void;
}

export const Step3ClassReview: React.FC<Step3ClassReviewProps> = ({
  validations,
  classConfigs,
  onToggleLab,
  onOpenMappingModal,
}) => {
  const [filterType, setFilterType] = useState<'all' | 'lab' | 'lec'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [engines, setEngines] = useState({
    attendance: true,
    ceit: true,
    grades: true,
  });

  const toggleEngine = (key: 'attendance' | 'ceit' | 'grades') => {
    setEngines(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const filtered = validations.filter((v) => {
    const key = `${v.course_section}_${v.schedule_code}`;
    const hasLab = classConfigs[key]?.has_lab ?? v.has_lab;

    if (filterType === 'lab' && !hasLab) return false;
    if (filterType === 'lec' && hasLab) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchSec = v.course_section.toLowerCase().includes(q);
      const matchSub = v.subject.toLowerCase().includes(q);
      const matchCode = v.schedule_code.toLowerCase().includes(q);
      if (!matchSec && !matchSub && !matchCode) return false;
    }

    return true;
  });

  const readyCount = validations.filter(v => v.status === 'paired').length;

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
      <div className="engine-selector" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginBottom: '16px' }}>
        <div
          className={`engine-chip ${engines.attendance ? 'active' : ''}`}
          id="chipAttendance"
          onClick={() => toggleEngine('attendance')}
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
          onClick={() => toggleEngine('ceit')}
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
          onClick={() => toggleEngine('grades')}
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
                Official Grade Sheets
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Lecture / Lab (.xlsx)</div>
            </div>
          </div>
        </div>
      </div>

      {/* Classes Header & Filters */}
      {validations.length > 0 ? (
        <div id="classesSection">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '10px',
              flexWrap: 'wrap',
              gap: '8px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12.5px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Detected Classes ({validations.length})
              </span>
              <span className="badge-version" id="classesReadyBadge">
                {readyCount} / {validations.length} Paired
              </span>
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="Search classes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  fontSize: '11.5px',
                  padding: '4px 10px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-subtle)',
                  background: 'var(--surface-card)',
                  color: 'var(--text-primary)',
                  outline: 'none',
                  width: '140px',
                }}
              />
              <button
                type="button"
                onClick={onOpenMappingModal}
                className="nav-btn"
                id="btnOpenMappingModal"
                style={{ padding: '4px 10px', fontSize: '11.5px' }}
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                Manual Section Mapping
              </button>
            </div>
          </div>

          {/* Quick Filters */}
          <div className="segmented-control" style={{ marginBottom: '12px' }}>
            <button
              className={`segmented-btn filter-pill ${filterType === 'all' ? 'active' : ''}`}
              type="button"
              onClick={() => setFilterType('all')}
            >
              All
            </button>
            <button
              className={`segmented-btn filter-pill ${filterType === 'lab' ? 'active' : ''}`}
              type="button"
              onClick={() => setFilterType('lab')}
            >
              Lecture &amp; Lab Only
            </button>
            <button
              className={`segmented-btn filter-pill ${filterType === 'lec' ? 'active' : ''}`}
              type="button"
              onClick={() => setFilterType('lec')}
            >
              Lecture Only
            </button>
          </div>

          {/* Classes Table */}
          <div
            className="classes-table-wrapper"
            style={{
              maxHeight: '380px',
              overflowY: 'auto',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
              background: 'var(--surface-elevated)',
            }}
          >
            <table className="settings-data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--surface-subtle)', borderBottom: '1px solid var(--border-subtle)' }}>
                  <th style={{ padding: '10px 14px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Section</th>
                  <th style={{ padding: '10px 14px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Code</th>
                  <th style={{ padding: '10px 14px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Subject Title</th>
                  <th style={{ padding: '10px 14px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Paired Roster</th>
                  <th style={{ padding: '10px 14px', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', textAlign: 'center', color: 'var(--text-secondary)' }}>Grading Template</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((v, idx) => {
                  const key = `${v.course_section}_${v.schedule_code}`;
                  const hasLab = classConfigs[key]?.has_lab ?? v.has_lab;
                  const isPaired = v.status === 'paired';

                  return (
                    <tr
                      key={idx}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        transition: 'background-color 0.15s ease',
                      }}
                    >
                      <td style={{ padding: '10px 14px', fontWeight: 700, fontSize: '12.5px', color: 'var(--text-primary)' }}>
                        {v.course_section}
                      </td>
                      <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: '12px', color: 'var(--text-muted)' }}>
                        {v.schedule_code}
                      </td>
                      <td style={{ padding: '10px 14px', fontSize: '12.5px', color: 'var(--text-primary)', maxWidth: '240px' }} className="truncate" title={v.subject}>
                        {v.subject}
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        {isPaired ? (
                          <span
                            className="badge-ceit-pill"
                            style={{
                              background: 'rgba(16, 185, 129, 0.12)',
                              color: 'var(--accent-emerald)',
                              border: '1px solid rgba(16, 185, 129, 0.3)',
                              padding: '3px 8px',
                              borderRadius: '999px',
                              fontSize: '11px',
                              fontWeight: 600,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <CheckCircle2 className="w-3 h-3" />
                            <span>{v.student_count} Students</span>
                          </span>
                        ) : (
                          <span
                            style={{
                              background: 'rgba(245, 158, 11, 0.12)',
                              color: 'var(--accent-amber)',
                              border: '1px solid rgba(245, 158, 11, 0.3)',
                              padding: '3px 8px',
                              borderRadius: '999px',
                              fontSize: '11px',
                              fontWeight: 600,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <AlertCircle className="w-3 h-3" />
                            <span>Missing Roster</span>
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '10px 14px', textAlign: 'center' }}>
                        <div
                          className="segmented-control"
                          style={{
                            display: 'inline-flex',
                            borderRadius: '8px',
                            padding: '2px',
                            background: 'var(--surface-subtle)',
                            border: '1px solid var(--border-subtle)',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => onToggleLab(key, false)}
                            style={{
                              padding: '4px 10px',
                              fontSize: '11px',
                              fontWeight: 600,
                              borderRadius: '6px',
                              border: 'none',
                              cursor: 'pointer',
                              background: !hasLab ? 'var(--surface-elevated)' : 'transparent',
                              color: !hasLab ? 'var(--accent-emerald)' : 'var(--text-muted)',
                              boxShadow: !hasLab ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                            }}
                          >
                            Lecture
                          </button>
                          <button
                            type="button"
                            onClick={() => onToggleLab(key, true)}
                            style={{
                              padding: '4px 10px',
                              fontSize: '11px',
                              fontWeight: 600,
                              borderRadius: '6px',
                              border: 'none',
                              cursor: 'pointer',
                              background: hasLab ? 'var(--surface-elevated)' : 'transparent',
                              color: hasLab ? 'var(--accent-emerald)' : 'var(--text-muted)',
                              boxShadow: hasLab ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                            }}
                          >
                            Lec &amp; Lab
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div
          style={{
            textAlign: 'center',
            padding: '32px 16px',
            color: 'var(--text-muted)',
            fontSize: '13px',
          }}
        >
          Load your master schedule spreadsheet in Step 1 to populate detected classes.
        </div>
      )}
    </section>
  );
};
