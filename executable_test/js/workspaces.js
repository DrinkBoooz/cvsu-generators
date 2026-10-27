// ── Semester Workspaces & Smart Ingest Router ───────────────────────────────

let currentRosterDiffPayload = null;

function updateWorkspaceHeaderDisplay() {
  const select = document.getElementById("selectWorkspace");
  const btnSave = document.getElementById("btnSaveWorkspace");
  if (!btnSave) return;

  const activeId = state?.activeWorkspaceId || (select && select.value) || null;
  const activeName = state?.activeWorkspaceName || (select && select.value ? select.options[select.selectedIndex]?.text : null);

  if (activeId && activeName) {
    btnSave.title = `Update current workspace "${activeName}"`;
    btnSave.setAttribute("aria-label", `Update current workspace "${activeName}"`);
  } else {
    btnSave.title = "Save active semester state as new workspace";
    btnSave.setAttribute("aria-label", "Save active semester state as new workspace");
  }
}

function renderWorkspaceActiveBanner() {
  const label = document.getElementById("workspaceActiveNameLabel");
  const btnUpdate = document.getElementById("btnUpdateActiveWorkspace");
  const btnDelete = document.getElementById("btnDeleteActiveWorkspace");
  const activeId = state?.activeWorkspaceId;
  const activeName = state?.activeWorkspaceName;

  if (activeId && activeName) {
    if (label) label.textContent = activeName;
    if (btnUpdate) {
      btnUpdate.classList.remove("d-none");
      btnUpdate.textContent = `💾 Update "${activeName}"`;
      btnUpdate.title = `Overwrite and update "${activeName}" with current session state`;
    }
    if (btnDelete) {
      btnDelete.classList.remove("d-none");
      btnDelete.title = `Delete workspace "${activeName}"`;
    }
  } else {
    if (label) label.innerHTML = `<em>Default Workspace (Unsaved)</em>`;
    if (btnUpdate) {
      btnUpdate.classList.add("d-none");
    }
    if (btnDelete) {
      btnDelete.classList.add("d-none");
    }
  }
}

async function loadWorkspaceListUI() {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.list_workspaces) {
    return;
  }
  try {
    const workspaces = await window.pywebview.api.list_workspaces();
    const select = document.getElementById("selectWorkspace");
    const container = document.getElementById("workspaceListContainer");

    // Populate dropdown
    if (select) {
      const currentVal = select.value || state?.activeWorkspaceId || "";
      select.innerHTML = `<option value="">Default Workspace</option>`;
      (workspaces || []).forEach((ws) => {
        const opt = document.createElement("option");
        opt.value = ws.workspace_id;
        opt.textContent = ws.name || ws.workspace_id;
        if (ws.workspace_id === currentVal) {
          opt.selected = true;
          if (state) {
            state.activeWorkspaceId = ws.workspace_id;
            state.activeWorkspaceName = ws.name || ws.workspace_id;
          }
        }
        select.appendChild(opt);
      });
      updateWorkspaceHeaderDisplay();
    }

    // Populate Manager List
    if (container) {
      if (!workspaces || workspaces.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 16px; font-size: 11.5px;">No saved semester workspaces yet. Create one above!</div>`;
        return;
      }
      container.innerHTML = "";
      workspaces.forEach((ws) => {
        const item = document.createElement("div");
        item.className = "workspace-card-item";
        const dateStr = ws.updated_at ? new Date(ws.updated_at).toLocaleDateString() : "";
        const isActive = state?.activeWorkspaceId === ws.workspace_id;
        item.innerHTML = `
          <div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-weight: 700; font-size: 13px; color: var(--text-primary);">${escapeHTML(ws.name || ws.workspace_id)}</span>
              ${isActive ? `<span class="badge" style="background: rgba(34, 197, 94, 0.15); color: var(--accent-emerald); font-size: 10px; padding: 1px 6px; border-radius: 4px;">Active</span>` : ""}
            </div>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
              ${ws.rosters_count || 0} Rosters · Updated ${escapeHTML(dateStr)}
            </div>
          </div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <button type="button" class="btn-primary-compact" style="font-size: 11px; padding: 4px 10px;" onclick="loadWorkspaceById('${escapeHTML(ws.workspace_id)}')">
              Load
            </button>
            <button type="button" class="nav-btn" style="font-size: 11px; padding: 4px 8px; color: var(--accent-rose); border-color: rgba(239, 68, 68, 0.25);" title="Delete workspace" aria-label="Delete workspace" onclick="deleteWorkspaceById('${escapeHTML(ws.workspace_id)}', '${escapeHTML(ws.name)}')">
              🗑️ Delete
            </button>
          </div>
        `;
        container.appendChild(item);
      });
    }
  } catch (err) {
    console.error("Failed to load workspaces list:", err);
  }
}

