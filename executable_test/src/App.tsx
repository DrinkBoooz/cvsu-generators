import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Header } from './components/Header';
import { Stepper } from './components/Stepper';
import { Step1Schedule } from './components/steps/Step1Schedule';
import { Step2Rosters } from './components/steps/Step2Rosters';
import { Step3ClassReview } from './components/steps/Step3ClassReview';
import { Step4DateBoundaries } from './components/steps/Step4DateBoundaries';
import { Step5OutputFolder } from './components/steps/Step5OutputFolder';
import { Step6Execution } from './components/steps/Step6Execution';
import { BottomActionBar } from './components/BottomActionBar';
import { RosterMappingModal } from './components/modals/RosterMappingModal';
import { SettingsModal } from './components/modals/SettingsModal';
import { HelpDrawer } from './components/HelpDrawer';
import { CompletionModal } from './components/CompletionModal';
import { ToastContainer } from './components/ToastContainer';
import { useTheme } from './hooks/useTheme';
import { pywebviewService } from './services/pywebview';
import {
  ScheduleMetadata,
  RosterConfigMap,
  ParserConfig,
  CustomTemplate,
  FileEstimate,
  GenerationSummary,
  ToastMessage,
  DetectedClass,
  RosterValidationReport,
} from './types/api';

export const App: React.FC = () => {
  const { isDark, toggleTheme } = useTheme();

  // Primary Workflow State
  const [schedulePath, setSchedulePath] = useState<string>('');
  const [scheduleMetadata, setScheduleMetadata] = useState<ScheduleMetadata | null>(null);
  const [rosters, setRosters] = useState<string[]>([]);
  const [rosterReports, setRosterReports] = useState<RosterValidationReport[]>([]);
  const [detectedClasses, setDetectedClasses] = useState<DetectedClass[]>([]);
  const [selectedClassIds, setSelectedClassIds] = useState<string[]>([]);
  const [typeOverrides, setTypeOverrides] = useState<Record<string, string>>({});
  const [classConfigs, setClassConfigs] = useState<RosterConfigMap>({});
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [outputDir, setOutputDir] = useState<string>('');

  // Engine toggles
  const [engines, setEngines] = useState<{ attendance: boolean; ceit: boolean; grades: boolean }>({
    attendance: true,
    ceit: true,
    grades: true,
  });

  // Execution & Telemetry State
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [progressStatus, setProgressStatus] = useState<string>('');
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [totalSteps, setTotalSteps] = useState<number>(0);
  const [summary, setSummary] = useState<GenerationSummary | null>(null);

  // Modals & Overlays State
  const [isSettingsOpen, setIsSettingsOpen] = useState<boolean>(false);
  const [isMappingOpen, setIsMappingOpen] = useState<boolean>(false);
  const [mappingFilename, setMappingFilename] = useState<string>('');
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

  // Helper to re-detect classes from backend
  const refreshClasses = useCallback(async (currentConfigs?: RosterConfigMap) => {
    try {
      const classes = await pywebviewService.detectClasses(currentConfigs || classConfigs);
      setDetectedClasses(classes || []);
      // Automatically select all detected classes by default
      if (classes && classes.length > 0) {
        setSelectedClassIds(classes.map((c) => c.id || `${c.course_sec}_${c.schedule_code}`));
      }
    } catch (err) {
      console.error('Failed to detect classes:', err);
    }
  }, [classConfigs]);

  // Telemetry & Python Bridge Bindings (Invoked by Python via PyWebView evaluate_js)
  useEffect(() => {
    window.onScheduleLoaded = async (res) => {
      if (res && res.path) {
        setSchedulePath(res.path);
        setScheduleMetadata(res.metadata);
        if (res.validation) setRosterReports(res.validation);
        await refreshClasses();
        showToast(
          'success',
          'Schedule Loaded',
          `Loaded schedule for ${res.metadata?.instructor || 'Faculty'}`
        );
      }
    };

    window.onRostersLoaded = async (res) => {
      if (res) {
        setRosters(res.rosters || []);
        setRosterReports(res.validation || []);
        await refreshClasses();
        showToast('success', 'Rosters Loaded', `${res.rosters?.length || 0} student roster files loaded.`);
      }
    };

    window.onGenerationProgress = (info) => {
      setProgressPercent(info.percent);
      setProgressStatus(`${info.current_class || 'Class'}: ${info.current_task || 'Processing'}`);
      setCurrentStep(info.step);
      setTotalSteps(info.total_steps);
      setIsGenerating(info.percent < 100);
    };

    window.onGenerationComplete = (payload) => {
      setIsGenerating(false);
      setProgressPercent(100);
      if (payload.status === 'cancelled') {
        showToast('warning', 'Cancelled', payload.message || 'Generation cancelled by user.');
      } else if (payload.status === 'error') {
        showToast('error', 'Generation Error', payload.message || 'Generation failed.');
      } else {
        const totalDocs = payload.stats?.generated || 0;
        setSummary({
          total_documents: totalDocs,
          sections_processed: detectedClasses.length,
          output_directory: payload.output_dir || outputDir,
          generated_files: [],
        });
        showToast('success', 'Generation Succeeded', payload.message || `Generated ${totalDocs} documents.`);
      }
    };

    window.onGenerationError = () => {
      setIsGenerating(false);
      showToast('error', 'Generation Error', 'A fatal error occurred during generation.');
    };

    return () => {
      delete window.onScheduleLoaded;
      delete window.onRostersLoaded;
      delete window.onGenerationProgress;
      delete window.onGenerationComplete;
      delete window.onGenerationError;
    };
  }, [refreshClasses, showToast, detectedClasses.length, outputDir]);

  // Window-level Drag and Drop Listeners for Microsoft Edge WebView2
  useEffect(() => {
    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
    };

    const handleDrop = async (e: DragEvent) => {
      e.preventDefault();
      const files = e.dataTransfer ? e.dataTransfer.files : null;
      if (!files || files.length === 0) return;

      const fileList = Array.from(files);
      const scheduleFiles = fileList.filter((f) => {
        const ext = f.name.split('.').pop()?.toLowerCase();
        return ext === 'xls' || ext === 'xlsx' || ext === 'xlsm';
      });
      const rosterFiles = fileList.filter((f) => {
        const ext = f.name.split('.').pop()?.toLowerCase();
        return ext === 'csv' || (!f.name.toLowerCase().includes('schedule') && (ext === 'xlsx' || ext === 'xls'));
      });

      // If dropped schedule file
      if (scheduleFiles.length > 0 && !schedulePath) {
        const f = scheduleFiles[0];
        const path = (f as any).pywebviewFullPath || (f as any).path;
        if (path) {
          const res = await pywebviewService.handleDroppedSchedule(f.name, path);
          if (res && res.path) {
            setSchedulePath(res.path);
            setScheduleMetadata(res.metadata);
            if (res.validation) setRosterReports(res.validation);
            await refreshClasses();
            showToast('success', 'Schedule Loaded', `Loaded ${f.name}`);
          }
        }
      }

      // If dropped roster files
      if (rosterFiles.length > 0) {
        const payloads = rosterFiles.map((f) => ({
          filename: f.name,
          path: (f as any).pywebviewFullPath || (f as any).path || null,
          data: null,
        }));
        const res = await pywebviewService.handleDroppedRosters(payloads, classConfigs);
        if (res) {
          setRosters(res.rosters || []);
          setRosterReports(res.validation || []);
          await refreshClasses();
          showToast('success', 'Rosters Ingested', `Added ${payloads.length} roster files.`);
        }
      }
    };

    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('drop', handleDrop);

    return () => {
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('drop', handleDrop);
    };
  }, [schedulePath, classConfigs, refreshClasses, showToast]);

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

  // Calculate File Estimate dynamically
  const estimate: FileEstimate | null = useMemo(() => {
    const activeCustom = customTemplates.filter((t) => t.enabled).length;
    return pywebviewService.calculateFileEstimate(
      selectedClassIds.length,
      engines,
      activeCustom,
      startDate || undefined,
      endDate || undefined
    );
  }, [selectedClassIds.length, engines, customTemplates, startDate, endDate]);

  // Primary Actions
  const handleBrowseSchedule = async () => {
    try {
      const res = await pywebviewService.browseSchedule();
      if (res && res.path) {
        setSchedulePath(res.path);
        setScheduleMetadata(res.metadata);
        if (res.validation) setRosterReports(res.validation);
        await refreshClasses();
        showToast(
          'success',
          'Schedule Loaded',
          `Loaded schedule for ${res.metadata?.instructor || 'Faculty'}`
        );
      }
    } catch (err: any) {
      showToast('error', 'File Error', err.message || 'Failed to select schedule.');
    }
  };

  const handleDropScheduleFile = async (file: File) => {
    try {
      const path = (file as any).pywebviewFullPath || (file as any).path;
      const res = await pywebviewService.handleDroppedSchedule(file.name, path);
      if (res && res.path) {
        setSchedulePath(res.path);
        setScheduleMetadata(res.metadata);
        if (res.validation) setRosterReports(res.validation);
        await refreshClasses();
        showToast('success', 'Schedule Loaded', `Loaded ${file.name}`);
      }
    } catch (err: any) {
      showToast('error', 'Drop Error', err.message || 'Failed to process dropped schedule.');
    }
  };

  const handleClearSchedule = () => {
    setSchedulePath('');
    setScheduleMetadata(null);
    setDetectedClasses([]);
    setSelectedClassIds([]);
    showToast('info', 'Schedule Reset', 'Master schedule cleared.');
  };

  const handleBrowseRosters = async () => {
    try {
      const res = await pywebviewService.browseRosters(classConfigs);
      if (res) {
        setRosters(res.rosters || []);
        setRosterReports(res.validation || []);
        await refreshClasses();
        showToast('success', 'Rosters Loaded', `${res.rosters?.length || 0} student roster files loaded.`);
      }
    } catch (err: any) {
      showToast('error', 'Roster Error', err.message || 'Failed to load rosters.');
    }
  };

  const handleDropRosterFiles = async (files: FileList | File[]) => {
    try {
      const payload = Array.from(files).map((f) => ({
        filename: f.name,
        path: (f as any).pywebviewFullPath || (f as any).path || null,
        data: null,
      }));
      const res = await pywebviewService.handleDroppedRosters(payload, classConfigs);
      if (res) {
        setRosters(res.rosters || []);
        setRosterReports(res.validation || []);
        await refreshClasses();
        showToast('success', 'Rosters Ingested', `Added ${payload.length} files.`);
      }
    } catch (err: any) {
      showToast('error', 'Drop Error', err.message || 'Failed to drop rosters.');
    }
  };

  const handleRemoveRoster = async (index: number) => {
    try {
      const res = await pywebviewService.removeRoster(index, classConfigs);
      if (res) {
        setRosters(res.rosters || []);
        setRosterReports(res.validation || []);
        await refreshClasses();
      }
    } catch (err: any) {
      showToast('error', 'Remove Error', err.message || 'Failed to remove roster.');
    }
  };

  const handleClearAllRosters = async () => {
    try {
      const res = await pywebviewService.clearRosters();
      setRosters([]);
      setRosterReports([]);
      setDetectedClasses([]);
      setSelectedClassIds([]);
      showToast('info', 'Rosters Cleared', 'All student rosters removed.');
    } catch (err: any) {
      showToast('error', 'Clear Error', err.message || 'Failed to clear rosters.');
    }
  };

  const handleToggleClassSelection = (classId: string) => {
    setSelectedClassIds((prev) =>
      prev.includes(classId) ? prev.filter((id) => id !== classId) : [...prev, classId]
    );
  };

  const handleSelectAllClasses = (select: boolean) => {
    if (select) {
      setSelectedClassIds(detectedClasses.map((c) => c.id || `${c.course_sec}_${c.schedule_code}`));
    } else {
      setSelectedClassIds([]);
    }
  };

  const handleTypeOverrideChange = (classId: string, type: 'lecture_lab' | 'lecture_only') => {
    setTypeOverrides((prev) => ({
      ...prev,
      [classId]: type,
    }));
  };

  const handleToggleEngine = (engine: 'attendance' | 'ceit' | 'grades') => {
    setEngines((prev) => ({ ...prev, [engine]: !prev[engine] }));
  };

  const handleBrowseOutputDir = async () => {
    try {
      const res = await pywebviewService.browseOutputDir();
      if (res.path) {
        setOutputDir(res.path);
        showToast('info', 'Output Set', `Destination: ${res.path}`);
      }
    } catch (err: any) {
      showToast('error', 'Folder Error', err.message || 'Failed to select destination.');
    }
  };

  const handleStartGeneration = async () => {
    if (!schedulePath) {
      showToast('warning', 'Missing Schedule', 'Please select or drop a master schedule first.');
      return;
    }
    if (rosters.length === 0) {
      showToast('warning', 'Missing Rosters', 'Please add at least one student roster file.');
      return;
    }
    if (!outputDir) {
      showToast('warning', 'Missing Output', 'Please choose a target destination folder.');
      return;
    }
    if (selectedClassIds.length === 0) {
      showToast('warning', 'No Classes Selected', 'Please check at least one class to compile.');
      return;
    }

    setIsGenerating(true);
    setProgressPercent(0);
    setProgressStatus('Initializing document compilation pipeline...');

    const dateOverrides = startDate || endDate ? { start_date: startDate, end_date: endDate } : undefined;

    try {
      await pywebviewService.runGeneration(
        typeOverrides,
        dateOverrides,
        selectedClassIds,
        engines,
        classConfigs
      );
    } catch (err: any) {
      setIsGenerating(false);
      showToast('error', 'Execution Error', err.message || 'Failed to start generation.');
    }
  };

  const handleCancelGeneration = async () => {
    try {
      await pywebviewService.cancelGeneration();
    } catch (err: any) {
      showToast('error', 'Cancel Error', err.message || 'Failed to cancel generation.');
    }
  };

  const handleSaveConfig = async (newCfg: ParserConfig) => {
    try {
      const res = await pywebviewService.saveParserConfig(newCfg);
      if (res.status === 'success') {
        setConfig(newCfg);
        if (res.validation) setRosterReports(res.validation);
        if (res.detected_classes) setDetectedClasses(res.detected_classes);
        showToast('success', 'Settings Saved', 'Curriculum configuration applied.');
      }
    } catch (err: any) {
      showToast('error', 'Config Error', err.message || 'Failed to save config.');
    }
  };

  const handleResetDefaults = async () => {
    if (confirm('Reset all curriculum and parser preferences to factory defaults?')) {
      const res = await pywebviewService.resetParserConfig();
      if (res.config) setConfig(res.config);
      if (res.validation) setRosterReports(res.validation);
      if (res.detected_classes) setDetectedClasses(res.detected_classes);
      showToast('info', 'Defaults Restored', 'Reset to factory CEIT configuration.');
    }
  };

  const handleRefreshCustomTemplates = async () => {
    const list = await pywebviewService.getCustomTemplates();
    setCustomTemplates(list);
  };

  // Determine Stepper Active Step based on completion
  let stepperActive = 1;
  if (schedulePath) stepperActive = 2;
  if (schedulePath && rosters.length > 0) stepperActive = 3;
  if (schedulePath && rosters.length > 0 && selectedClassIds.length > 0) stepperActive = 4;
  if (schedulePath && rosters.length > 0 && outputDir) stepperActive = 6;

  const canGenerate = Boolean(
    schedulePath && rosters.length > 0 && outputDir && selectedClassIds.length > 0 && !isGenerating
  );

  return (
    <div className="app-shell" data-bs-theme={isDark ? 'dark' : 'light'}>
      <Header
        isDark={isDark}
        onToggleTheme={toggleTheme}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenHelp={() => setIsHelpOpen(true)}
      />

      <div className="main-content-layout">
        <Stepper
          hasSchedule={Boolean(schedulePath)}
          rosterCount={rosters.length}
          classCount={selectedClassIds.length}
          hasOutput={Boolean(outputDir)}
          isGenerating={isGenerating}
        />

        <div className="dashboard-grid">
          {/* LEFT COLUMN: Input Deck (Schedule & Rosters) */}
          <div className="dashboard-col col-inputs">
            <Step1Schedule
              schedulePath={schedulePath}
              metadata={scheduleMetadata}
              onBrowse={handleBrowseSchedule}
              onDropFile={handleDropScheduleFile}
              onClear={handleClearSchedule}
            />

            <Step2Rosters
              rosters={rosters}
              validations={rosterReports}
              onBrowse={handleBrowseRosters}
              onDropFiles={handleDropRosterFiles}
              onRemoveRoster={handleRemoveRoster}
              onClearAll={handleClearAllRosters}
              onOpenMappingModal={(fn) => {
                setMappingFilename(fn);
                setIsMappingOpen(true);
              }}
            />
          </div>

          {/* RIGHT COLUMN: Control Deck (Packages, Classes, Dates, Output) */}
          <div className="dashboard-col col-controls">
            <Step3ClassReview
              detectedClasses={detectedClasses}
              selectedClassIds={selectedClassIds}
              onToggleClassSelection={handleToggleClassSelection}
              onSelectAllClasses={handleSelectAllClasses}
              typeOverrides={typeOverrides}
              onTypeOverrideChange={handleTypeOverrideChange}
              engines={engines}
              onToggleEngine={handleToggleEngine}
              onOpenMappingModal={() => setIsMappingOpen(true)}
            />

            <Step4DateBoundaries
              startDate={startDate}
              endDate={endDate}
              onStartDateChange={setStartDate}
              onEndDateChange={setEndDate}
              semesterAy={scheduleMetadata?.semester || scheduleMetadata?.semester_ay}
            />

            <Step5OutputFolder
              outputPath={outputDir}
              onBrowse={handleBrowseOutputDir}
              onOpenFolder={() => pywebviewService.openOutputFolder()}
            />
          </div>
        </div>

        {/* STEP 6: Initialize Workflow & Telemetry Progress */}
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
      </div>

      {/* Floating Bottom Action Capsule Dock */}
      <BottomActionBar
        hasSchedule={Boolean(schedulePath)}
        rosterCount={rosters.length}
        hasOutput={Boolean(outputDir)}
        classCount={selectedClassIds.length}
        isGenerating={isGenerating}
        progressPercent={progressPercent}
        progressMessage={progressStatus}
        onGenerate={handleStartGeneration}
        onCancel={handleCancelGeneration}
      />

      {/* Modals & Overlays */}
      <RosterMappingModal
        isOpen={isMappingOpen}
        onClose={() => {
          setIsMappingOpen(false);
          setMappingFilename('');
        }}
        validations={[]}
        availableRosters={rosters}
        classConfigs={classConfigs}
        onSaveMapping={async (newMap) => {
          setClassConfigs(newMap);
          await refreshClasses(newMap);
        }}
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
            if (res.detected_classes) setDetectedClasses(res.detected_classes);
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
