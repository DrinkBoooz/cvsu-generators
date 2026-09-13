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

        function setupVisualZone(zone) {
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
            (e) => {
              e.preventDefault();
              enterCount = 0;
              zone.classList.remove("dragover");
            },
            false,
          );
        }

        setupVisualZone(document.getElementById("scheduleDropzone"));
        setupVisualZone(document.getElementById("rostersDropzone"));
        setupVisualZone(document.getElementById("templateDropzone"));
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

        // Accessible Live Announcer for Screen Readers (Narrator/NVDA)
        window.announceA11y = function(message) {
          if (!message) return;
          const el = document.getElementById("a11yLiveAnnouncer");
          if (el) {
            el.textContent = "";
            setTimeout(() => {
              el.textContent = message;
            }, 50);
          }
        };

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