async function onWorkspaceSelectChange(workspaceId) {
  if (!workspaceId) {
    if (state) {
      state.activeWorkspaceId = null;
      state.activeWorkspaceName = "Default Workspace";
    }
    updateWorkspaceHeaderDisplay();
    renderWorkspaceActiveBanner();
    showToast("Default Workspace", "Switched to Default Workspace", "info");
    return;
  }
  await loadWorkspaceById(workspaceId);
}

async function loadWorkspaceById(workspaceId) {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.load_workspace) {
    return;
  }
  try {
    const res = await window.pywebview.api.load_workspace(workspaceId);
    if (res && res.status === "success") {
      const ws = res.workspace;
      state.schedulePath = ws.schedule_path || "";
      state.rosters = ws.rosters || [];
      state.rosterConfigs = ws.roster_configs || {};
      state.outputDir = ws.output_dir || "";
      state.activeWorkspaceId = ws.workspace_id;
      state.activeWorkspaceName = ws.name || ws.workspace_id;

      if (state.outputDir) {
        const outDisplay = document.getElementById("outputDisplay");
        if (outDisplay) outDisplay.value = state.outputDir;
      }

      renderScheduleStatus();
      renderRosterStatus();
      await refreshClassDetection();
      updateStepperStatus();
      updateFileEstimate();
      closeWorkspaceModal();

      const select = document.getElementById("selectWorkspace");
      if (select) select.value = ws.workspace_id;
      updateWorkspaceHeaderDisplay();
      renderWorkspaceActiveBanner();

      showToast("Workspace Loaded", `Loaded snapshot for ${ws.name}`, "success");
    } else {
      showToast("Load Failed", res?.message || "Failed to load workspace", "error");
    }
  } catch (err) {
    console.error("Error loading workspace:", err);
    showToast("Error", "Could not load workspace", "error");
  }
}

function openWorkspaceModal() {
  const modal = document.getElementById("modalWorkspaceBackdrop");
  if (modal) {
    modal.classList.remove("d-none");
    renderWorkspaceActiveBanner();
    loadWorkspaceListUI();
  }
}

function closeWorkspaceModal() {
  const modal = document.getElementById("modalWorkspaceBackdrop");
  if (modal) modal.classList.add("d-none");
}

async function promptSaveCurrentWorkspace() {
  const select = document.getElementById("selectWorkspace");
  const activeId = state?.activeWorkspaceId || (select && select.value) || null;
  const activeName = state?.activeWorkspaceName || (select && select.value ? select.options[select.selectedIndex]?.text : null);

  if (activeId && activeName) {
    // Active workspace is loaded: directly update it!
    await executeSaveWorkspace(activeName, activeId);
  } else {
    // On Default Workspace: prompt for a name to create a new workspace
    const name = prompt("Enter a name for this Semester Workspace (e.g. '1st Sem AY 2026-2027'):", "");
    if (!name || !name.trim()) return;
    await executeSaveWorkspace(name.trim(), null);
  }
}

async function saveCurrentWorkspaceFromUI() {
  const input = document.getElementById("inputWorkspaceName");
  const name = input ? input.value.trim() : "";
  if (!name) {
    showToast("Name Required", "Please enter a workspace name", "warning");
    return;
  }
  await executeSaveWorkspace(name, null);
  if (input) input.value = "";
}

async function updateActiveWorkspaceFromUI() {
  const activeId = state?.activeWorkspaceId;
  const activeName = state?.activeWorkspaceName;
  if (!activeId || !activeName) {
    showToast("No Active Workspace", "Please select a workspace to update, or save as new.", "info");
    return;
  }
  await executeSaveWorkspace(activeName, activeId);
}

