import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { Stepper } from './components/Stepper';
import { Step1Schedule } from './components/steps/Step1Schedule';
import { Step2Rosters } from './components/steps/Step2Rosters';
import { Step3ClassReview } from './components/steps/Step3ClassReview';
import { Step4DateBoundaries } from './components/steps/Step4DateBoundaries';
import { Step5OutputFolder } from './components/steps/Step5OutputFolder';
import { Step6Execution } from './components/steps/Step6Execution';
import { RosterMappingModal } from './components/modals/RosterMappingModal';
import { SettingsModal } from './components/modals/SettingsModal';
import { HelpDrawer } from './components/HelpDrawer';
import { CompletionModal } from './components/CompletionModal';
import { ToastContainer } from './components/ToastContainer';
import { useTheme } from './hooks/useTheme';
import { pywebviewService } from './services/pywebview';
import {
  ScheduleMetadata,
  ClassValidation,
  RosterConfigMap,
  ParserConfig,
  CustomTemplate,
  FileEstimate,
  GenerationSummary,
  ToastMessage,
} from './types/api';

export const App: React.FC = () => {
  const { isDark, toggleTheme } = useTheme();

  // Primary Workflow State
  const [schedulePath, setSchedulePath] = useState<string>('');
  const [scheduleMetadata, setScheduleMetadata] = useState<ScheduleMetadata | null>(null);
  const [rosters, setRosters] = useState<string[]>([]);
  const [validations, setValidations] = useState<ClassValidation[]>([]);
  const [classConfigs, setClassConfigs] = useState<RosterConfigMap>({});
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [outputDir, setOutputDir] = useState<string>('');

  // Execution & Telemetry State
  const [estimate, setEstimate] = useState<FileEstimate | null>(null);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [progressStatus, setProgressStatus] = useState<string>('');
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [totalSteps, setTotalSteps] = useState<number>(0);
  const [summary, setSummary] = useState<GenerationSummary | null>(null);

  // Modals & Drawers State
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isMappingOpen, setIsMappingOpen] = useState<boolean>(false);
  const [isHelpOpen, setIsHelpOpen] = useState<boolean>(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  // Configuration & Custom Templates State
  const [config, setConfig] = useState<ParserConfig>({
    ceit_prefix_map: {},
    known_lab_subjects: [],
    program_aliases: {},
    roster_keywords: { name_tokens: [], id_tokens: [] },
    schedule_config: { fallback_instructor: '', fallback_college: '', fallback_semester: '' },
  });
  const [customTemplates, setCustomTemplates] = useState<CustomTemplate[]>([]);

  // Toast Helper
  const showToast = useCallback((type: ToastMessage['type'], title: string, message: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Telemetry Bindings
  useEffect(() => {
    window.updateProgress = (percent, statusText, step, total) => {
      setProgressPercent(percent);
      setProgressStatus(statusText);
      setCurrentStep(step);
      setTotalSteps(total);
      setIsGenerating(percent < 100);
    };

    window.generationComplete = (resSummary) => {
      setIsGenerating(false);
      setSummary(resSummary);
      showToast('success', 'Generation Succeeded', `Generated ${resSummary.total_documents} documents.`);
    };

    window.generationError = (errMessage) => {
      setIsGenerating(false);
      showToast('error', 'Generation Error', errMessage);
    };

    return () => {
      delete window.updateProgress;
      delete window.generationComplete;
      delete window.generationError;
    };
  }, [showToast]);

  // Initial Data Fetch
  useEffect(() => {
    const initData = async () => {
      try {
        const loadedCfg = await pywebviewService.getParserConfig();
        if (loadedCfg) setConfig(loadedCfg);
        const loadedTemplates = await pywebviewService.getCustomTemplates();
        if (loadedTemplates) setCustomTemplates(loadedTemplates);
      } catch (e: any) {
        console.warn('Initial data load error:', e);
      }
    };
    initData();
  }, []);

  // Update File Estimate whenever relevant parameters change
  useEffect(() => {
    if (!schedulePath || rosters.length === 0) {
      setEstimate(null);
      return;
    }
    const updateEst = async () => {
      try {
        const est = await pywebviewService.getFileEstimate({
          schedule_path: schedulePath,
          rosters,
          output_dir: outputDir,
          start_date: startDate || undefined,
          end_date: endDate || undefined,
          class_configs: classConfigs,
        });
        setEstimate(est);
      } catch (err) {
        console.error('Failed to get estimate:', err);
      }
    };
    updateEst();
  }, [schedulePath, rosters, outputDir, startDate, endDate, classConfigs, customTemplates]);

  // Actions
  const handleBrowseSchedule = async () => {
    try {
      const res = await pywebviewService.browseSchedule();
      if (res.path) {
        setSchedulePath(res.path);
        setScheduleMetadata(res.metadata);
        setValidations(res.validation || []);
        showToast('info', 'Schedule Loaded', 'Ingested master schedule successfully.');
      }
    } catch (err: any) {
      showToast('error', 'File Error', err.message);
    }
  };

  const handleDropSchedule = async (file: File) => {
    try {
      const res = await pywebviewService.handleDroppedSchedule({
        filename: file.name,
        path: (file as any).path,
      });
      if (res.path) {
        setSchedulePath(res.path);
        setScheduleMetadata(res.metadata);
        setValidations(res.validation || []);
        showToast('info', 'Schedule Loaded', `Loaded ${file.name}`);
      }
    } catch (err: any) {
      showToast('error', 'Drop Error', err.message);
    }
  };

  const handleClearSchedule = () => {
    setSchedulePath('');
    setScheduleMetadata(null);
    setValidations([]);
  };

  const handleBrowseRosters = async () => {
    try {
      const res = await pywebviewService.browseRosters(classConfigs);
      setRosters(res.rosters);
      setValidations(res.validation || []);
      showToast('info', 'Rosters Updated', `${res.count} class rosters loaded.`);
    } catch (err: any) {
      showToast('error', 'Roster Error', err.message);
    }
  };

  const handleDropRosters = async (files: FileList | File[]) => {
    try {
      const payload = Array.from(files).map((f) => ({
        filename: f.name,
        path: (f as any).path,
      }));
      const res = await pywebviewService.handleDroppedRosters(payload, classConfigs);
      setRosters(res.rosters);
      setValidations(res.validation || []);
      showToast('info', 'Rosters Ingested', `Added ${payload.length} files.`);
    } catch (err: any) {
      showToast('error', 'Drop Error', err.message);
    }
  };

  const handleRemoveRoster = async (index: number) => {
    try {
      const res = await pywebviewService.removeRoster(index, classConfigs);
      setRosters(res.rosters);
      setValidations(res.validation || []);
    } catch (err: any) {
      showToast('error', 'Remove Error', err.message);
    }
  };

  const handleClearAllRosters = () => {
    setRosters([]);
    setValidations([]);
  };

  const handleToggleLab = (key: string, hasLab: boolean) => {
    setClassConfigs((prev) => ({
      ...prev,
      [key]: {
        has_lab: hasLab,
        manual_roster_path: prev[key]?.manual_roster_path,
      },
    }));
  };

  const handleBrowseOutputDir = async () => {
    try {
      const res = await pywebviewService.browseOutputDir();
      if (res.path) {
        setOutputDir(res.path);
        showToast('info', 'Output Set', `Destination: ${res.path}`);
      }
    } catch (err: any) {
      showToast('error', 'Folder Error', err.message);
    }
  };

  const handleStartGeneration = async () => {
    if (!schedulePath) {
      showToast('warning', 'Missing Input', 'Please select a master schedule first.');
      return;
    }
    if (rosters.length === 0) {
      showToast('warning', 'Missing Input', 'Please add at least one student class roster.');
      return;
    }
    if (!outputDir) {
      showToast('warning', 'Missing Input', 'Please select a target destination folder.');
      return;
    }

    setIsGenerating(true);
    setProgressPercent(0);
    setProgressStatus('Initializing document generator pipeline...');
    try {
      await pywebviewService.startGeneration({
        schedule_path: schedulePath,
        rosters,
        output_dir: outputDir,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        class_configs: classConfigs,
      });
    } catch (err: any) {
      setIsGenerating(false);
      showToast('error', 'Execution Error', err.message);
    }
  };

  const handleCancelGeneration = async () => {
    try {
      await pywebviewService.cancelGeneration();
      setIsGenerating(false);
      showToast('warning', 'Cancelled', 'Generation cancelled by user.');
    } catch (err: any) {
      showToast('error', 'Cancel Error', err.message);
    }
  };

  const handleSaveConfig = async (newCfg: ParserConfig) => {
    try {
      const res = await pywebviewService.saveParserConfig(newCfg);
      if (res.status === 'success') {
        setConfig(newCfg);
        if (res.validation) setValidations(res.validation);
        showToast('success', 'Settings Saved', 'Curriculum configuration applied.');
      }
    } catch (err: any) {
      showToast('error', 'Config Error', err.message);
    }
  };

  const handleResetDefaults = async () => {
    if (confirm('Reset all curriculum and parser preferences to factory defaults?')) {
      const res = await pywebviewService.resetParserConfig();
      if (res.config) setConfig(res.config);
      if (res.validation) setValidations(res.validation);
      showToast('info', 'Defaults Restored', 'Reset to factory CEIT configuration.');
    }
  };

  const handleRefreshCustomTemplates = async () => {
    const list = await pywebviewService.getCustomTemplates();
    setCustomTemplates(list);
  };

  // Determine Stepper Active Step
  let stepperActive = 1;
  if (schedulePath) stepperActive = 2;
  if (schedulePath && rosters.length > 0) stepperActive = 3;
  if (schedulePath && rosters.length > 0 && outputDir) stepperActive = 4;

  const canGenerate = Boolean(schedulePath && rosters.length > 0 && outputDir && !isGenerating);

  return (
    <div className="min-h-screen flex flex-col bg-[var(--bg-app)] text-[var(--text-primary)]">
      {/* Top Navigation */}
      <Header
        isDark={isDark}
        onToggleTheme={toggleTheme}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenHelp={() => setIsHelpOpen(true)}
      />

      {/* Main Workflow Container */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <Stepper currentStep={stepperActive} />

        {/* Step 1: Schedule Ingestion */}
        <Step1Schedule
          schedulePath={schedulePath}
          metadata={scheduleMetadata}
          onBrowse={handleBrowseSchedule}
          onDropFile={handleDropSchedule}
          onClear={handleClearSchedule}
        />

        {/* Step 2: Student Rosters */}
        <Step2Rosters
          rosters={rosters}
          onBrowse={handleBrowseRosters}
          onDropFiles={handleDropRosters}
          onRemoveRoster={handleRemoveRoster}
          onClearAll={handleClearAllRosters}
        />

        {/* Step 3: Class Review & Subject Type Selection */}
        <Step3ClassReview
          validations={validations}
          classConfigs={classConfigs}
          onToggleLab={handleToggleLab}
          onOpenMappingModal={() => setIsMappingOpen(true)}
        />

        {/* Step 4: Semester Date Boundaries */}
        <Step4DateBoundaries
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
        />

        {/* Step 5: Target Output Destination */}
        <Step5OutputFolder outputDir={outputDir} onBrowse={handleBrowseOutputDir} />

        {/* Step 6: Execution & Progress Telemetry */}
        <Step6Execution
          isGenerating={isGenerating}
          progressPercent={progressPercent}
          progressStatus={progressStatus}
          currentStep={currentStep}
          totalSteps={totalSteps}
          estimate={estimate}
          canGenerate={canGenerate}
          onStart={handleStartGeneration}
          onCancel={handleCancelGeneration}
        />
      </main>

      {/* Modals & Overlays */}
      <RosterMappingModal
        isOpen={isMappingOpen}
        onClose={() => setIsMappingOpen(false)}
        validations={validations}
        availableRosters={rosters}
        classConfigs={classConfigs}
        onSaveMapping={setClassConfigs}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={config}
        customTemplates={customTemplates}
        onSaveConfig={handleSaveConfig}
        onResetDefaults={handleResetDefaults}
        onExportConfig={() => pywebviewService.exportParserConfig()}
        onImportConfig={async () => {
          const res = await pywebviewService.importParserConfig();
          if (res.status === 'success') {
            const cfg = await pywebviewService.getParserConfig();
            setConfig(cfg);
            showToast('success', 'Config Imported', 'Configuration loaded from file.');
          }
        }}
        onRefreshCustomTemplates={handleRefreshCustomTemplates}
        onShowToast={showToast}
      />

      <HelpDrawer isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} />

      <CompletionModal summary={summary} onClose={() => setSummary(null)} />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
};

export default App;
