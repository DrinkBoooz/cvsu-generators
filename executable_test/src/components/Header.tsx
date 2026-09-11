import React from 'react';
import { Sun, Moon, Settings, HelpCircle, FileText } from 'lucide-react';

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
    <header className="sticky top-0 z-30 backdrop-blur-xl border-b border-[var(--border-subtle)] bg-[var(--surface-card)] transition-colors duration-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Left */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-emerald-400 flex items-center justify-center text-white shadow-md shadow-emerald-500/20">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold tracking-tight text-[var(--text-primary)]">
                CvSU Document Generator
              </h1>
              <span className="badge-version text-[11px] font-semibold tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                v2.0 Beta
              </span>
            </div>
            <p className="text-xs text-[var(--text-muted)] font-medium">
              Cavite State University · Academic Forms Engine
            </p>
          </div>
        </div>

        {/* Action Controls Right */}
        <div className="flex items-center space-x-2">
          {/* Help Drawer Trigger */}
          <button
            onClick={onOpenHelp}
            className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] transition-colors"
            title="Help & Guidelines"
            id="btnHelpDrawer"
          >
            <HelpCircle className="w-5 h-5" />
          </button>

          {/* Theme Toggle */}
          <button
            onClick={onToggleTheme}
            className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] transition-colors"
            title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
            id="btnThemeToggle"
          >
            {isDark ? <Sun className="w-5 h-5 text-amber-400" /> : <Moon className="w-5 h-5" />}
          </button>

          {/* Settings Modal Trigger */}
          <button
            onClick={onOpenSettings}
            className="p-2 rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] transition-colors"
            title="Curriculum & Parser Settings (Ctrl+,)"
            id="btnSettings"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
};