async function executeSaveWorkspace(name, workspaceId = null) {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.save_workspace) {
    return;
  }
  try {
    const res = await window.pywebview.api.save_workspace(name, null, workspaceId);
    if (res && res.status === "success") {
      const isUpdate = Boolean(workspaceId);
      const title = isUpdate ? "Workspace Updated" : "Workspace Saved";
      const desc = isUpdate ? `Updated active workspace: ${name}` : `Saved workspace: ${name}`;
      showToast(title, desc, "success");

      if (state) {
        state.activeWorkspaceId = res.workspace?.workspace_id || workspaceId;
        state.activeWorkspaceName = res.workspace?.name || name;
      }

      await loadWorkspaceListUI();
      const select = document.getElementById("selectWorkspace");
      if (select && res.workspace) select.value = res.workspace.workspace_id;
      updateWorkspaceHeaderDisplay();
      renderWorkspaceActiveBanner();
    } else {
      showToast("Save Failed", res?.message || "Failed to save workspace", "error");
    }
  } catch (err) {
    console.error("Error saving workspace:", err);
    showToast("Error", "Could not save workspace", "error");
  }
}

async function deleteActiveWorkspaceFromUI() {
  const activeId = state?.activeWorkspaceId;
  const activeName = state?.activeWorkspaceName;
  if (!activeId) {
    showToast("No Active Workspace", "Default Workspace cannot be deleted.", "info");
    return;
  }
  await deleteWorkspaceById(activeId, activeName);
}

async function deleteWorkspaceById(workspaceId, workspaceName) {
  if (typeof showAppleConfirm === "function") {
    const confirmed = await showAppleConfirm({
      title: "Delete Workspace",
      message: `Are you sure you want to delete workspace "${workspaceName || workspaceId}"? This action cannot be undone.`,
      confirmText: "Delete Workspace",
      cancelText: "Cancel",
      isDestructive: true,
    });
    if (!confirmed) return;
  }
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.delete_workspace) {
    return;
  }
  try {
    const res = await window.pywebview.api.delete_workspace(workspaceId);
    if (res && res.status === "success") {
      showToast("Workspace Deleted", `Removed workspace ${workspaceName || workspaceId}`, "info");
      if (state && state.activeWorkspaceId === workspaceId) {
        state.activeWorkspaceId = null;
        state.activeWorkspaceName = "Default Workspace";
        const select = document.getElementById("selectWorkspace");
        if (select) select.value = "";
        updateWorkspaceHeaderDisplay();
        renderWorkspaceActiveBanner();
      }
      await loadWorkspaceListUI();
    } else {
      showToast("Delete Failed", res?.message || "Could not delete workspace", "error");
    }
  } catch (err) {
    console.error("Error deleting workspace:", err);
  }
}

async function exportActiveWorkspaceFromUI() {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.export_workspace_file) {
    return;
  }
  try {
    const res = await window.pywebview.api.export_workspace_file();
    if (res && res.status === "success") {
      showToast("Workspace Exported", `Saved to ${res.file_path}`, "success");
    } else if (res && res.status !== "cancelled") {
      showToast("Export Failed", res.message || "Failed to export", "error");
    }
  } catch (err) {
    console.error("Error exporting workspace:", err);
  }
}

async function importWorkspaceFromUI() {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.import_workspace_file) {
    return;
  }
  try {
    const res = await window.pywebview.api.import_workspace_file();
    if (res && res.status === "success") {
      showToast("Workspace Imported", `Imported ${res.workspace?.name}`, "success");
      await loadWorkspaceListUI();
      if (res.workspace?.workspace_id) {
        await loadWorkspaceById(res.workspace.workspace_id);
      }
    } else if (res && res.status !== "cancelled") {
      showToast("Import Failed", res.message || "Failed to import", "error");
    }
  } catch (err) {
    console.error("Error importing workspace:", err);
  }
}

// ── Smart Mid-Semester Roster Diff Engine & Modal ───────────────────────────

function openRosterDiffModal() {
  const modal = document.getElementById("modalRosterDiffBackdrop");
  if (modal) modal.classList.remove("d-none");
}

function closeRosterDiffModal() {
  const modal = document.getElementById("modalRosterDiffBackdrop");
  if (modal) modal.classList.add("d-none");
  currentRosterDiffPayload = null;
}

async function triggerRosterDiff(classKey) {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.browse_rosters) {
    return;
  }
  try {
    const res = await window.pywebview.api.browse_rosters();
    if (!res || res.cancelled || !res.rosters || res.rosters.length === 0) {
      return;
    }
    const updatedFile = res.rosters[res.rosters.length - 1];
    await previewRosterDiffForClass(classKey, updatedFile);
  } catch (err) {
    console.error("Error initiating roster update browse:", err);
  }
}

