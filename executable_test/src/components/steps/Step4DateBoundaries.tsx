import React from 'react';

interface Step4DateBoundariesProps {
  startDate: string;
  endDate: string;
  onStartDateChange: (val: string) => void;
  onEndDateChange: (val: string) => void;
  semesterAy?: string;
}

export const Step4DateBoundaries: React.FC<Step4DateBoundariesProps> = ({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  semesterAy,
}) => {
  const currentYear = new Date().getFullYear();

  const setPreset = (sem: '1st' | '2nd') => {
    if (sem === '1st') {
      onStartDateChange(`${currentYear}-08-15`);
      onEndDateChange(`${currentYear}-12-20`);
    } else {
      onStartDateChange(`${currentYear + 1}-01-15`);
      onEndDateChange(`${currentYear + 1}-05-30`);
    }
  };

  const clearPresets = () => {
    onStartDateChange('');
    onEndDateChange('');
  };

  return (
    <section className="glass-card" id="cardStep4">
      <div className="step-header">
        <div className="step-number">4</div>
        <div className="step-header-text">
          <div className="step-title">(Optional) Set Semester Date Boundaries</div>
          <div className="step-sub">Standard calendar (Aug–Dec / Jan–May) or custom range</div>
        </div>
        <div className="step-desc">Attendance Calendar</div>
      </div>

      <p className="step-instructions">
        If you want attendance sheets to cover only specific dates of the semester, select a{' '}
        <strong>Start Date</strong> and <strong>End Date</strong>.<br />
        <em>
          If left blank, the app will generate sheets for the standard semester calendar (August–December for 1st Semester; January–May for 2nd Semester).
        </em>
      </p>

      <div className="date-boundary-box">
        <div className="date-inputs-row">
          <div className="date-input-group">
            <span>Start:</span>
            <input
              type="date"
              id="startDate"
              className="date-input"
              value={startDate}
              onChange={(e) => onStartDateChange(e.target.value)}
            />
          </div>
          <div className="date-input-group">
            <span>End:</span>
            <input
              type="date"
              id="endDate"
              className="date-input"
              value={endDate}
              onChange={(e) => onEndDateChange(e.target.value)}
            />
          </div>
        </div>

        <div className="preset-chips segmented-control">
          <button
            type="button"
            className="chip-preset segmented-btn"
            onClick={() => setPreset('1st')}
          >
            1st Sem (Aug-Dec)
          </button>
          <button
            type="button"
            className="chip-preset segmented-btn"
            onClick={() => setPreset('2nd')}
          >
            2nd Sem (Jan-May)
          </button>
          <button
            type="button"
            className="chip-preset segmented-btn"
            onClick={clearPresets}
          >
            Reset Dates
          </button>
        </div>
      </div>
    </section>
  );
};
