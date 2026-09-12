// ── Callbacks Invoked from Python (Bridge / Native DnD) ────────────────
      window.onScheduleLoaded = async function (res) {
        if (res && res.path) {
          state.schedulePath = res.path;
          state.scheduleMeta = res.metadata;
          if (res.validation && res.validation.length > 0) {
            state.rosterReports = res.validation;
            renderRosterStatus();
          }
          renderScheduleStatus();
          await refreshClassDetection();
          updateStepperStatus();
          updateFileEstimate();
          showToast(
            "Schedule Loaded",
            `Loaded schedule for ${state.scheduleMeta?.instructor || "Instructor"}`,
            "success",
          );
        }
      };

      window.onRostersLoaded = async function (res) {
        if (res) {
          state.rosters = res.rosters || [];
          state.rosterReports = res.validation || [];
          renderRosterStatus();
          await refreshClassDetection();
          updateStepperStatus();
          updateFileEstimate();
          showToast(
            "Rosters Loaded",
            `${state.rosters.length} student roster files loaded.`,
            "success",
          );
        }
      };

      window.onGenerationProgress = function (info) {
        if (typeof handleGenerationProgress === "function") {
          handleGenerationProgress(info);
        }
      };

      window.onGenerationComplete = function (payload) {
        if (typeof handleGenerationComplete === "function") {
          handleGenerationComplete(payload);
        }
      };

      window.onGenerationError = function () {
        if (typeof handleGenerationError === "function") {
          handleGenerationError();
        }
      };

      window.renderCustomTemplateInspection = function (res) {
        if (typeof handleCustomTemplateInspection === "function") {
          handleCustomTemplateInspection(res);
        }
      };

      function initDragAndDrop() {
        window.addEventListener(
          "dragover",
          (e) => {
            e.preventDefault();
          },
          false,
        );

        window.addEventListener(
          "drop",
          (e) => {
            e.preventDefault();
          },
          false,
        );

        function setupVisualZone(zone, onFiles) {
          if (!zone) return;
          let enterCount = 0;

          zone.addEventListener(
            "dragenter",
            (e) => {
              e.preventDefault();
              enterCount++;
              zone.classList.add("dragover");
            },
            false,
          );

          zone.addEventListener(
            "dragover",
            (e) => {
              e.preventDefault();
              if (e.dataTransfer) {
                e.dataTransfer.dropEffect = "copy";
              }
              zone.classList.add("dragover");
            },
            false,
          );

          zone.addEventListener(
            "dragleave",
            (e) => {
              e.preventDefault();
              enterCount--;
              if (enterCount <= 0) {
                enterCount = 0;
                zone.classList.remove("dragover");
              }
            },
            false,
          );

          zone.addEventListener(
            "drop",
            async (e) => {
              e.preventDefault();
              enterCount = 0;
              zone.classList.remove("dragover");

              const files = e.dataTransfer ? e.dataTransfer.files : null;
              if (files && files.length > 0 && onFiles) {
                await onFiles(Array.from(files));
              }
            },
            false,
          );
        }

        setupVisualZone(
          document.getElementById("scheduleDropzone"),
          async (files) => {
            if (!window.pywebview || !window.pywebview.api) return;
            const file = files[0];
            const path = file.pywebviewFullPath || file.path;
            if (path) {
              const res = await window.pywebview.api.handle_dropped_schedule(
                file.name,
                path,
              );
              window.onScheduleLoaded(res);
            }
          },
        );

        setupVisualZone(
          document.getElementById("rostersDropzone"),
          async (files) => {
            if (!window.pywebview || !window.pywebview.api) return;
            const payloads = files
              .filter(
                (f) =>
                  !f.name.startsWith("~$") && (f.pywebviewFullPath || f.path),
              )
              .map((f) => ({
                filename: f.name,
                path: f.pywebviewFullPath || f.path,
                data: null,
              }));
            if (payloads.length > 0) {
              const res = await window.pywebview.api.handle_dropped_rosters(
                payloads,
                state.rosterConfigs,
              );
              window.onRostersLoaded(res);
            }
          },
        );

        setupVisualZone(
          document.getElementById("templateDropzone"),
          async (files) => {
            if (!window.pywebview || !window.pywebview.api) return;
            const file = files[0];
            if (!file) return;
            if (!file.name.toLowerCase().endsWith(".docx")) {
              showToast(
                "Invalid File",
                "Please drop a Word .docx document template.",
                "warning",
              );
              return;
            }
            const path = file.pywebviewFullPath || file.path;
            let res = null;
            if (path && window.pywebview.api.inspect_custom_template) {
              res = await window.pywebview.api.inspect_custom_template(path);
            }
            if (res && res.status === "success") {
              renderCustomTemplateInspection(res);
            } else if (res) {
              showToast(
                "Inspection Error",
                res.message || "Could not analyze template",
                "error",
              );
            }
          },
        );
      }

      document.addEventListener("DOMContentLoaded", () => {
        loadSavedTheme();
        loadSavedDates();
        initDragAndDrop();
        loadCustomTemplatesUI();
        if (state.outputDir) {
          document.getElementById("outputDisplay").value = state.outputDir;
          const statusDisplay = document.getElementById("outputPathStatus");
          if (statusDisplay) {
            statusDisplay.innerHTML = `<span style="color: var(--accent-emerald);">✔ Ready:</span> ${escapeHTML(state.outputDir)}`;
          }
        }
        renderActiveMonths();
        updateStepperStatus();
        updateFileEstimate();
        initScrollAwareDock();
        initStepperScrollSpy();

        // Global Escape dismissal for modal & slide-over drawers
        document.addEventListener("keydown", (e) => {
          if (e.key === "Escape") {
            const confirmModal = document.getElementById("modalAppleConfirmBackdrop");
            if (confirmModal && !confirmModal.classList.contains("d-none")) {
              dismissAppleConfirm();
              return;
            }
            const settingsModal = document.getElementById("modalParserSettingsBackdrop");
            if (settingsModal && !settingsModal.classList.contains("d-none")) {
              closeSettingsModal();
              return;
            }
            const modal = document.getElementById("modalRosterMappingBackdrop");
            if (modal && !modal.classList.contains("d-none")) {
              closeColumnMappingModal();
              return;
            }
            const activeDrawer = document.querySelector(".drawer-panel.active");
            if (activeDrawer) {
              closeAllDrawers();
            }
          }
        });
      });