async function previewRosterDiffForClass(classKey, newFilePath) {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.preview_roster_diff) {
    return;
  }
  try {
    const res = await window.pywebview.api.preview_roster_diff(classKey, newFilePath);
    if (res && res.status === "success") {
      currentRosterDiffPayload = res;
      renderRosterDiff(res);
      openRosterDiffModal();
    } else {
      showToast("Diff Inspection Failed", res?.message || "Could not analyze roster diff", "error");
    }
  } catch (err) {
    console.error("Error previewing roster diff:", err);
    showToast("Error", "Could not preview roster diff", "error");
  }
}

function renderRosterDiff(diffData) {
  const diff = diffData.diff || {};
  const classKeyEl = document.getElementById("rosterDiffClassKey");
  const summaryEl = document.getElementById("rosterDiffSummary");
  const addedEl = document.getElementById("rosterDiffAddedList");
  const removedEl = document.getElementById("rosterDiffRemovedList");
  const modEl = document.getElementById("rosterDiffModifiedList");
  const unchEl = document.getElementById("rosterDiffUnchangedCount");

  if (classKeyEl) classKeyEl.textContent = diffData.class_key || "Class";

  if (summaryEl) {
    summaryEl.innerHTML = `
      <span class="diff-badge-added">+ ${diff.counts?.added || 0} Added</span>
      <span class="diff-badge-removed">- ${diff.counts?.removed || 0} Dropped</span>
      <span class="diff-badge-modified">~ ${diff.counts?.modified || 0} Modified</span>
    `;
  }

  if (addedEl) {
    const added = diff.added || [];
    if (added.length === 0) {
      addedEl.innerHTML = `<em>None</em>`;
    } else {
      addedEl.innerHTML = added
        .map((s) => `<div><strong>${escapeHTML(s.name)}</strong> (${escapeHTML(s.student_number || "No ID")})</div>`)
        .join("");
    }
  }

  if (removedEl) {
    const removed = diff.removed || [];
    if (removed.length === 0) {
      removedEl.innerHTML = `<em>None</em>`;
    } else {
      removedEl.innerHTML = removed
        .map((s) => `<div><span style="text-decoration: line-through;">${escapeHTML(s.name)}</span> (${escapeHTML(s.student_number || "No ID")})</div>`)
        .join("");
    }
  }

  if (modEl) {
    const modified = diff.modified || [];
    if (modified.length === 0) {
      modEl.innerHTML = `<em>None</em>`;
    } else {
      modEl.innerHTML = modified
        .map((m) => `<div>${escapeHTML(m.reason || "Record modified")}</div>`)
        .join("");
    }
  }

  if (unchEl) {
    unchEl.textContent = diff.counts?.unchanged || 0;
  }
}

async function confirmApplyRosterDiff() {
  if (!currentRosterDiffPayload) return;
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.apply_roster_diff) {
    return;
  }
  try {
    const res = await window.pywebview.api.apply_roster_diff(
      currentRosterDiffPayload.class_key,
      currentRosterDiffPayload.new_file_path
    );
    if (res && res.status === "success") {
      state.rosters = res.rosters || [];
      state.rosterReports = res.validation || [];
      renderRosterStatus();
      await refreshClassDetection();
      updateStepperStatus();
      updateFileEstimate();
      closeRosterDiffModal();
      showToast("Roster Updated", `Updated roster for ${currentRosterDiffPayload.class_key}`, "success");
    } else {
      showToast("Apply Failed", res?.message || "Failed to apply roster update", "error");
    }
  } catch (err) {
    console.error("Error applying roster diff:", err);
    showToast("Error", "Could not apply roster update", "error");
  }
}

// ── Smart Ingest Multi-File Drop Router ──────────────────────────────────────

async function handleSmartIngestFiles(filePaths) {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.smart_ingest_files) {
    return;
  }
  try {
    const res = await window.pywebview.api.smart_ingest_files(filePaths);
    if (res && res.status === "success") {
      const actions = res.applied_actions || [];
      if (actions.length > 0) {
        showToast("Smart Ingest", actions.join(" · "), "success");
      }
      await refreshClassDetection();
      await loadWorkspaceListUI();
      updateStepperStatus();
      updateFileEstimate();
    }
  } catch (err) {
    console.error("Smart Ingest failed:", err);
  }
}

// Initialize workspaces UI when document is ready
document.addEventListener("DOMContentLoaded", () => {
  loadWorkspaceListUI();
});
