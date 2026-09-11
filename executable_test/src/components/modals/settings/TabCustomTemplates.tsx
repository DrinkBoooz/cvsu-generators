import React, { useState } from 'react';
import { UploadCloud, CheckCircle2, AlertTriangle, Trash2, Plus, Sparkles, FileText, ToggleLeft, ToggleRight } from 'lucide-react';
import { CustomTemplate, TemplateRecipe } from '../../../types/api';
import { pywebviewService } from '../../../services/pywebview';

interface TabCustomTemplatesProps {
  customTemplates: CustomTemplate[];
  onRefreshTemplates: () => void;
  onShowToast: (type: 'success' | 'warning' | 'error' | 'info', title: string, msg: string) => void;
}

export const TabCustomTemplates: React.FC<TabCustomTemplatesProps> = ({
  customTemplates,
  onRefreshTemplates,
  onShowToast,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isInspecting, setIsInspecting] = useState(false);
  const [inspectedFile, setInspectedFile] = useState<string | null>(null);
  const [recipe, setRecipe] = useState<TemplateRecipe | null>(null);
  const [customTitle, setCustomTitle] = useState('');
  const [customSuffix, setCustomSuffix] = useState('');

  const handleInspect = async (path: string) => {
    setIsInspecting(true);
    try {
      const res = await pywebviewService.inspectCustomTemplate(path);
      if (res.status === 'success' && res.recipe) {
        setInspectedFile(res.file_path || path);
        setRecipe(res.recipe);
        setCustomTitle(res.recipe.title);
        setCustomSuffix(res.recipe.suffix);
        onShowToast('success', 'Template Analyzed', `Heuristic analysis completed with ${res.recipe.confidence}% confidence.`);
      } else {
        onShowToast('error', 'Inspection Failed', res.message || 'Could not analyze template file.');
      }
    } catch (err: any) {
      onShowToast('error', 'Inspection Error', err.message || 'Error inspecting template');
    } finally {
      setIsInspecting(false);
    }
  };

  const handleBrowseTemplate = async () => {
    const res = await pywebviewService.browseCustomTemplate();
    if (res.path) {
      handleInspect(res.path);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (!file.name.endsWith('.docx')) {
        onShowToast('warning', 'Invalid File', 'Only Word (.docx) documents can be analyzed.');
        return;
      }
      const res = await pywebviewService.handleDroppedCustomTemplate({
        filename: file.name,
        path: (file as any).path,
      });
      if (res.path) {
        handleInspect(res.path);
      }
    }
  };

  const handleSaveCustomTemplate = async () => {
    if (!inspectedFile || !recipe || !customTitle.trim() || !customSuffix.trim()) return;
    try {
      const res = await pywebviewService.saveCustomTemplate(
        inspectedFile,
        customTitle.trim(),
        customSuffix.trim().toUpperCase(),
        recipe,
        true
      );
      if (res.status === 'success') {
        onShowToast('success', 'Custom Template Saved', `Registered "${customTitle}" as an active generator.`);
        setInspectedFile(null);
        setRecipe(null);
        onRefreshTemplates();
      } else {
        onShowToast('error', 'Save Failed', res.message || 'Could not save template.');
      }
    } catch (err: any) {
      onShowToast('error', 'Save Error', err.message);
    }
  };

  const handleToggle = async (id: string, current: boolean) => {
    await pywebviewService.toggleCustomTemplate(id, !current);
    onRefreshTemplates();
  };

  const handleDelete = async (id: string) => {
    if (confirm(`Remove custom template "${id}" from generators?`)) {
      await pywebviewService.deleteCustomTemplate(id);
      onShowToast('info', 'Template Removed', `Deleted custom template ${id}`);
      onRefreshTemplates();
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
            Deterministic Heuristic Template Analyzer
          </h4>
          <p className="text-[11px] text-[var(--text-muted)]">
            Drop any Word (.docx) document. The in-app heuristic engine inspects tables, colons, and tag placeholders in &lt; 20ms without external AI.
          </p>
        </div>
      </div>

      {/* Dropzone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        onClick={handleBrowseTemplate}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 ${
          isDragOver
            ? 'border-emerald-500 bg-emerald-500/5 scale-[1.01]'
            : 'border-[var(--border-subtle)] hover:border-emerald-500/50 hover:bg-[var(--surface-subtle)]'
        }`}
      >
        <div className="w-10 h-10 mx-auto mb-2 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
          <UploadCloud className="w-5 h-5" />
        </div>
        <p className="text-sm font-semibold text-[var(--text-primary)]">
          Drop new .docx template here, or{' '}
          <span className="text-emerald-600 dark:text-emerald-400 underline">Browse File</span>
        </p>
        <p className="text-xs text-[var(--text-muted)] mt-1">
          Instant offline heuristic detection of student tables and header coordinates
        </p>
      </div>

      {/* Live Inspection Card */}
      {recipe && (
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 space-y-4 animate-fade-in">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-emerald-500" />
              <span className="text-xs font-bold text-[var(--text-primary)]">
                Heuristic Inspection Card
              </span>
            </div>
            <div className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{recipe.confidence}% Confidence</span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-[var(--text-secondary)] mb-1">
                Document Form Title
              </label>
              <input
                type="text"
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs text-[var(--text-primary)] font-medium"
              />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[var(--text-secondary)] mb-1">
                File Output Suffix
              </label>
              <input
                type="text"
                value={customSuffix}
                onChange={(e) => setCustomSuffix(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-xs font-bold uppercase text-[var(--text-primary)]"
              />
            </div>
          </div>

          {/* Roster & Binding Preview */}
          <div className="p-3 rounded-lg bg-[var(--surface-elevated)] border border-[var(--border-subtle)] text-[11px] space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[var(--text-muted)]">Roster Table:</span>
              <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                {recipe.roster_table ? `Table #${recipe.roster_table.table_index + 1} (${recipe.roster_table.total_cols} columns)` : 'Not Detected'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[var(--text-muted)]">Bound Header Fields:</span>
              <span className="font-medium text-[var(--text-primary)]">
                {recipe.summary?.detected_fields?.join(', ') || 'None'}
              </span>
            </div>
          </div>

          <button
            onClick={handleSaveCustomTemplate}
            className="w-full py-2 px-4 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 shadow-md shadow-emerald-500/20 transition-colors flex items-center justify-center space-x-1.5"
          >
            <Plus className="w-4 h-4" />
            <span>Save & Register as In-App Generator</span>
          </button>
        </div>
      )}

      {/* Registered Templates List */}
      <div className="space-y-3">
        <h5 className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
          Registered Custom Templates ({customTemplates.length})
        </h5>

        {customTemplates.length === 0 ? (
          <p className="text-xs text-[var(--text-muted)] p-4 text-center rounded-xl bg-[var(--surface-subtle)] border border-[var(--border-subtle)]">
            No custom templates registered yet. Drop any .docx file above to add one!
          </p>
        ) : (
          <div className="space-y-2">
            {customTemplates.map((t) => (
              <div
                key={t.id}
                className="p-3 rounded-xl bg-[var(--surface-elevated)] border border-[var(--border-subtle)] flex items-center justify-between gap-3 hover:border-emerald-500/30 transition-colors"
              >
                <div className="flex items-center space-x-3 truncate">
                  <FileText className="w-4 h-4 text-emerald-500 shrink-0" />
                  <div className="truncate">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-bold text-[var(--text-primary)] truncate">
                        {t.title}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--surface-subtle)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
                        _{t.suffix}.docx
                      </span>
                    </div>
                    <span className="text-[10px] text-[var(--text-muted)] truncate block">
                      {t.filename}
                    </span>
                  </div>
                </div>

                <div className="flex items-center space-x-2 shrink-0">
                  <button
                    onClick={() => handleToggle(t.id, t.enabled)}
                    className="p-1 rounded text-xs font-semibold text-[var(--text-secondary)] hover:text-emerald-500 transition-colors"
                    title={t.enabled ? 'Disable Template' : 'Enable Template'}
                  >
                    {t.enabled ? (
                      <ToggleRight className="w-6 h-6 text-emerald-500" />
                    ) : (
                      <ToggleLeft className="w-6 h-6 text-[var(--text-muted)]" />
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(t.id)}
                    className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
                    title="Delete Custom Template"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
