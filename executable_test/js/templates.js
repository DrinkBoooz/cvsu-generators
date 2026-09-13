// ── Custom Templates & Deterministic Heuristic Analyzer ───────────────
      let currentInspectedTemplate = null;

      async function loadCustomTemplatesUI() {
        if (
          !window.pywebview ||
          !window.pywebview.api ||
          !window.pywebview.api.get_custom_templates
        ) {
          renderCustomTemplatesList(state.customTemplates || []);
          return;
        }
        try {
          const templates = await window.pywebview.api.get_custom_templates();
          state.customTemplates = templates || [];
          renderCustomTemplatesList(templates || []);
          updateFileEstimate();
        } catch (err) {
          console.error("Failed to load custom templates:", err);
          renderCustomTemplatesList(state.customTemplates || []);
        }
      }

      function renderCustomTemplatesList(templates) {
        const listEl = document.getElementById("customTemplatesList");
        const countEl = document.getElementById("customTemplatesCount");
        if (!listEl) return;

        if (countEl) countEl.innerText = (templates || []).length;

        if (!templates || templates.length === 0) {
          listEl.innerHTML = `
            <div style="text-align: center; padding: 24px; color: var(--text-muted); background: var(--surface-subtle); border-radius: var(--radius-md); border: 1px dashed var(--border-subtle); font-size: 12.5px;">
              No custom forms registered yet. Upload any CEIT Word (.docx) template above to analyze and add it.
            </div>
          `;
          return;
        }

        listEl.innerHTML = templates
          .map((t) => {
            const isEnabled = t.enabled !== false;
            const escapedId = encodeURIComponent(t.id);
            const title = escapeHTML(t.title || t.id);
            const suffix = escapeHTML(t.suffix || "FORM");
            const filename = escapeHTML(t.filename || "");
            return `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: var(--surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); gap: 12px;">
              <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
                <div style="font-size: 20px;">📄</div>
                <div style="min-width: 0;">
                  <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <strong style="font-size: 13px; color: var(--text-primary);">${title}</strong>
                    <span class="filter-pill active" style="font-size: 10.5px; padding: 1px 7px;">${suffix}</span>
                  </div>
                  <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
                    File: ${filename}
                  </div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 12px;">
                <label style="display: flex; align-items: center; gap: 6px; font-size: 12px; cursor: pointer; color: var(--text-secondary); user-select: none;">
                  <input type="checkbox" ${isEnabled ? "checked" : ""} onchange="toggleCustomTemplateUI('${escapedId}', this.checked)" style="accent-color: var(--accent-emerald); cursor: pointer;" />
                  <span>Enabled</span>
                </label>
                <button
                  type="button"
                  class="btn-remove-roster"
                  title="Delete Template"
                  onclick="deleteCustomTemplateUI('${escapedId}')"
                  style="font-size: 15px; padding: 4px 8px;"
                >
                  ✕
                </button>
              </div>
            </div>
          `;
          })
          .join("");
      }

      async function browseCustomTemplateFile() {
        if (
          !window.pywebview ||
          !window.pywebview.api ||
          !window.pywebview.api.browse_custom_template
        ) {
          showToast(
            "Bridge Unavailable",
            "Desktop backend bridge is not active.",
            "warning",
          );
          return;
        }
        try {
          const res = await window.pywebview.api.browse_custom_template();
          if (res && res.status === "success") {
            renderCustomTemplateInspection(res);
          } else if (res && res.status === "error") {
            showToast(
              "Analysis Error",
              res.message || "Failed to inspect template",
              "error",
            );
          }
        } catch (e) {
          console.error("Browse custom template error:", e);
          showToast("Error", String(e), "error");
        }
      }

      function renderCustomTemplateInspection(res) {
        currentInspectedTemplate = res;
        const recipe = res.recipe || {};
        const card = document.getElementById("customTemplateResultCard");
        if (!card) return;

        card.classList.remove("d-none");

        const titleInput = document.getElementById("customFormTitle");
        const suffixInput = document.getElementById("customFormSuffix");
        const confBadge = document.getElementById("customConfidenceBadge");
        const fieldsList = document.getElementById("customDetectedFieldsList");
        const rosterSummary = document.getElementById(
          "customRosterStructureSummary",
        );

        if (titleInput) titleInput.value = recipe.title || "";
        if (suffixInput) suffixInput.value = recipe.suffix || "";
        if (confBadge) confBadge.innerText = `${recipe.confidence || 0}% Match`;

        if (fieldsList) {
          const bindings = recipe.header_bindings || [];
          if (bindings.length === 0) {
            fieldsList.innerHTML = `<span style="color: var(--text-muted);">None detected</span>`;
          } else {
            fieldsList.innerHTML = bindings
              .map((b) => {
                const fName = (b.field || "").replace("_", " ").toUpperCase();
                return `<span class="filter-pill" style="font-size: 10.5px; padding: 2px 6px;">${escapeHTML(fName)}</span>`;
              })
              .join("");
          }
        }

        if (rosterSummary) {
          const r = recipe.roster_table;
          if (!r) {
            rosterSummary.innerHTML = `<span style="color: var(--accent-amber);">No roster table detected. Only header metadata will be populated.</span>`;
          } else {
            rosterSummary.innerHTML = `
              <div>Table Index: ${r.table_index} | Total Cols: ${r.total_cols}</div>
              <div style="font-size: 11.5px; margin-top: 2px; color: var(--text-muted);">
                Name Col: ${r.name_col !== null ? r.name_col : "None"} | ID Col: ${r.id_col !== null ? r.id_col : "None"} | Index Col: ${r.index_col !== null ? r.index_col : "None"}
              </div>
            `;
          }
        }

        card.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }

      function cancelCustomTemplatePreview() {
        currentInspectedTemplate = null;
        const card = document.getElementById("customTemplateResultCard");
        if (card) card.classList.add("d-none");
      }

      async function saveCustomTemplateFromUI() {
        if (!currentInspectedTemplate) return;
        const titleInput = document.getElementById("customFormTitle");
        const suffixInput = document.getElementById("customFormSuffix");

        const title = titleInput ? titleInput.value.trim() : "";
        const suffix = suffixInput ? suffixInput.value.trim() : "";

        if (!suffix) {
          showToast(
            "Invalid Suffix",
            "Please provide a file suffix.",
            "warning",
          );
          return;
        }

        const recipe = currentInspectedTemplate.recipe;
        recipe.title = title;
        recipe.suffix = suffix;

        try {
          const res = await window.pywebview.api.save_custom_template(
            currentInspectedTemplate.file_path,
            title,
            suffix,
            recipe,
          );
          if (res && res.status === "success") {
            showToast(
              "Custom Form Added",
              `Successfully registered ${title || suffix}!`,
              "success",
            );
            cancelCustomTemplatePreview();
            await loadCustomTemplatesUI();
          } else {
            showToast(
              "Save Error",
              (res && res.message) || "Failed to save template",
              "error",
            );
          }
        } catch (e) {
          console.error("Save custom template error:", e);
          showToast("Error", String(e), "error");
        }
      }

      async function toggleCustomTemplateUI(encodedId, enabled) {
        const id = decodeURIComponent(encodedId);
        try {
          const res = await window.pywebview.api.toggle_custom_template(
            id,
            enabled,
          );
          if (res && res.status === "success") {
            showToast(
              "Template Updated",
              `Template ${id} is now ${enabled ? "enabled" : "disabled"}.`,
              "info",
            );
            await loadCustomTemplatesUI();
          }
        } catch (e) {
          console.error("Toggle template error:", e);
        }
      }

      async function deleteCustomTemplateUI(encodedId) {
        const id = decodeURIComponent(encodedId);
        const confirmed = await showAppleConfirm({
          title: "Delete Custom Template",
          message: `Are you sure you want to delete custom template "${id}"? This cannot be undone.`,
          confirmText: "Delete Template",
          cancelText: "Cancel",
          isDestructive: true,
        });
        if (!confirmed) return;
        try {
          const res = await window.pywebview.api.delete_custom_template(id);
          if (res && res.status === "success") {
            showToast(
              "Template Deleted",
              `Custom template ${id} removed.`,
              "info",
            );
            await loadCustomTemplatesUI();
          }
        } catch (e) {
          console.error("Delete template error:", e);
        }
      }
