// ── Template Sets System: Multi-Template Institutional Management ─────────

const CANONICAL_ROLE_NAMES = {
  syllabus: "Syllabus Acceptance",
  exam_returns_midterm: "Exam Returns (Midterm)",
  exam_returns_final: "Exam Returns (Final)",
  tos_midterm: "Table of Specifications (Midterm)",
  tos_final: "Table of Specifications (Final)",
  grade_discussion_midterm: "Grade Discussion (Midterm)",
  grade_discussion_final: "Grade Discussion (Final)",
  attendance_lecture: "Attendance Sheet (Lecture)",
  attendance_lecture_lab: "Attendance Sheet (Lecture + Lab)",
  grade_sheet_lecture: "Grading Sheet (Lecture)",
  grade_sheet_lecture_lab: "Grading Sheet (Lecture + Lab)",
};

let currentEditingTemplateSet = null; // null if creating, set_id if editing
let inspectedTemplateSetFiles = []; // list of inspected file entries with detected/assigned roles

async function loadTemplateSetsUI() {
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_template_sets) {
    console.warn("pywebview bridge unavailable for Template Sets");
    return;
  }
  try {
    const res = await window.pywebview.api.get_template_sets();
    if (res && res.status === "success") {
      renderTemplateSetsList(res.template_sets || [], res.active_set_id || "builtin_cvsu");
    } else {
      console.error("Failed to load template sets:", res);
    }
  } catch (err) {
    console.error("Error loading template sets:", err);
  }
}

