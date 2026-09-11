import React from 'react';

interface StepperProps {
  hasSchedule: boolean;
  rosterCount: number;
  classCount: number;
  hasOutput: boolean;
  isGenerating: boolean;
}

export const Stepper: React.FC<StepperProps> = ({
  hasSchedule,
  rosterCount,
  classCount,
  hasOutput,
  isGenerating,
}) => {
  const scrollTo = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const isStep1Ready = hasSchedule;
  const isStep2Ready = rosterCount > 0;
  const isStep3Ready = classCount > 0;
  const isStep4Ready = true; // Dates are optional with defaults
  const isStep5Ready = Boolean(hasOutput);
  const isStep6Ready = isStep1Ready && isStep2Ready && isStep3Ready && isStep5Ready;

  return (
    <div className="stepper-bar" id="workflowStepper">
      <div className="stepper-track">
        {/* Step 1: Schedule */}
        <button
          className={`step-chip ${isStep1Ready ? 'ready' : ''}`}
          id="chipStep1"
          type="button"
          onClick={() => scrollTo('cardStep1')}
        >
          <span className="chip-num">1</span>
          <span className="chip-txt">Schedule</span>
          <span className="chip-status" id="statusStep1">{isStep1Ready ? '🟢' : '⚪'}</span>
        </button>

        <div className={`stepper-connector ${isStep1Ready ? 'ready' : ''}`} id="connector1to2" />

        {/* Step 2: Rosters */}
        <button
          className={`step-chip ${isStep2Ready ? 'ready' : ''}`}
          id="chipStep2"
          type="button"
          onClick={() => scrollTo('cardStep2')}
        >
          <span className="chip-num">2</span>
          <span className="chip-txt">Rosters</span>
          <span className="chip-status" id="statusStep2">{isStep2Ready ? '🟢' : '⚪'}</span>
        </button>

        <div className={`stepper-connector ${isStep2Ready ? 'ready' : ''}`} id="connector2to3" />

        {/* Step 3: Packages */}
        <button
          className={`step-chip ${isStep3Ready ? 'ready' : ''}`}
          id="chipStep3"
          type="button"
          onClick={() => scrollTo('cardStep3')}
        >
          <span className="chip-num">3</span>
          <span className="chip-txt">Packages</span>
          <span className="chip-status" id="statusStep3">{isStep3Ready ? '🟢' : '⚪'}</span>
        </button>

        <div className={`stepper-connector ${isStep3Ready ? 'ready' : ''}`} id="connector3to4" />

        {/* Step 4: Dates */}
        <button
          className={`step-chip ${isStep4Ready ? 'ready' : ''}`}
          id="chipStep4"
          type="button"
          onClick={() => scrollTo('cardStep4')}
        >
          <span className="chip-num">4</span>
          <span className="chip-txt">Dates</span>
          <span className="chip-status" id="statusStep4">{isStep4Ready ? '🟢' : '⚪'}</span>
        </button>

        <div className={`stepper-connector ${isStep4Ready ? 'ready' : ''}`} id="connector4to5" />

        {/* Step 5: Output */}
        <button
          className={`step-chip ${isStep5Ready ? 'ready' : ''}`}
          id="chipStep5"
          type="button"
          onClick={() => scrollTo('cardStep5')}
        >
          <span className="chip-num">5</span>
          <span className="chip-txt">Output</span>
          <span className="chip-status" id="statusStep5">{isStep5Ready ? '🟢' : '⚪'}</span>
        </button>

        <div className={`stepper-connector ${isStep5Ready ? 'ready' : ''}`} id="connector5to6" />

        {/* Step 6: Generate */}
        <button
          className={`step-chip ${isStep6Ready ? 'ready' : ''}`}
          id="chipStep6"
          type="button"
          onClick={() => scrollTo('cardStep6')}
        >
          <span className="chip-num">6</span>
          <span className="chip-txt">Generate</span>
          <span className="chip-status" id="statusStep6">{isStep6Ready ? '🟢' : '⚪'}</span>
        </button>
      </div>
    </div>
  );
};
