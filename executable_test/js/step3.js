// ── Step 3: Execution, Cancellation & Telemetry ───────────────────────
      async function cancelGeneration() {
        const btnCancel = document.getElementById("btnCancelGeneration");
        if (btnCancel) {
          btnCancel.disabled = true;
          btnCancel.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
            Cancelling...
          `;
        }
        if (window._progressPollingInterval) {
          clearInterval(window._progressPollingInterval);
          window._progressPollingInterval = null;
        }
        showToast(
          "Cancelling Generation",
          "Stopping after current file completes...",
          "warning",
        );
        if (
          window.pywebview &&
          window.pywebview.api &&
          window.pywebview.api.cancel_generation
        ) {
          await window.pywebview.api.cancel_generation();
        }
      }

      async function openArtifactFile(filePath) {
        if (
          !window.pywebview ||
          !window.pywebview.api ||
          !window.pywebview.api.open_file
        )
          return;
        try {
          const res = await window.pywebview.api.open_file(filePath);
          if (res && res.status === "error") {
            showToast("Could Not Open File", res.message || "File not found", "error");
            return;
          }
          const name = filePath
            ? String(filePath).split(/[\\/]/).pop()
            : "Document";
          showToast("Opening Document", name, "info", 2500);
        } catch (e) {
          showToast("Could Not Open File", String(e), "error");
        }
      }

      window._generationSequence = window._generationSequence || 0;
      window._activeGenerationId = null;
      window._generationState = "idle";

      async function startGeneration() {
        if (window._isGenerationRunning || window._generationState !== "idle") return;
        window._isGenerationRunning = true;
        window._generationState = "running";
        const currentGenId = ++window._generationSequence;
        window._activeGenerationId = currentGenId;

        const btn = document.getElementById("processBtn");
        const btnLabel = document.getElementById("processBtnLabel");
        const progressContainer = document.getElementById("progressContainer");
        const progressFill = document.getElementById("progressFill");
        const progressPercent = document.getElementById("progressPercent");
        const progressTaskLabel = document.getElementById("progressTaskLabel");
        const progressElapsedTimer = document.getElementById(
          "progressElapsedTimer",
        );
        const btnCancel = document.getElementById("btnCancelGeneration");
        const resultsCard = document.getElementById("resultsCard");
        const readiness = getGenerationReadiness();

        // Validate basic inputs using non-blocking toasts
        if (!readiness.schedule) {
          window._isGenerationRunning = false;
          window._generationState = "idle";
          window._activeGenerationId = null;
          showToast(
            "Schedule Required",
            "Please select or drop your Instructor Schedule (.xls / .xlsx) before proceeding.",
            "warning",
          );
          scrollToStep("cardStep1");
          return;
        }
        if (!readiness.rosters) {
          window._isGenerationRunning = false;
          window._generationState = "idle";
          window._activeGenerationId = null;
          showToast(
            "Rosters Required",
            "Please select or drop at least one Student Roster file before proceeding.",
            "warning",
          );
          scrollToStep("cardStep2");
          return;
        }
        if (!state.outputDir) {
          window._isGenerationRunning = false;
          window._generationState = "idle";
          window._activeGenerationId = null;
          showToast(
            "Output Folder Required",
            "Please select a Target Output Folder for saving documents.",
            "warning",
          );
          scrollToStep("cardStep5");
          return;
        }

        // Collect class filter
        const selectedClasses = [];
        document.querySelectorAll(".item-class-check:checked").forEach((cb) => {
          selectedClasses.push(cb.getAttribute("data-class-id"));
        });

        if (!readiness.classes) {
          window._isGenerationRunning = false;
          window._generationState = "idle";
          window._activeGenerationId = null;
          showToast(
            "No Classes Selected",
            "Please select at least one class to generate.",
            "warning",
          );
          scrollToStep("cardStep3");
          return;
        }

        // Collect engine filter
        const enabledEngines = [];
        if (state.engines.attendance) enabledEngines.push("attendance");
        if (state.engines.ceit) enabledEngines.push("ceit");
        if (state.engines.grades) enabledEngines.push("grades");

        if (!readiness.engines || enabledEngines.length === 0) {
          window._isGenerationRunning = false;
          window._generationState = "idle";
          window._activeGenerationId = null;
          showToast(
            "No Packages Selected",
            "Please enable at least one document package (Attendance, CEIT Forms, or Grades).",
            "warning",
          );
          scrollToStep("cardStep3");
          return;
        }

        // Collect type overrides
        const typeOverrides = {};
        document.querySelectorAll(".class-type-select").forEach((sel) => {
          const cid = sel.getAttribute("data-class-id");
          if (cid) typeOverrides[cid] = sel.value;
        });

        // Collect date boundaries
        let dateOverrides = null;
        const startVal = document.getElementById("startDate").value;
        const endVal = document.getElementById("endDate").value;
        if (startVal && endVal) {
          const [sY, sM, sD] = startVal.split("-").map(Number);
          const [eY, eM, eD] = endVal.split("-").map(Number);
          if (sY && sM && sD && eY && eM && eD) {
            dateOverrides = {
              startYear: sY,
              startMonth: sM,
              startDay: sD,
              endYear: eY,
              endMonth: eM,
              endDay: eD,
            };
          }
        }

        // Lock button and open progress container
        setGenerationRunningState(true, "Compiling Documents...");
        progressContainer.classList.remove("d-none");
        resultsCard.classList.add("d-none");
        progressFill.style.width = "5%";
        progressPercent.innerText = "5%";
        progressTaskLabel.innerText = "Initializing generation pipeline...";

        // Reset and start stopwatch timer
        generationStartTime = Date.now();
        if (progressElapsedTimer) progressElapsedTimer.innerText = "⏱️ 00:00";
        if (window.elapsedTimerInterval) clearInterval(window.elapsedTimerInterval);
        window.elapsedTimerInterval = setInterval(() => {
          const sec = Math.floor((Date.now() - generationStartTime) / 1000);
          const m = String(Math.floor(sec / 60)).padStart(2, "0");
          const s = String(sec % 60).padStart(2, "0");
          if (progressElapsedTimer)
            progressElapsedTimer.innerText = `⏱️ ${m}:${s}`;
        }, 1000);

        if (btnCancel) {
          btnCancel.disabled = false;
          btnCancel.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
            Cancel Generation
          `;
          btnCancel.classList.remove("d-none");
        }

        const exportPdf = document.getElementById("checkExportPdf")?.checked || false;

        // Start deterministic batch progress polling fallback
        if (window._progressPollingInterval) clearInterval(window._progressPollingInterval);
        window._progressPollingInterval = setInterval(async () => {
          if (window._generationState !== "running") {
            clearInterval(window._progressPollingInterval);
            window._progressPollingInterval = null;
            return;
          }
          try {
            if (window.pywebview?.api?.get_generation_progress) {
              const prog = await window.pywebview.api.get_generation_progress();
              if (prog && prog.status === "running") {
                const pct = prog.percent || 0;
                const label = `[${prog.current_index}/${prog.total_count}] Generating ${prog.current_file_label || 'documents'}...`;
                if (progressFill) progressFill.style.width = `${pct}%`;
                if (progressPercent) progressPercent.innerText = `${pct}%`;
                if (progressTaskLabel) progressTaskLabel.innerText = label;
                if (progressContainer) {
                  progressContainer.setAttribute("aria-valuenow", String(pct));
                  progressContainer.setAttribute("aria-valuetext", `${pct}% - ${label}`);
                }
              }
            }
          } catch (e) {}
        }, 350);

        try {
          const payload = await window.pywebview.api.run_generation(
            typeOverrides,
            dateOverrides,
            selectedClasses,
            enabledEngines,
            state.rosterConfigs,
            exportPdf,
          );

          if (
            payload &&
            (payload.status === "error" || payload.status === "cancelled")
          ) {
            window.onGenerationComplete(payload, currentGenId);
          }
        } catch (error) {
          console.error("Generation API failure:", error);
          window.onGenerationComplete({
            status: "error",
            message: `Generation failed: ${error?.message || error}`,
            generation_id: currentGenId,
          }, currentGenId);
        }
      }

      // Telemetry callback called continuously from Python background thread
      window.onGenerationProgress = function (info, callbackGenId = null) {
        if (window._activeGenerationId === null) {
          return;
        }
        const cbId =
          info && info.generation_id !== undefined && info.generation_id !== null
            ? info.generation_id
            : callbackGenId;

        if (cbId !== window._activeGenerationId) {
          console.warn(
            "Ignoring stale progress callback. Active:",
            window._activeGenerationId,
            "Got:",
            cbId,
          );
          return;
        }

        const fill = document.getElementById("progressFill");
        const pctDisplay = document.getElementById("progressPercent");
        const taskDisplay = document.getElementById("progressTaskLabel");
        const container = document.getElementById("progressContainer");

        const pct = info.percent || 0;
        const taskText = `${info.current_class}: ${info.current_task} (${info.step}/${info.total_steps})`;
        fill.style.width = `${pct}%`;
        pctDisplay.innerText = `${pct}%`;
        taskDisplay.innerText = taskText;

        if (container) {
          container.setAttribute("aria-valuenow", String(pct));
          container.setAttribute("aria-valuetext", `${pct}% - ${taskText}`);
        }
      };

      // Completion callback called when background thread finishes
      window.onGenerationComplete = function (payload, callbackGenId = null) {
        if (window._activeGenerationId === null) {
          console.warn("Ignoring duplicate/untracked generation callback while idle.");
          return;
        }
        const cbId =
          payload && payload.generation_id !== undefined && payload.generation_id !== null
            ? payload.generation_id
            : callbackGenId;

        if (cbId !== window._activeGenerationId) {
          console.warn(
            "Ignoring stale completion callback. Active:",
            window._activeGenerationId,
            "Got:",
            cbId,
          );
          return;
        }

        // Authoritative state transition to IDLE
        window._activeGenerationId = null;
        window._generationState = "idle";
        if (window._progressPollingInterval) {
          clearInterval(window._progressPollingInterval);
          window._progressPollingInterval = null;
        }

        const btn = document.getElementById("processBtn");
        const btnLabel = document.getElementById("processBtnLabel");
        const progressFill = document.getElementById("progressFill");
        const pctDisplay = document.getElementById("progressPercent");
        const taskDisplay = document.getElementById("progressTaskLabel");
        const container = document.getElementById("progressContainer");
        const btnCancel = document.getElementById("btnCancelGeneration");
        const resultsCard = document.getElementById("resultsCard");
        const resultsIcon = document.getElementById("resultsIcon");
        const resultsTitleText = document.getElementById("resultsTitleText");
        const resultsMessage = document.getElementById("resultsMessage");
        const metricsContainer = document.getElementById("resultsMetricsPills");
        const treeContainer = document.getElementById("fileTreeContainer");

        if (window.elapsedTimerInterval) {
          clearInterval(window.elapsedTimerInterval);
          window.elapsedTimerInterval = null;
        }

        setGenerationRunningState(false, "Initialize Workflow");
        if (btnCancel) {
          btnCancel.disabled = false;
          btnCancel.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
            Cancel Generation
          `;
          btnCancel.classList.add("d-none");
        }

        progressFill.style.width = "100%";
        if (pctDisplay) pctDisplay.innerText = "100%";
        if (container) {
          container.setAttribute("aria-valuenow", "100");
          container.setAttribute("aria-valuetext", "100% - Generation complete");
        }

        resultsCard.classList.remove(
          "d-none",
          "results-success",
          "results-error",
        );

        if (payload.status === "cancelled") {
          resultsCard.classList.add("results-error");
          resultsIcon.innerHTML = `<circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line>`;
          resultsTitleText.innerText = "Generation Cancelled";
          resultsTitleText.style.color = "var(--accent-amber)";
          if (window.announceA11y) {
            window.announceA11y("Document compilation was cancelled.");
          }
          resultsMessage.innerText =
            payload.message || "Generation was stopped by the user.";
          if (taskDisplay) taskDisplay.innerText = "Generation stopped by user";
          showToast(
            "Generation Cancelled",
            payload.message || "Process stopped.",
            "warning",
          );
          treeContainer.innerHTML = `<div class="file-tree-item" style="color: var(--text-secondary);">Generation was safely halted. Files created before cancellation are preserved in the output folder.</div>`;
        } else if (payload.status === "error") {
          resultsCard.classList.add("results-error");
          resultsIcon.innerHTML = `<circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line>`;
          resultsTitleText.innerText = "Generation Encountered Issues";
          resultsTitleText.style.color = "var(--accent-rose)";
          resultsMessage.innerText = payload.message;
          if (taskDisplay)
            taskDisplay.innerText = "Workflow failed with errors";
          showToast("Generation Encountered Issues", payload.message, "error");
          treeContainer.innerHTML = `<div class="file-tree-item" style="color: var(--accent-rose);">Click 'Logs' at the top right to view exact failure stack traces.</div>`;
        } else {
          resultsCard.classList.add("results-success");
          resultsIcon.innerHTML = `<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline>`;
          resultsTitleText.innerText = "Document Generation Succeeded!";
          resultsTitleText.style.color = "var(--accent-emerald)";
          resultsMessage.innerText = payload.message;
          if (taskDisplay)
            taskDisplay.innerText = "All tasks completed successfully";
          showToast(
            "Documents Ready",
            payload.message || "All academic forms and grade sheets generated.",
            "success",
          );

          // Render Metrics Pills
          const details = payload.details;
          if (metricsContainer && details && details.generated) {
            const ceitCount = (details.generated.ceit || []).length;
            const attCount = (details.generated.attendance || []).length;
            const gradeCount = (details.generated.grades || []).length;
            const pdfCount = (details.generated.pdf || []).length;
            const totalFiles = ceitCount + attCount + gradeCount + pdfCount;

            let elapsedStr = "0s";
            if (generationStartTime) {
              const sec = Math.round((Date.now() - generationStartTime) / 1000);
              elapsedStr = `${sec}s`;
            }

            metricsContainer.innerHTML = `
              <span class="meta-pill">📁 ${totalFiles} Total Files</span>
              <span class="meta-pill">📋 ${ceitCount} CEIT Forms</span>
              <span class="meta-pill">📅 ${attCount} Attendance</span>
              <span class="meta-pill">📊 ${gradeCount} Grade Sheets</span>
              ${pdfCount > 0 ? `<span class="meta-pill" style="border-color: var(--accent-cyan); color: var(--accent-cyan);">📄 ${pdfCount} PDFs</span>` : ""}
              <span class="meta-pill">⏱️ ${elapsedStr}</span>
            `;
          }

          // Render Interactive File Artifact Tree
          treeContainer.innerHTML = "";
          if (
            details &&
            details.by_class &&
            Object.keys(details.by_class).length > 0
          ) {
            for (const [courseSec, pkgs] of Object.entries(details.by_class)) {
              const classCard = document.createElement("div");
              classCard.className = "artifact-class-card";

              const totalClassFiles =
                (pkgs.ceit?.length || 0) +
                (pkgs.attendance?.length || 0) +
                (pkgs.grades?.length || 0) +
                (pkgs.pdf?.length || 0);

              let fileRowsHtml = "";
              const addCategoryRows = (catName, files, icon) => {
                if (!files || files.length === 0) return;
                fileRowsHtml += `<div style="font-weight: 700; color: var(--text-primary); font-size: 11.5px; margin-top: 6px; margin-bottom: 2px;">${catName} (${files.length}):</div>`;
                files.forEach((item) => {
                  let fPath = "";
                  let fname = "";
                  let isMerged = false;
                  if (typeof item === "object" && item !== null) {
                    fPath = item.path || item.name || "";
                    fname =
                      item.name ||
                      (fPath ? fPath.split(/[\\/]/).pop() : "File");
                    isMerged = !!item.is_merged || fname.toUpperCase().includes("MERGED");
                  } else {
                    fPath = String(item || "");
                    fname = fPath ? fPath.split(/[\\/]/).pop() : "File";
                    isMerged = fname.toUpperCase().includes("MERGED");
                  }
                  const rowIcon = isMerged ? "📑" : icon;
                  const bundleBadge = isMerged
                    ? `<span style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.35); font-size: 10px; padding: 1px 6px; border-radius: 4px; margin-right: 6px; font-weight: 700; display: inline-flex; align-items: center; gap: 3px;">Merged Bundle</span>`
                    : "";
                  const rowStyle = isMerged
                    ? `style="background: rgba(16, 185, 129, 0.06); border-left: 2px solid var(--accent-emerald);"`
                    : "";
                  fileRowsHtml += `
                    <div class="artifact-file-row" ${rowStyle}>
                      <span title="${escapeHTML(fPath)}" style="display: inline-flex; align-items: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${rowIcon} ${bundleBadge}${escapeHTML(fname)}</span>
                      <button class="btn-launch-file" type="button" data-path="${escapeHTML(fPath)}" onclick="openArtifactFile(this.getAttribute('data-path'))">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                          <polyline points="15 3 21 3 21 9"></polyline>
                          <line x1="10" y1="14" x2="21" y2="3"></line>
                        </svg>
                        Open
                      </button>
                    </div>
                  `;
                });
              };

              addCategoryRows("CEIT Forms", pkgs.ceit, "📄");
              addCategoryRows("Attendance Sheets", pkgs.attendance, "📅");
              addCategoryRows("Grade Sheets", pkgs.grades, "📊");
              addCategoryRows("PDF Submissions", pkgs.pdf, "📄");

              classCard.innerHTML = `
                <div class="artifact-class-header" onclick="this.nextElementSibling.classList.toggle('d-none')">
                  <span>📁 ${escapeHTML(courseSec)} (${totalClassFiles} files)</span>
                  <span style="font-size: 11px; color: var(--accent-emerald);">▼ Details</span>
                </div>
                <div class="artifact-class-body">
                  ${fileRowsHtml}
                </div>
              `;
              treeContainer.appendChild(classCard);
            }
          } else if (details && details.generated) {
            const ceit = details.generated.ceit || [];
            const att = details.generated.attendance || [];
            const grades = details.generated.grades || [];

            if (ceit.length > 0) {
              treeContainer.innerHTML += `<div style="font-weight: 700; color: var(--text-primary); margin-top: 4px;">📁 CEIT Department Forms (${ceit.length} files):</div>`;
              ceit.slice(0, 10).forEach((f) => {
                treeContainer.innerHTML += `<div class="file-tree-item">📄 ${escapeHTML(f)}</div>`;
              });
              if (ceit.length > 10)
                treeContainer.innerHTML += `<div class="file-tree-item text-muted">... and ${ceit.length - 10} more CEIT files</div>`;
            }

            if (att.length > 0) {
              treeContainer.innerHTML += `<div style="font-weight: 700; color: var(--text-primary); margin-top: 8px;">📁 Attendance Sheets (${att.length} files):</div>`;
              att.slice(0, 8).forEach((f) => {
                treeContainer.innerHTML += `<div class="file-tree-item">📅 ${escapeHTML(f)}</div>`;
              });
              if (att.length > 8)
                treeContainer.innerHTML += `<div class="file-tree-item text-muted">... and ${att.length - 8} more attendance files</div>`;
            }

            if (grades.length > 0) {
              treeContainer.innerHTML += `<div style="font-weight: 700; color: var(--text-primary); margin-top: 8px;">📁 Official Grade Sheets (${grades.length} files):</div>`;
              grades.forEach((f) => {
                treeContainer.innerHTML += `<div class="file-tree-item">📊 ${escapeHTML(f)}</div>`;
              });
            }
          }
        }
        updateStepperStatus();
      };

      window.onGenerationError = function () {
        setGenerationRunningState(false, "Initialize Workflow");
        const btnCancel = document.getElementById("btnCancelGeneration");
        if (btnCancel) btnCancel.classList.add("d-none");
        if (window.elapsedTimerInterval) {
          clearInterval(window.elapsedTimerInterval);
          window.elapsedTimerInterval = null;
        }
        showToast(
          "Error",
          "Generation encountered an unexpected runtime error.",
          "error",
        );
      };

      // ── In-Memory Pre-Flight Sample Document Preview Controller ───────────
      async function openPreflightPreviewModal() {
        const readiness = getGenerationReadiness();
        if (!readiness.schedule) {
          showToast(
            "Schedule Required",
            "Please select or drop your Instructor Schedule (.xls / .xlsx) before previewing.",
            "warning",
          );
          scrollToStep("cardStep1");
          return;
        }
        if (!readiness.rosters) {
          showToast(
            "Rosters Required",
            "Please select or drop at least one Student Roster file before previewing.",
            "warning",
          );
          scrollToStep("cardStep2");
          return;
        }

        const modal = document.getElementById("modalPreflightPreviewBackdrop");
        if (modal) modal.classList.remove("d-none");

        const badge = document.getElementById("previewFontScalingBadge");
        const slotsBody = document.getElementById("previewResolvedSlotsBody");
        const rosterBody = document.getElementById("previewRosterTableBody");
        const sigsList = document.getElementById("previewSignatoriesList");

        const infoCourseSec = document.getElementById("previewInfoCourseSec");
        const infoSchedCode = document.getElementById("previewInfoSchedCode");
        const infoSubject = document.getElementById("previewInfoSubject");
        const infoInstructor = document.getElementById("previewInfoInstructor");
        const infoStudentCount = document.getElementById("previewInfoStudentCount");
        const infoFontTier = document.getElementById("previewInfoFontTier");

        if (badge) {
          badge.innerText = "Analyzing Section...";
          badge.style.background = "var(--surface-subtle)";
          badge.style.color = "var(--text-secondary)";
        }
        if (slotsBody) {
          slotsBody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: var(--text-muted); padding: 14px;">Synthesizing sample document in memory...</td></tr>';
        }
        if (rosterBody) {
          rosterBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 14px;">Loading sample student records...</td></tr>';
        }
        if (sigsList) {
          sigsList.innerHTML = '<span style="color: var(--text-muted);">Resolving signatory chain hierarchy...</span>';
        }

        // Collect class filter & overrides
        const selectedClasses = [];
        document.querySelectorAll(".item-class-check:checked").forEach((cb) => {
          selectedClasses.push(cb.getAttribute("data-class-id"));
        });
        const enabledEngines = [];
        if (state.engines.attendance) enabledEngines.push("attendance");
        if (state.engines.ceit) enabledEngines.push("ceit");
        if (state.engines.grades) enabledEngines.push("grades");

        const typeOverrides = {};
        document.querySelectorAll(".class-type-select").forEach((sel) => {
          const cid = sel.getAttribute("data-class-id");
          if (cid) typeOverrides[cid] = sel.value;
        });

        try {
          if (!window.pywebview?.api?.preview_sample_document) {
            showToast("Bridge Unavailable", "preview_sample_document API is not ready.", "warning");
            return;
          }

          const payload = {
            schedule_path: state.schedulePath,
            roster_paths: state.rosterPaths,
            selected_classes: selectedClasses,
            enabled_engines: enabledEngines,
            class_type_overrides: typeOverrides,
            roster_configs: state.rosterConfigs || {},
          };

          const res = await window.pywebview.api.preview_sample_document(payload);
          if (!res || res.status === "error") {
            showToast("Preview Error", res?.message || "Failed to generate sample preview.", "error");
            if (slotsBody) slotsBody.innerHTML = `<tr><td colspan="2" style="color: var(--accent-rose); padding: 10px;">${escapeHTML(res?.message || "Preview error")}</td></tr>`;
            return;
          }

          const fontPt = res.active_font_pt || "8pt";
          const count = res.student_count || 0;
          const slots = res.resolved_slots || {};
          const rows = res.sample_roster_rows || [];
          const sigs = res.signatory_chain || [];

          if (badge) {
            badge.innerText = `${fontPt} Tier (${count} Students)`;
            if (fontPt === "8pt") {
              badge.style.background = "var(--accent-emerald)";
              badge.style.color = "#fff";
            } else if (fontPt === "7pt") {
              badge.style.background = "var(--accent-amber)";
              badge.style.color = "#000";
            } else {
              badge.style.background = "var(--accent-rose)";
              badge.style.color = "#fff";
            }
          }

          if (infoCourseSec) infoCourseSec.innerText = res.course_sec || slots.section || "-";
          if (infoSchedCode) infoSchedCode.innerText = res.schedule_code || slots.schedule_code || "-";
          if (infoSubject) infoSubject.innerText = res.subject || slots.course_code || "-";
          if (infoInstructor) infoInstructor.innerText = res.instructor || slots.instructor || "-";
          if (infoStudentCount) infoStudentCount.innerText = String(count);
          if (infoFontTier) infoFontTier.innerText = fontPt;

          // Render Slots Table
          if (slotsBody) {
            const entries = Object.entries(slots);
            if (entries.length === 0) {
              slotsBody.innerHTML = '<tr><td colspan="2" style="color: var(--text-muted); padding: 10px;">No slots resolved.</td></tr>';
            } else {
              slotsBody.innerHTML = entries.map(([field, val]) => `
                <tr>
                  <td style="font-weight: 600; color: var(--text-secondary);"><code style="color: var(--accent-emerald);">{{${escapeHTML(field)}}}</code></td>
                  <td style="color: var(--text-primary);">${escapeHTML(String(val))}</td>
                </tr>
              `).join("");
            }
          }

          // Render Roster Table (first 10)
          if (rosterBody) {
            if (rows.length === 0) {
              rosterBody.innerHTML = '<tr><td colspan="4" style="color: var(--text-muted); padding: 10px;">No students found in sample roster.</td></tr>';
            } else {
              rosterBody.innerHTML = rows.map((st, idx) => `
                <tr>
                  <td style="color: var(--text-muted); text-align: center;">${idx + 1}</td>
                  <td style="font-family: monospace;">${escapeHTML(st.student_id || "-")}</td>
                  <td><strong>${escapeHTML(st.name || "-")}</strong></td>
                  <td>${escapeHTML(st.gender || "-")}</td>
                </tr>
              `).join("");
            }
          }

          // Render Signatories Hierarchy
          if (sigsList) {
            if (sigs.length === 0) {
              sigsList.innerHTML = '<span style="color: var(--text-muted);">Standard university signatories apply.</span>';
            } else {
              sigsList.innerHTML = sigs.map((s, idx) => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border-bottom: 1px solid var(--border-subtle);">
                  <div>
                    <strong>${idx + 1}. ${escapeHTML(s.role_label || s.title || 'Signatory')}</strong>: 
                    <span>${escapeHTML(s.signatory_name || s.name || 'Pending Faculty')}</span>
                  </div>
                  <span class="filter-pill" style="font-size: 10px; padding: 1px 6px;">${escapeHTML(s.bound_key || '')}</span>
                </div>
              `).join("");
            }
          }
        } catch (e) {
          console.error("openPreflightPreviewModal error:", e);
          showToast("Error", String(e), "error");
        }
      }
      window.openPreflightPreviewModal = openPreflightPreviewModal;

      function closePreflightPreviewModal() {
        const modal = document.getElementById("modalPreflightPreviewBackdrop");
        if (modal) modal.classList.add("d-none");
      }
      window.closePreflightPreviewModal = closePreflightPreviewModal;