function renderTemplateSetsList(sets, activeSetId) {
  const container = document.getElementById("templateSetsListContainer");
  const activeBanner = document.getElementById("activeTemplateSetBanner");
  if (!container) return;

  const activeSet = sets.find((s) => s.set_id === activeSetId) || sets[0];

  // Render Active Banner
  if (activeBanner && activeSet) {
    const isBuiltin = activeSet.source === "builtin";
    const statusClass = activeSet.is_complete ? "badge-complete" : "badge-incomplete";
    const statusText = activeSet.is_complete ? "Complete (11/11 Roles)" : `${activeSet.configured_roles || 0}/11 Roles`;
    const fallbackText = activeSet.fallback_to_default ? "ON" : "OFF";
    const fallbackColor = activeSet.fallback_to_default ? "var(--accent-emerald)" : "var(--accent-amber)";

    activeBanner.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;">
        <div>
          <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--accent-emerald); font-weight: 700;">
            ACTIVE TEMPLATE SET
          </div>
          <div style="font-size: 16px; font-weight: 700; color: var(--text-primary); margin-top: 2px;">
            ${escapeHTML(activeSet.display_name)}
            <span class="filter-pill ${statusClass}" style="font-size: 11px; margin-left: 8px; vertical-align: middle;">
              ${statusText}
            </span>
            ${isBuiltin ? `<span class="filter-pill" style="font-size: 11px; margin-left: 4px; vertical-align: middle;">Built-in</span>` : ""}
          </div>
          <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
            ${escapeHTML(activeSet.description || "Active document template set used for all generation.")}
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 16px;">
          ${!isBuiltin ? `
            <div style="text-align: right;">
              <div style="font-size: 11.5px; color: var(--text-secondary); margin-bottom: 2px;">Fallback to CvSU Default:</div>
              <button
                type="button"
                class="nav-btn"
                onclick="toggleSetFallbackUI('${encodeURIComponent(activeSet.set_id)}', ${!activeSet.fallback_to_default})"
                style="color: ${fallbackColor}; border-color: ${fallbackColor}; font-weight: 600; padding: 2px 10px; font-size: 11.5px;"
                title="When ON, missing templates in this set fall back to built-in CvSU templates."
              >
                ${fallbackText}
              </button>
            </div>
          ` : ""}
        </div>
      </div>
    `;
  }

  // Render Sets Cards
  container.innerHTML = sets
    .map((s) => {
      const isCurActive = s.set_id === activeSetId;
      const isBuiltin = s.source === "builtin";
      const totalRoles = 11;
      const assignedCount = s.configured_roles !== undefined ? s.configured_roles : Object.keys(s.templates || {}).length;
      const isComplete = s.is_complete;
      const statusPill = isComplete
        ? `<span class="filter-pill active" style="font-size: 11px; background: rgba(16,185,129,0.15); color: var(--accent-emerald); border-color: rgba(16,185,129,0.3);">✓ Complete (11/11)</span>`
        : `<span class="filter-pill" style="font-size: 11px; background: rgba(245,158,11,0.15); color: var(--accent-amber); border-color: rgba(245,158,11,0.3);">⚠️ ${assignedCount}/${totalRoles} Templates</span>`;
      const fallbackPill = !isBuiltin
        ? `<span class="filter-pill" style="font-size: 10.5px;">Fallback: ${s.fallback_to_default ? "ON" : "OFF"}</span>`
        : "";

      return `
        <div class="template-set-card ${isCurActive ? "active-set-border" : ""}" style="background: var(--surface-elevated); border: 1px solid ${isCurActive ? "var(--accent-emerald)" : "var(--border-subtle)"}; border-radius: var(--radius-md); padding: 14px 16px; margin-bottom: 10px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap;">
            <div style="min-width: 0; flex: 1;">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <strong style="font-size: 14px; color: var(--text-primary);">${escapeHTML(s.display_name)}</strong>
                ${statusPill}
                ${isBuiltin ? `<span class="filter-pill" style="font-size: 10.5px;">Read Only</span>` : fallbackPill}
                ${isCurActive ? `<span class="filter-pill active" style="font-size: 10.5px; background: var(--accent-emerald); color: #fff;">Active</span>` : ""}
              </div>
              <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px; line-height: 1.4;">
                ${escapeHTML(s.description || "No description provided.")}
              </div>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">
                ID: <code>${escapeHTML(s.set_id)}</code> • Version: ${escapeHTML(s.version || "1.0.0")}
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              ${!isCurActive ? `
                <button
                  type="button"
                  class="btn-primary-compact"
                  onclick="activateTemplateSetUI('${encodeURIComponent(s.set_id)}')"
                  style="font-size: 12px; padding: 4px 12px;"
                >
                  Activate
                </button>
              ` : `
                <button
                  type="button"
                  class="nav-btn"
                  disabled
                  style="font-size: 12px; padding: 4px 12px; opacity: 0.8; cursor: default; border-color: var(--accent-emerald); color: var(--accent-emerald);"
                >
                  ✓ Active
                </button>
              `}
              <button
                type="button"
                class="nav-btn"
                onclick="duplicateTemplateSetUI('${encodeURIComponent(s.set_id)}', '${escapeHTML(s.display_name)}')"
                style="font-size: 12px; padding: 4px 10px;"
                title="Duplicate set"
              >
                Duplicate
              </button>
              <button
                type="button"
                class="nav-btn"
                onclick="exportTemplateSetUI('${encodeURIComponent(s.set_id)}')"
                style="font-size: 12px; padding: 4px 10px;"
                title="Export .cvstemplateset.zip package"
              >
                Export
              </button>
              ${!isBuiltin ? `
                <button
                  type="button"
                  class="nav-btn"
                  onclick="openEditTemplateSetModal('${encodeURIComponent(s.set_id)}')"
                  style="font-size: 12px; padding: 4px 10px;"
                  title="Edit set templates"
                >
                  Edit
                </button>
                <button
                  type="button"
                  class="nav-btn"
                  onclick="deleteTemplateSetUI('${encodeURIComponent(s.set_id)}', '${escapeHTML(s.display_name)}')"
                  style="font-size: 12px; padding: 4px 10px; color: var(--accent-red, #ef4444); border-color: rgba(239, 68, 68, 0.3);"
                  title="Delete set"
                >
                  Delete
                </button>
              ` : ""}
            </div>
          </div>
        </div>
      `;
    })
    .join("");
}

// ── Actions ──────────────────────────────────────────────────────────────────
async function activateTemplateSetUI(encodedId) {
  const setId = decodeURIComponent(encodedId);
  try {
    const res = await window.pywebview.api.activate_template_set(setId);
    if (res && res.status === "success") {
      showToast("Template Set Activated", `Set "${setId}" is now active.`, "success");
      await loadTemplateSetsUI();
    } else {
      showToast("Activation Failed", (res && res.message) || "Could not activate template set", "error");
    }
  } catch (err) {
    console.error("Activate set error:", err);
    showToast("Error", String(err), "error");
  }
}

async function toggleSetFallbackUI(encodedId, enabled) {
  const setId = decodeURIComponent(encodedId);
  try {
    const res = await window.pywebview.api.set_template_set_fallback(setId, enabled);
    if (res && res.status === "success") {
      showToast("Policy Updated", `Fallback to CvSU Default is now ${enabled ? "ON" : "OFF"}.`, "info");
      await loadTemplateSetsUI();
    }
  } catch (err) {
    console.error("Toggle fallback error:", err);
  }
}

async function deleteTemplateSetUI(encodedId, displayName) {
  const setId = decodeURIComponent(encodedId);
  const confirmed = await showAppleConfirm({
    title: "Delete Template Set",
    message: `Are you sure you want to delete template set "${displayName}"? All copies of templates in this set will be deleted. This cannot be undone.`,
    confirmText: "Delete Set",
    cancelText: "Cancel",
    isDestructive: true,
  });
  if (!confirmed) return;

  try {
    const res = await window.pywebview.api.delete_template_set(setId);
    if (res && res.status === "success") {
      showToast("Template Set Deleted", `Set "${displayName}" removed.`, "info");
      await loadTemplateSetsUI();
    } else {
      showToast("Delete Failed", (res && res.message) || "Could not delete set", "error");
    }
  } catch (err) {
    console.error("Delete set error:", err);
    showToast("Error", String(err), "error");
  }
}

async function duplicateTemplateSetUI(encodedId, displayName) {
  const setId = decodeURIComponent(encodedId);
  const newName = prompt(`Enter a name for the duplicated set:`, `${displayName} (Copy)`);
  if (!newName || !newName.trim()) return;

  try {
    const res = await window.pywebview.api.duplicate_template_set(setId, newName.trim());
    if (res && res.status === "success") {
      showToast("Set Duplicated", `Created "${newName.trim()}".`, "success");
      await loadTemplateSetsUI();
    } else {
      showToast("Duplicate Failed", (res && res.message) || "Could not duplicate set", "error");
    }
  } catch (err) {
    console.error("Duplicate set error:", err);
  }
}

async function exportTemplateSetUI(encodedId) {
  const setId = decodeURIComponent(encodedId);
  try {
    const res = await window.pywebview.api.export_template_set(setId);
    if (res && res.status === "success") {
      showToast("Export Complete", `Saved package to ${res.file_path}`, "success");
    } else if (res && res.status !== "cancelled") {
      showToast("Export Failed", res.message || "Failed to export", "error");
    }
  } catch (err) {
    console.error("Export set error:", err);
    showToast("Error", String(err), "error");
  }
}

async function importTemplateSetUI() {
  try {
    const res = await window.pywebview.api.import_template_set();
    if (res && res.status === "success") {
      showToast("Import Complete", `Successfully imported "${res.template_set.display_name}".`, "success");
      await loadTemplateSetsUI();
    } else if (res && res.status !== "cancelled") {
      showToast("Import Failed", res.message || "Failed to import template set", "error");
    }
  } catch (err) {
    console.error("Import set error:", err);
    showToast("Error", String(err), "error");
  }
}

// ── Create & Edit Modal Workflow ─────────────────────────────────────────────
function openCreateTemplateSetModal() {
  currentEditingTemplateSet = null;
  inspectedTemplateSetFiles = [];

  const modal = document.getElementById("templateSetEditorModal");
  const title = document.getElementById("templateSetEditorTitle");
  const nameInput = document.getElementById("templateSetNameInput");
  const descInput = document.getElementById("templateSetDescInput");
  const fallbackCheck = document.getElementById("templateSetFallbackCheck");

  if (title) title.innerText = "➕ Create New Template Set";
  if (nameInput) nameInput.value = "";
  if (descInput) descInput.value = "";
  if (fallbackCheck) fallbackCheck.checked = false;

  renderInspectedFilesList();
  if (modal) modal.classList.remove("d-none");
}

async function openEditTemplateSetModal(encodedId) {
  const setId = decodeURIComponent(encodedId);
  currentEditingTemplateSet = setId;
  inspectedTemplateSetFiles = [];

  try {
    const res = await window.pywebview.api.get_template_sets();
    const setObj = (res.template_sets || []).find((s) => s.set_id === setId);
    if (!setObj) {
      showToast("Error", "Template set not found", "error");
      return;
    }

    const modal = document.getElementById("templateSetEditorModal");
    const title = document.getElementById("templateSetEditorTitle");
    const nameInput = document.getElementById("templateSetNameInput");
    const descInput = document.getElementById("templateSetDescInput");
    const fallbackCheck = document.getElementById("templateSetFallbackCheck");

    if (title) title.innerText = `✏️ Edit Template Set: ${setObj.display_name}`;
    if (nameInput) nameInput.value = setObj.display_name || "";
    if (descInput) descInput.value = setObj.description || "";
    if (fallbackCheck) fallbackCheck.checked = !!setObj.fallback_to_default;

    // Populate existing templates
    inspectedTemplateSetFiles = Object.entries(setObj.templates || {}).map(([role, t]) => ({
      file_path: t.file_path,
      file_name: (t.display_metadata && t.display_metadata.original_filename) || t.file_path.split(/[\\/]/).pop(),
      file_type: t.file_type,
      status: "confirmed",
      role: role,
      candidate_roles: [role],
      structural_evidence: ["Verified template from existing set"],
      diagnostic_hints: [],
      profile_id: t.profile_id,
      error: null,
    }));

    renderInspectedFilesList();
    if (modal) modal.classList.remove("d-none");
  } catch (err) {
    console.error("Open edit modal error:", err);
  }
}

function closeTemplateSetEditorModal() {
  const modal = document.getElementById("templateSetEditorModal");
  if (modal) modal.classList.add("d-none");
  currentEditingTemplateSet = null;
  inspectedTemplateSetFiles = [];
}

async function browseTemplateSetFilesFromUI() {
  try {
    const res = await window.pywebview.api.browse_template_set_files();
    if (res && res.status === "success") {
      addInspectedFiles(res.inspections || []);
    } else if (res && res.status === "error") {
      showToast("Analysis Error", res.message || "Failed to inspect templates", "error");
    }
  } catch (err) {
    console.error("Browse files error:", err);
    showToast("Error", String(err), "error");
  }
}

function addInspectedFiles(newInspections) {
  for (const item of newInspections) {
    // If a file for the same role or same path is already present, update it
    const existingIdx = inspectedTemplateSetFiles.findIndex(
      (f) => f.file_path === item.file_path || (item.role && f.role === item.role)
    );
    if (existingIdx >= 0) {
      inspectedTemplateSetFiles[existingIdx] = item;
    } else {
      inspectedTemplateSetFiles.push(item);
    }
  }
  renderInspectedFilesList();
}

function onTemplateFileRoleChanged(index, newRole) {
  if (inspectedTemplateSetFiles[index]) {
    inspectedTemplateSetFiles[index].role = newRole;
    inspectedTemplateSetFiles[index].status = newRole ? "confirmed" : "ambiguous";
    renderInspectedFilesList();
  }
}

function removeInspectedFile(index) {
  inspectedTemplateSetFiles.splice(index, 1);
  renderInspectedFilesList();
}

function renderInspectedFilesList() {
  const listEl = document.getElementById("templateSetInspectedFilesList");
  const completenessEl = document.getElementById("templateSetCompletenessSummary");
  if (!listEl) return;

  const totalCanonical = Object.keys(CANONICAL_ROLE_NAMES).length;
  const assignedRoles = new Set();
  inspectedTemplateSetFiles.forEach((f) => {
    if (f.role && f.status === "confirmed") {
      assignedRoles.add(f.role);
    }
  });

  const assignedCount = assignedRoles.size;
  const isComplete = assignedCount === totalCanonical;

  if (completenessEl) {
    completenessEl.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span style="font-size: 12.5px; font-weight: 600; color: var(--text-primary);">
          Template Set Roles: ${assignedCount} / ${totalCanonical} Assigned
        </span>
        <span class="filter-pill ${isComplete ? "active" : ""}" style="font-size: 11px;">
          ${isComplete ? "✓ Complete Set" : "⚠️ Incomplete (Requires 11 Roles)"}
        </span>
      </div>
      <div style="background: var(--surface-subtle); height: 6px; border-radius: 3px; overflow: hidden;">
        <div style="background: ${isComplete ? "var(--accent-emerald)" : "var(--accent-amber)"}; height: 100%; width: ${(assignedCount / totalCanonical) * 100}%; transition: width 0.3s ease;"></div>
      </div>
    `;
  }

  if (inspectedTemplateSetFiles.length === 0) {
    listEl.innerHTML = `
      <div style="text-align: center; padding: 24px; color: var(--text-muted); background: var(--surface-subtle); border-radius: var(--radius-md); border: 1px dashed var(--border-subtle); font-size: 12px;">
        No templates added yet. Drag & drop or browse DOCX and XLSX template files to inspect and assign roles.
      </div>
    `;
    return;
  }

  listEl.innerHTML = inspectedTemplateSetFiles
    .map((item, idx) => {
      const isConfirmed = item.status === "confirmed" && !!item.role;
      const roleDisplayName = item.role ? (CANONICAL_ROLE_NAMES[item.role] || item.role) : "Unassigned / Ambiguous";
      const evidenceList = item.structural_evidence || [];
      const isXlsx = item.file_type === "xlsx";

      const options = Object.entries(CANONICAL_ROLE_NAMES).map(([rKey, rName]) => {
        const isSelected = item.role === rKey;
        return `<option value="${rKey}" ${isSelected ? "selected" : ""}>${escapeHTML(rName)}</option>`;
      }).join("");

      return `
        <div style="background: var(--surface-elevated); border: 1px solid ${isConfirmed ? "var(--accent-emerald)" : "var(--accent-amber)"}; border-radius: var(--radius-md); padding: 12px; margin-bottom: 8px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;">
            <div style="min-width: 0; flex: 1;">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span style="font-size: 16px;">${isXlsx ? "📊" : "📄"}</span>
                <strong style="font-size: 13px; color: var(--text-primary);">${escapeHTML(item.file_name)}</strong>
                <span class="filter-pill ${isConfirmed ? "active" : ""}" style="font-size: 10.5px;">
                  ${isConfirmed ? "✓ " + escapeHTML(roleDisplayName) : "⚠️ Ambiguous - Selection Required"}
                </span>
              </div>
              
              <!-- Structural Evidence -->
              <div style="margin-top: 6px; font-size: 11.5px; color: var(--text-secondary); line-height: 1.4;">
                ${evidenceList.map((e) => `<div style="display: flex; align-items: center; gap: 4px;"><span>•</span> <span>${escapeHTML(e)}</span></div>`).join("")}
                ${item.diagnostic_hints ? item.diagnostic_hints.map((h) => `<div style="color: var(--text-muted); font-size: 11px;">💡 ${escapeHTML(h)}</div>`).join("") : ""}
                ${item.error ? `<div style="color: var(--accent-red, #ef4444); font-size: 11px;">❌ ${escapeHTML(item.error)}</div>` : ""}
              </div>
            </div>

            <!-- Role Selector & Actions -->
            <div style="display: flex; align-items: center; gap: 8px;">
              <select
                class="form-control-custom"
                style="font-size: 11.5px; padding: 4px 8px; min-width: 220px;"
                onchange="onTemplateFileRoleChanged(${idx}, this.value)"
              >
                <option value="">-- Choose Canonical Role --</option>
                ${options}
              </select>
              <button
                type="button"
                class="btn-remove-roster"
                title="Remove template"
                onclick="removeInspectedFile(${idx})"
                style="font-size: 14px; padding: 4px 8px;"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      `;
    })
    .join("");
}

