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

      async function startGeneration() {
        if (window._isGenerationRunning) return;
        window._isGenerationRunning = true;

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

        // Validate basic inputs using non-blocking toasts
        if (!state.schedulePath) {
          window._isGenerationRunning = false;
          showToast(
            "Schedule Required",
            "Please select or drop your Instructor Schedule (.xls / .xlsx) before proceeding.",
            "warning",
          );
          scrollToStep("cardStep1");
          return;
        }
        if (!state.rosters || state.rosters.length === 0) {
          window._isGenerationRunning = false;
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

        if (selectedClasses.length === 0) {
          window._isGenerationRunning = false;
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

        if (enabledEngines.length === 0) {
          window._isGenerationRunning = false;
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
        if (elapsedTimerInterval) clearInterval(elapsedTimerInterval);
        elapsedTimerInterval = setInterval(() => {
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

        const payload = await window.pywebview.api.run_generation(
          typeOverrides,
          dateOverrides,
          selectedClasses,
          enabledEngines,
          state.rosterConfigs,
        );

        if (
          payload &&
          (payload.status === "error" || payload.status === "cancelled")
        ) {
          onGenerationComplete(payload);
        }
      }

      // Telemetry callback called continuously from Python background thread
      window.onGenerationProgress = function (info) {
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
      window.onGenerationComplete = function (payload) {
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

        if (elapsedTimerInterval) {
          clearInterval(elapsedTimerInterval);
          elapsedTimerInterval = null;
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
            const totalFiles = ceitCount + attCount + gradeCount;

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
                (pkgs.grades?.length || 0);

              let fileRowsHtml = "";
              const addCategoryRows = (catName, files, icon) => {
                if (!files || files.length === 0) return;
                fileRowsHtml += `<div style="font-weight: 700; color: var(--text-primary); font-size: 11.5px; margin-top: 6px; margin-bottom: 2px;">${catName} (${files.length}):</div>`;
                files.forEach((item) => {
                  let fPath = "";
                  let fname = "";
                  if (typeof item === "object" && item !== null) {
                    fPath = item.path || item.name || "";
                    fname =
                      item.name ||
                      (fPath ? fPath.split(/[\\/]/).pop() : "File");
                  } else {
                    fPath = String(item || "");
                    fname = fPath ? fPath.split(/[\\/]/).pop() : "File";
                  }
                  fileRowsHtml += `
                    <div class="artifact-file-row">
                      <span title="${escapeHTML(fPath)}">${icon} ${escapeHTML(fname)}</span>
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
        if (elapsedTimerInterval) {
          clearInterval(elapsedTimerInterval);
          elapsedTimerInterval = null;
        }
        showToast(
          "Error",
          "Generation encountered an unexpected runtime error.",
          "error",
        );
      };
