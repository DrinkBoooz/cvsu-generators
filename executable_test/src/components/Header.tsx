import React from 'react';
import { Sun, Moon, Settings, HelpCircle, FileText, Activity } from 'lucide-react';

interface HeaderProps {
  isDark: boolean;
  onToggleTheme: () => void;
  onOpenSettings: () => void;
  onOpenHelp: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  isDark,
  onToggleTheme,
  onOpenSettings,
  onOpenHelp,
}) => {
  return (
    <div className="top-nav-bar">
      <header className="top-header">
        <div className="brand-lockup">
          <div className="brand-icon">
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="brand-title">CvSU Gen</span>
              <span className="badge-version">v2.0 Beta</span>
            </div>
            <div className="brand-subtitle">
              Cavite State University Document Automation
            </div>
          </div>
        </div>

        <div className="header-actions">
          <button
            className="nav-btn"
            id="btnToggleTheme"
            onClick={onToggleTheme}
            title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
            aria-label="Toggle Dark/Light Mode"
          >
            <span id="themeIcon" className="theme-icon-container">
              {isDark ? (
                <Sun className="w-[15px] h-[15px] text-amber-400" />
              ) : (
                <Moon className="w-[15px] h-[15px]" />
              )}
            </span>
            <span id="themeLabel">{isDark ? "Light" : "Dark"}</span>
          </button>

          <button
            className="nav-btn"
            id="btnOpenSettings"
            onClick={onOpenSettings}
            title="Curriculum & Parser Settings"
            aria-label="Open Curriculum and Parser Configuration"
          >
            <Settings className="w-[15px] h-[15px]" />
            Settings
          </button>

          <button
            className="nav-btn"
            id="btnOpenHelp"
            onClick={onOpenHelp}
            title="View User Guide & Rules"
          >
            <HelpCircle className="w-[15px] h-[15px]" />
            Guides
          </button>
        </div>
      </header>
    </div>
  );
};
