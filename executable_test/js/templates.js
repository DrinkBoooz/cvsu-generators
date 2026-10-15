// ── Custom Templates & Deterministic Heuristic Analyzer ───────────────
      let currentInspectedTemplate = null;

      async function loadCustomTemplatesUI() {
        if (
          !window.pywebview ||
          !window.pywebview.api ||
          !window.pywebview.api.get_custom_templates
        ) {
          renderCustomTemplatesList(state.customTemplates || []);
          renderCustomWorkflowPackages(state.customTemplates || []);
          return;
        }
        try {
          const templates = await window.pywebview.api.get_custom_templates();
          state.customTemplates = templates || [];
          renderCustomTemplatesList(templates || []);
          renderCustomWorkflowPackages(templates || []);
          updateFileEstimate();
        } catch (err) {
          console.error("Failed to load custom templates:", err);
          renderCustomTemplatesList(state.customTemplates || []);
          renderCustomWorkflowPackages(state.customTemplates || []);
        }
      }

      function renderCustomWorkflowPackages(templates) {
        const container = document.getElementById("customWorkflowPackages");
        if (!container) return;

        const enabled = (templates || []).filter((template) => template.enabled !== false);
        if (enabled.length === 0) {
          container.classList.add("d-none");
          container.innerHTML = "";
          return;
        }

        container.classList.remove("d-none");
        container.innerHTML = `
          <div class="form-label" style="margin: 12px 0 6px">Custom Forms Included with CEIT</div>
          <div class="template-spec-box" role="list" aria-label="Enabled custom document forms">
            ${enabled.map((template) => {
              const title = escapeHTML(template.title || template.id || "Custom Form");
              const suffix = escapeHTML(template.suffix || "CUSTOM_FORM");
              const folder = escapeHTML(
                (template.recipe && template.recipe.metadata && template.recipe.metadata.output_folder) || "CEIT_Forms",
              );
              return `
                <div role="listitem" style="display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 6px 0;">
                  <span>${title}</span>
                  <span class="filter-pill active" title="Output folder: ${folder}">${suffix}</span>
                </div>
              `;
            }).join("")}
          </div>
        `;
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
            const outFolder = escapeHTML(
              (t.recipe && t.recipe.metadata && t.recipe.metadata.output_folder) || "CEIT_Forms"
            );
            return `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; background: var(--surface-elevated); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); gap: 12px;">
              <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
                <div style="font-size: 20px;">📄</div>
                <div style="min-width: 0;">
                  <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <strong style="font-size: 13px; color: var(--text-primary);">${title}</strong>
                    <span class="filter-pill active" style="font-size: 10.5px; padding: 1px 7px;">${suffix}</span>
                    <span class="filter-pill" style="font-size: 10px; padding: 1px 6px; color: var(--accent-cyan); border-color: rgba(6,182,212,0.3);">📁 ${outFolder}</span>
                  </div>
                  <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
                    File: ${filename}
                  </div>
                </div>
              </div>
              <div style="display: flex; align-items: center; gap: 10px;">
                <button
                  type="button"
                  class="nav-btn"
                  onclick="openSlotMapperForTemplate('${escapeHTML(t.path || t.file_path || filename)}')"
                  title="Open Visual Slot Mapper"
                  style="font-size: 11px; padding: 3px 8px; border-color: var(--accent-cyan); color: var(--accent-cyan);"
                >
                  🗺️ Map Slots
                </button>
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
        const manifestSummary = res.manifest_summary || null;
        const card = document.getElementById("customTemplateResultCard");
        if (!card) return;

        card.classList.remove("d-none");

        const titleInput = document.getElementById("customFormTitle");
        const suffixInput = document.getElementById("customFormSuffix");
        const confBadge = document.getElementById("customConfidenceBadge");
        const compatBadge = document.getElementById("customCompatibilityBadge");
        const fieldsList = document.getElementById("customDetectedFieldsList");
        const rosterSummary = document.getElementById(
          "customRosterStructureSummary",
        );
        const diagDiv = document.getElementById("customTemplateDiagnostics");

        const suggestedTitle = (manifestSummary && manifestSummary.suggested_title) || recipe.title || "";
        const suggestedSuffix = (manifestSummary && manifestSummary.suggested_suffix) || recipe.suffix || "";

        if (titleInput) titleInput.value = suggestedTitle;
        if (suffixInput) suffixInput.value = suggestedSuffix;
        if (confBadge) confBadge.innerText = `${recipe.confidence || 100}% Match`;

        if (compatBadge) {
          compatBadge.style.display = "inline-flex";
          const isReady = manifestSummary ? manifestSummary.is_ready : true;
          if (isReady) {
            compatBadge.innerText = "✓ Ready";
            compatBadge.style.background = "var(--accent-emerald)";
            compatBadge.style.color = "#fff";
          } else {
            compatBadge.innerText = "⚠️ Incomplete";
            compatBadge.style.background = "var(--accent-amber)";
            compatBadge.style.color = "#000";
          }
        }

        const folderSelect = document.getElementById("customFormTargetFolderSelect");
        const folderInput = document.getElementById("customFormCustomFolderInput");
        const folderContainer = document.getElementById("customFormCustomFolderContainer");
        const metaFolder = (recipe.metadata && recipe.metadata.output_folder) || "CEIT_Forms";
        if (folderSelect) {
          if (metaFolder === "CEIT_Forms" || metaFolder === "Attendance") {
            folderSelect.value = metaFolder;
            if (folderContainer) folderContainer.classList.add("d-none");
          } else {
            folderSelect.value = "custom";
            if (folderInput) folderInput.value = metaFolder;
            if (folderContainer) folderContainer.classList.remove("d-none");
          }
        }

        if (fieldsList) {
          if (manifestSummary && manifestSummary.slots && manifestSummary.slots.length > 0) {
            fieldsList.innerHTML = manifestSummary.slots
              .map((s) => {
                const fName = (s.field || "").replace(/_/g, " ").toUpperCase();
                return `<span class="filter-pill" style="font-size: 10.5px; padding: 2px 6px;">${escapeHTML(fName)}</span>`;
              })
              .join("");
          } else {
            const bindings = recipe.header_bindings || [];
            if (bindings.length === 0) {
              fieldsList.innerHTML = `<span style="color: var(--text-muted);">None detected</span>`;
            } else {
              fieldsList.innerHTML = bindings
                .map((b) => {
                  const fName = (b.field || "").replace(/_/g, " ").toUpperCase();
                  return `<span class="filter-pill" style="font-size: 10.5px; padding: 2px 6px;">${escapeHTML(fName)}</span>`;
                })
                .join("");
            }
          }
        }

        if (rosterSummary) {
          if (manifestSummary && manifestSummary.roster_table) {
            const r = manifestSummary.roster_table;
            rosterSummary.innerHTML = `
              <div>Table Index: ${r.table_index} | Capacity: ${r.capacity} rows | Cols: ${r.total_cols}</div>
              <div style="font-size: 11.5px; margin-top: 2px; color: var(--text-muted);">
                First Data Row: ${r.first_data_row} | Registered Cols: ${Object.keys(r.columns || {}).join(", ") || "None"}
              </div>
            `;
          } else {
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
        }

        const orgSummaryEl = document.getElementById("customDiscoveredOrgSummary");
        const sigsSummaryEl = document.getElementById("customDiscoveredSignatoriesSummary");

        if (orgSummaryEl) {
          const org = manifestSummary ? manifestSummary.organizational_context : null;
          if (org) {
            orgSummaryEl.innerHTML = `
              <div><strong>Institution:</strong> ${escapeHTML(org.institution || 'CvSU')}</div>
              <div><strong>Campus:</strong> ${escapeHTML(org.campus || 'Main Campus')}</div>
              <div><strong>College:</strong> ${escapeHTML(org.college || 'None (Campus Level)')}</div>
              <div><strong>Department:</strong> ${escapeHTML(org.department || 'None detected')}</div>
            `;
          } else {
            orgSummaryEl.innerHTML = `<span style="color: var(--text-muted);">Standard university headers detected</span>`;
          }
        }

        if (sigsSummaryEl) {
          const sigs = manifestSummary ? manifestSummary.signatory_slots : [];
          if (sigs && sigs.length > 0) {
            sigsSummaryEl.innerHTML = sigs.map((s, i) => `
              <div style="margin-bottom: 2px;">
                <strong>${i + 1}. ${escapeHTML(s.role_label)}</strong> &rarr; <span class="filter-pill" style="font-size: 10px; padding: 1px 5px;">${escapeHTML(s.default_title || s.bound_key)}</span>
              </div>
            `).join("");
          } else {
            sigsSummaryEl.innerHTML = `<span style="color: var(--text-muted);">No footer signatory anchors detected</span>`;
          }
        }

        if (diagDiv) {
          const diags = (manifestSummary && manifestSummary.diagnostics) || [];
          if (diags.length > 0) {
            diagDiv.classList.remove("d-none");
            diagDiv.innerHTML = `<strong>Diagnostics:</strong><ul style="margin: 4px 0 0 16px; padding: 0;">${diags
              .map((d) => `<li>${escapeHTML(d)}</li>`)
              .join("")}</ul>`;
          } else {
            diagDiv.classList.add("d-none");
            diagDiv.innerHTML = "";
          }
        }

        card.scrollIntoView({ behavior: "smooth", block: "nearest" });

        if (window.announceA11y) {
          const isReady = manifestSummary ? manifestSummary.is_ready : true;
          window.announceA11y(`Template analysis complete. ${isReady ? "Ready for configuration." : "Diagnostics available."}`);
        }

        if (titleInput) {
          setTimeout(() => titleInput.focus(), 150);
        }
      }

      function cancelCustomTemplatePreview() {
        currentInspectedTemplate = null;
        const card = document.getElementById("customTemplateResultCard");
        if (card) card.classList.add("d-none");
        const dz = document.getElementById("templateDropzone");
        if (dz) dz.focus();
        if (window.announceA11y) {
          window.announceA11y("Template preview discarded.");
        }
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

        const folderSelect = document.getElementById("customFormTargetFolderSelect");
        const folderInput = document.getElementById("customFormCustomFolderInput");
        let targetFolder = "CEIT_Forms";
        if (folderSelect) {
          if (folderSelect.value === "custom") {
            targetFolder = folderInput ? folderInput.value.trim() : "";
            if (!targetFolder) targetFolder = "CEIT_Forms";
          } else {
            targetFolder = folderSelect.value;
          }
        }

        const recipe = currentInspectedTemplate.recipe || {};
        recipe.title = title;
        recipe.suffix = suffix;
        recipe.metadata = recipe.metadata || {};
        recipe.metadata.output_folder = targetFolder;
        delete recipe.output_folder;

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

      function onCustomTargetFolderChange(val) {
        const container = document.getElementById("customFormCustomFolderContainer");
        if (container) {
          if (val === "custom") {
            container.classList.remove("d-none");
          } else {
            container.classList.add("d-none");
          }
        }
      }
      window.onCustomTargetFolderChange = onCustomTargetFolderChange;

      // ── Interactive Visual Slot Mapper Drawer & 2D Grid Engine ────────────
      let slotMapperActivePath = null;
      let slotMapperGridData = null;
      let slotMapperCurrentTableIndex = 0;
      let slotMapperSelectedCell = null;
      let slotMapperStagedOverrides = {};

      function openSlotMapperForCurrent() {
        if (!currentInspectedTemplate || !currentInspectedTemplate.file_path) {
          showToast("No Template", "Please inspect or select a template first.", "warning");
          return;
        }
        openSlotMapperModal(currentInspectedTemplate.file_path);
      }
      window.openSlotMapperForCurrent = openSlotMapperForCurrent;

      function openSlotMapperForTemplate(filePath) {
        if (!filePath) {
          showToast("No Template", "Target template path was not specified.", "warning");
          return;
        }
        openSlotMapperModal(filePath);
      }
      window.openSlotMapperForTemplate = openSlotMapperForTemplate;

      async function openSlotMapperModal(filePath) {
        slotMapperActivePath = filePath;
        slotMapperSelectedCell = null;
        slotMapperStagedOverrides = {};
        slotMapperCurrentTableIndex = 0;

        const modal = document.getElementById("modalSlotMapperBackdrop");
        const fileLabel = document.getElementById("slotMapperFileLabel");
        const gridContainer = document.getElementById("slotMapperGridContainer");
        const coordBadge = document.getElementById("slotMapperCoordBadge");
        const roleDiv = document.getElementById("slotMapperCurrentRole");
        const textPrev = document.getElementById("slotMapperTextPreview");
        const tableSelect = document.getElementById("slotMapperTableSelect");
        const metaPill = document.getElementById("slotMapperTableMeta");

        if (modal) modal.classList.remove("d-none");
        if (fileLabel) fileLabel.innerText = String(filePath).split(/[/\\]/).pop() || filePath;
        if (coordBadge) coordBadge.innerText = "No cell selected";
        if (roleDiv) roleDiv.innerHTML = "Current Role: <em>None detected</em>";
        if (textPrev) textPrev.innerText = "-";
        if (gridContainer) {
          gridContainer.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 12px;">Loading 2D Virtual Grid representation...</div>';
        }

        renderSlotOverridesList();

        try {
          if (!window.pywebview?.api?.get_template_grid_preview) {
            if (gridContainer) gridContainer.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 12px;">PyWebView bridge is unavailable.</div>';
            return;
          }

          const res = await window.pywebview.api.get_template_grid_preview(filePath, 25);
          if (res && res.status === "success" && res.preview) {
            slotMapperGridData = res.preview;
            const tables = slotMapperGridData.tables || [];

            if (tableSelect) {
              tableSelect.innerHTML = tables.map((t, idx) => `
                <option value="${idx}">Table ${idx + 1} (${t.row_count}x${t.col_count})</option>
              `).join("");
              tableSelect.value = "0";
            }

            renderSlotMapperGrid();
          } else {
            showToast("Grid Preview Error", (res && res.message) || "Failed to load grid preview.", "error");
            if (gridContainer) {
              gridContainer.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--accent-rose); font-size: 12px;">${escapeHTML(res?.message || "Failed to parse grid")}</div>`;
            }
          }
        } catch (e) {
          console.error("openSlotMapperModal error:", e);
          showToast("Error", String(e), "error");
          if (gridContainer) {
            gridContainer.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--accent-rose); font-size: 12px;">${escapeHTML(String(e))}</div>`;
          }
        }
      }
      window.openSlotMapperModal = openSlotMapperModal;

      function closeSlotMapperModal() {
        const modal = document.getElementById("modalSlotMapperBackdrop");
        if (modal) modal.classList.add("d-none");
        slotMapperActivePath = null;
        slotMapperSelectedCell = null;
      }
      window.closeSlotMapperModal = closeSlotMapperModal;

      function onSlotMapperTableChange(idx) {
        slotMapperCurrentTableIndex = parseInt(idx, 10) || 0;
        slotMapperSelectedCell = null;
        renderSlotMapperGrid();
      }
      window.onSlotMapperTableChange = onSlotMapperTableChange;

      function renderSlotMapperGrid() {
        const gridContainer = document.getElementById("slotMapperGridContainer");
        const metaPill = document.getElementById("slotMapperTableMeta");
        if (!gridContainer || !slotMapperGridData) return;

        const tables = slotMapperGridData.tables || [];
        const table = tables[slotMapperCurrentTableIndex];
        if (!table) {
          gridContainer.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 12px;">No table found at this index.</div>';
          return;
        }

        if (metaPill) {
          metaPill.innerText = `Table ${slotMapperCurrentTableIndex + 1} (${table.row_count} rows x ${table.col_count} cols)`;
        }

        const maxCols = table.col_count || 1;
        let html = '<table class="slot-mapper-table"><thead><tr>';
        html += '<th style="width: 42px;">Row</th>';
        for (let c = 0; c < maxCols; c++) {
          html += `<th>Col ${c}</th>`;
        }
        html += '</tr></thead><tbody>';

        const matrix = table.grid || [];
        for (let r = 0; r < matrix.length; r++) {
          html += `<tr><td style="font-weight: 600; color: var(--text-muted); background: var(--surface-subtle); text-align: center;">${r}</td>`;
          const row = matrix[r] || [];
          for (let c = 0; c < maxCols; c++) {
            const cell = row[c];
            if (!cell) {
              html += '<td></td>';
              continue;
            }

            const isSelected = slotMapperSelectedCell && slotMapperSelectedCell.tableIdx === slotMapperCurrentTableIndex && slotMapperSelectedCell.r === r && slotMapperSelectedCell.c === c;
            const overrideKey = `${slotMapperCurrentTableIndex}_${r}_${c}`;
            const staged = slotMapperStagedOverrides[overrideKey];

            let cellClasses = ['slot-mapper-cell'];
            if (isSelected) cellClasses.push('cell-selected');
            if (cell.is_merged_continuation) cellClasses.push('cell-continuation');
            if (staged) cellClasses.push('cell-has-slot');
            else if (cell.bound_role) {
              if (cell.bound_role.includes('roster')) cellClasses.push('cell-is-roster');
              else if (cell.bound_role.includes('signatory')) cellClasses.push('cell-is-signatory');
              else cellClasses.push('cell-has-slot');
            }

            let badgeHtml = '';
            if (staged) {
              badgeHtml = `<div class="slot-cell-badge">⚡ ${escapeHTML(staged.field)} (${escapeHTML(staged.strategy)})</div>`;
            } else if (cell.bound_role) {
              const isRoster = cell.bound_role.includes('roster');
              const isSig = cell.bound_role.includes('signatory');
              const bCls = isRoster ? 'badge-roster' : (isSig ? 'badge-sig' : '');
              badgeHtml = `<div class="slot-cell-badge ${bCls}">${escapeHTML(cell.bound_role)}</div>`;
            }

            const rawText = escapeHTML(cell.text || '');
            const spanAttr = `rowspan="${cell.rowspan || 1}" colspan="${cell.colspan || 1}"`;
            html += `
              <td
                class="${cellClasses.join(' ')}"
                tabindex="0"
                role="gridcell"
                aria-label="Row ${r}, Column ${c}: ${cell.text ? escapeHTML(cell.text.substring(0, 30)) : 'Empty'}"
                onclick="selectSlotMapperCell(${slotMapperCurrentTableIndex}, ${r}, ${c})"
                onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();selectSlotMapperCell(${slotMapperCurrentTableIndex}, ${r}, ${c});}"
              >
                <div style="font-size: 11px; max-height: 48px; overflow: hidden; text-overflow: ellipsis; word-break: break-word;">${rawText || '<span style="color:var(--text-muted);">&mdash;</span>'}</div>
                ${badgeHtml}
              </td>
            `;
          }
          html += '</tr>';
        }
        html += '</tbody></table>';

        gridContainer.innerHTML = html;
      }

      function selectSlotMapperCell(tableIdx, r, c) {
        slotMapperSelectedCell = { tableIdx, r, c };

        const coordBadge = document.getElementById("slotMapperCoordBadge");
        const roleDiv = document.getElementById("slotMapperCurrentRole");
        const textPrev = document.getElementById("slotMapperTextPreview");
        const fieldSelect = document.getElementById("slotMapperFieldSelect");
        const stratSelect = document.getElementById("slotMapperStrategySelect");
        const customInput = document.getElementById("slotMapperCustomFieldInput");
        const customContainer = document.getElementById("slotMapperCustomFieldContainer");

        const tables = (slotMapperGridData && slotMapperGridData.tables) || [];
        const table = tables[tableIdx];
        const cell = table?.grid?.[r]?.[c] || { row: r, col: c, text: "", rowspan: 1, colspan: 1, bound_role: null };

        if (coordBadge) coordBadge.innerText = `Row ${r}, Col ${c} (${cell.rowspan}x${cell.colspan})`;
        if (roleDiv) roleDiv.innerHTML = `Current Role: <strong>${escapeHTML(cell.bound_role || 'None detected')}</strong>`;
        if (textPrev) textPrev.innerText = cell.text || '(empty cell)';

        const overrideKey = `${tableIdx}_${r}_${c}`;
        const staged = slotMapperStagedOverrides[overrideKey];
        if (staged) {
          const isStandard = ['instructor', 'course_code', 'course_title', 'section', 'schedule_code', 'semester', 'academic_year', 'campus', 'college', 'department', 'room'].includes(staged.field);
          if (fieldSelect) {
            fieldSelect.value = isStandard ? staged.field : 'custom';
          }
          if (customContainer) {
            if (!isStandard) {
              customContainer.classList.remove('d-none');
              if (customInput) customInput.value = staged.field;
            } else {
              customContainer.classList.add('d-none');
            }
          }
          if (stratSelect && staged.strategy) stratSelect.value = staged.strategy;
        }

        renderSlotMapperGrid();
      }
      window.selectSlotMapperCell = selectSlotMapperCell;

      function onSlotFieldSelectChange(val) {
        const customContainer = document.getElementById("slotMapperCustomFieldContainer");
        if (customContainer) {
          if (val === "custom") customContainer.classList.remove("d-none");
          else customContainer.classList.add("d-none");
        }
      }
      window.onSlotFieldSelectChange = onSlotFieldSelectChange;

      function applyCellSlotOverride() {
        if (!slotMapperSelectedCell) {
          showToast("No Cell Selected", "Click on any grid cell first.", "warning");
          return;
        }

        const fieldSelect = document.getElementById("slotMapperFieldSelect");
        const customInput = document.getElementById("slotMapperCustomFieldInput");
        const stratSelect = document.getElementById("slotMapperStrategySelect");

        let field = fieldSelect ? fieldSelect.value : "instructor";
        if (field === "custom") {
          field = customInput ? customInput.value.trim() : "";
          if (!field) {
            showToast("Missing Field Name", "Please specify a custom slot field name.", "warning");
            return;
          }
        }

        const strategy = stratSelect ? stratSelect.value : "exact_cell";
        const { tableIdx, r, c } = slotMapperSelectedCell;
        const key = `${tableIdx}_${r}_${c}`;

        slotMapperStagedOverrides[key] = {
          table_index: tableIdx,
          row: r,
          col: c,
          field: field,
          strategy: strategy,
        };

        renderSlotMapperGrid();
        renderSlotOverridesList();
        showToast("Slot Assigned", `Bound {{${field}}} (${strategy}) to Table ${tableIdx + 1} [${r}, ${c}]`, "success");
      }
      window.applyCellSlotOverride = applyCellSlotOverride;

      function removeCellSlotOverride() {
        if (!slotMapperSelectedCell) return;
        const { tableIdx, r, c } = slotMapperSelectedCell;
        const key = `${tableIdx}_${r}_${c}`;
        if (slotMapperStagedOverrides[key]) {
          delete slotMapperStagedOverrides[key];
          renderSlotMapperGrid();
          renderSlotOverridesList();
          showToast("Slot Cleared", `Cleared slot override for [${r}, ${c}]`, "info");
        }
      }
      window.removeCellSlotOverride = removeCellSlotOverride;

      function renderSlotOverridesList() {
        const listEl = document.getElementById("slotMapperOverridesList");
        const countEl = document.getElementById("slotMapperOverridesCount");
        const keys = Object.keys(slotMapperStagedOverrides);

        if (countEl) countEl.innerText = keys.length;
        if (!listEl) return;

        if (keys.length === 0) {
          listEl.innerHTML = '<div style="color: var(--text-muted); font-size: 10.5px; text-align: center; padding: 8px;">No custom overrides staged.</div>';
          return;
        }

        listEl.innerHTML = keys.map((k) => {
          const item = slotMapperStagedOverrides[k];
          return `
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 6px; border-bottom: 1px solid var(--border-subtle); gap: 6px;">
              <div>
                <strong style="color: var(--accent-emerald);">{{${escapeHTML(item.field)}}}</strong>
                <span style="color: var(--text-muted); font-size: 10px;"> &rarr; T${item.table_index + 1}[${item.row},${item.col}] (${escapeHTML(item.strategy)})</span>
              </div>
              <button
                type="button"
                class="nav-btn"
                onclick="deleteSpecificSlotOverride('${k}')"
                title="Remove Override"
                style="font-size: 10px; padding: 1px 5px; color: var(--accent-rose);"
              >✕</button>
            </div>
          `;
        }).join("");
      }

      function deleteSpecificSlotOverride(key) {
        if (slotMapperStagedOverrides[key]) {
          delete slotMapperStagedOverrides[key];
          renderSlotMapperGrid();
          renderSlotOverridesList();
        }
      }
      window.deleteSpecificSlotOverride = deleteSpecificSlotOverride;

      function resetSlotOverridesUI() {
        slotMapperStagedOverrides = {};
        renderSlotMapperGrid();
        renderSlotOverridesList();
        showToast("Overrides Reset", "Cleared all pending slot overrides.", "info");
      }
      window.resetSlotOverridesUI = resetSlotOverridesUI;

      async function saveSlotOverridesFromUI() {
        if (!slotMapperActivePath) {
          showToast("No Active Template", "No template is currently open for editing.", "warning");
          return;
        }

        try {
          if (!window.pywebview?.api?.save_template_slot_overrides) {
            showToast("Bridge Unavailable", "save_template_slot_overrides API is not ready.", "warning");
            return;
          }

          const res = await window.pywebview.api.save_template_slot_overrides(
            slotMapperActivePath,
            slotMapperStagedOverrides
          );

          if (res && res.status === "success") {
            showToast(
              "Overrides Saved",
              `Successfully applied ${Object.keys(slotMapperStagedOverrides).length} slot override(s)!`,
              "success"
            );
            closeSlotMapperModal();
            await loadCustomTemplatesUI();
          } else {
            showToast("Save Error", res?.message || "Failed to save slot overrides.", "error");
          }
        } catch (e) {
          console.error("saveSlotOverridesFromUI error:", e);
          showToast("Error", String(e), "error");
        }
      }
      window.saveSlotOverridesFromUI = saveSlotOverridesFromUI;