async function saveTemplateSetFromModal() {
  const nameInput = document.getElementById("templateSetNameInput");
  const descInput = document.getElementById("templateSetDescInput");
  const fallbackCheck = document.getElementById("templateSetFallbackCheck");

  const displayName = nameInput ? nameInput.value.trim() : "";
  const description = descInput ? descInput.value.trim() : "";
  const fallbackToDefault = fallbackCheck ? fallbackCheck.checked : false;

  if (!displayName) {
    showToast("Name Required", "Please enter a display name for the template set.", "warning");
    return;
  }

  // Filter valid confirmed assignments
  const assignments = inspectedTemplateSetFiles
    .filter((f) => f.role && f.file_path)
    .map((f) => ({
      role: f.role,
      file_path: f.file_path,
      display_metadata: {
        original_filename: f.file_name,
        structural_evidence: f.structural_evidence || [],
      },
    }));

  const setId = currentEditingTemplateSet || displayName.toLowerCase().replace(/[^a-z0-9_-]/g, "_");

  try {
    const res = await window.pywebview.api.save_template_set(
      setId,
      displayName,
      description,
      fallbackToDefault,
      assignments
    );

    if (res && res.status === "success") {
      showToast("Template Set Saved", `Saved "${displayName}" with ${assignments.length} templates.`, "success");
      closeTemplateSetEditorModal();
      await loadTemplateSetsUI();
    } else {
      showToast("Save Error", (res && res.message) || "Failed to save template set", "error");
    }
  } catch (err) {
    console.error("Save template set error:", err);
    showToast("Error", String(err), "error");
  }
}

// Export functions to window
window.loadTemplateSetsUI = loadTemplateSetsUI;
window.activateTemplateSetUI = activateTemplateSetUI;
window.toggleSetFallbackUI = toggleSetFallbackUI;
window.deleteTemplateSetUI = deleteTemplateSetUI;
window.duplicateTemplateSetUI = duplicateTemplateSetUI;
window.exportTemplateSetUI = exportTemplateSetUI;
window.importTemplateSetUI = importTemplateSetUI;
window.openCreateTemplateSetModal = openCreateTemplateSetModal;
window.openEditTemplateSetModal = openEditTemplateSetModal;
window.closeTemplateSetEditorModal = closeTemplateSetEditorModal;
window.browseTemplateSetFilesFromUI = browseTemplateSetFilesFromUI;
window.onTemplateFileRoleChanged = onTemplateFileRoleChanged;
window.removeInspectedFile = removeInspectedFile;
window.saveTemplateSetFromModal = saveTemplateSetFromModal;
