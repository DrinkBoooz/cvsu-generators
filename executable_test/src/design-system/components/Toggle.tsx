import React from 'react';

export interface ToggleProps {
  id?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: React.ReactNode;
  description?: React.ReactNode;
  disabled?: boolean;
}

export const Toggle: React.FC<ToggleProps> = ({
  id,
  checked,
  onChange,
  label,
  description,
  disabled = false,
}) => {
  const toggleId = id || `hig-toggle-${Math.random().toString(36).substring(2, 8)}`;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (disabled) return;
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      onChange(!checked);
    }
  };

  return (
    <div className={`hig-toggle-row ${disabled ? 'hig-disabled' : ''}`}>
      <div
        id={toggleId}
        role="switch"
        aria-checked={checked}
        aria-disabled={disabled}
        tabIndex={disabled ? -1 : 0}
        className={`hig-toggle-switch ${checked ? 'hig-checked' : ''}`}
        onClick={() => !disabled && onChange(!checked)}
        onKeyDown={handleKeyDown}
      >
        <div className="hig-toggle-thumb" />
      </div>
      {(label || description) && (
        <div className="hig-toggle-text-block" onClick={() => !disabled && onChange(!checked)}>
          {label && <div className="hig-toggle-label">{label}</div>}
          {description && <div className="hig-toggle-desc">{description}</div>}
        </div>
      )}
    </div>
  );
};
