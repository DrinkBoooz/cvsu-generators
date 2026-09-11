import React, { useState } from 'react';
import { X, RotateCcw, Download, Upload, Check, BookOpen, FlaskConical, Link2, Tag, Sliders, FilePlus2 } from 'lucide-react';
import { ParserConfig, CustomTemplate } from '../../types/api';
import { TabPrefixes } from './settings/TabPrefixes';
import { TabLabCodes } from './settings/TabLabCodes';
import { TabDegreeAliases } from './settings/TabDegreeAliases';
import { TabKeywords } from './settings/TabKeywords';
import { TabDefaults } from './settings/TabDefaults';
import { TabCustomTemplates } from './settings/TabCustomTemplates';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  config: ParserConfig;
  customTemplates: CustomTemplate[];
  onSaveConfig: (cfg: ParserConfig) => void;
  onResetDefaults: () => void;
  onExportConfig: () => void;
  onImportConfig: () => void;
  onRefreshCustomTemplates: () => void;
  onShowToast: (type: 'success' | 'warning' | 'error' | 'info', title: string, msg: string) => void;
}

type SettingsTab = 'prefixes' | 'labs' | 'degrees' | 'keywords' | 'defaults' | 'custom_templates';

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  config,
  customTemplates,
  onSaveConfig,
  onResetDefaults,
  onExportConfig,
  onImportConfig,
  onRefreshCustomTemplates,
  onShowToast,
}) => {
  if (!isOpen) return null;

  const [activeTab, setActiveTab] = useState<SettingsTab>('prefixes');
  const [localConfig, setLocalConfig] = useState<ParserConfig>(() => ({ ...config }));

  const tabs = [
    { id: 'prefixes', label: 'Subject Prefixes', icon: BookOpen },
    { id: 'labs', label: 'Lab Courses', icon: FlaskConical },
    { id: 'degrees', label: 'Degree Aliases', icon: Link2 },
    { id: 'keywords', label: 'Column Keywords', icon: Tag },
    { id: 'defaults', label: 'Defaults', icon: Sliders },
    { id: 'custom_templates', label: 'Custom Templates', icon: FilePlus2 },
  ];

  const handleSave = () => {
    onSaveConfig(localConfig);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--modal-overlay)] backdrop-blur-sm animate-fade-in">
      <div className="glass-card w-full max-w-4xl max-h-[90vh] flex flex-col bg-[var(--surface-elevated)] shadow-2xl border border-[var(--border-subtle)] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[var(--border-subtle)]">
          <div>
            <h3 className="text-base font-bold text-[var(--text-primary)]">
              Curriculum, Parser & Template Settings
            </h3>
            <p className="text-xs text-[var(--text-muted)]">
              Manage subject prefixes, lab requirements, column keywords, and custom document templates
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-subtle)] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 6 Segmented Tabs Navigation */}
        <div className="px-5 pt-3 border-b border-[var(--border-subtle)] bg-[var(--surface-subtle)] overflow-x-auto flex space-x-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as SettingsTab)}
                className={`flex items-center space-x-2 py-2 px-3.5 border-b-2 text-xs font-semibold whitespace-nowrap transition-colors ${
                  isActive
                    ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400 bg-[var(--surface-elevated)] rounded-t-lg'
                    : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab Content Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {activeTab === 'prefixes' && (
            <TabPrefixes config={localConfig} onChange={setLocalConfig} />
          )}
          {activeTab === 'labs' && (
            <TabLabCodes config={localConfig} onChange={setLocalConfig} />
          )}
          {activeTab === 'degrees' && (
            <TabDegreeAliases config={localConfig} onChange={setLocalConfig} />
          )}
          {activeTab === 'keywords' && (
            <TabKeywords config={localConfig} onChange={setLocalConfig} />
          )}
          {activeTab === 'defaults' && (
            <TabDefaults config={localConfig} onChange={setLocalConfig} />
          )}
          {activeTab === 'custom_templates' && (
            <TabCustomTemplates
              customTemplates={customTemplates}
              onRefreshTemplates={onRefreshCustomTemplates}
              onShowToast={onShowToast}
            />
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 border-t border-[var(--border-subtle)] bg-[var(--surface-subtle)]">
          {/* Left Action Buttons */}
          <div className="flex items-center space-x-2 w-full sm:w-auto">
            <button
              onClick={onResetDefaults}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-[var(--text-secondary)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
              title="Reset all settings to factory defaults"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset Defaults</span>
            </button>
            <button
              onClick={onExportConfig}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-elevated)] transition-colors"
              title="Export configuration JSON"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export</span>
            </button>
            <button
              onClick={onImportConfig}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-elevated)] transition-colors"
              title="Import configuration JSON"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Import</span>
            </button>
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center space-x-2 w-full sm:w-auto justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-elevated)] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-500/20 transition-colors"
            >
              <Check className="w-4 h-4" />
              <span>Save & Apply Changes</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
