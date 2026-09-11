// ── Step 1: Schedule Ingestion ────────────────────────────────────────
      async function loadSchedule() {
        if (!window.pywebview || !window.pywebview.api) return;
        const res = await window.pywebview.api.browse_schedule();
        if (res && res.cancelled) return;
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
      }

      function renderScheduleStatus() {
        const dropzone = document.getElementById("scheduleDropzone");
        const filenameDisplay = document.getElementById("scheduleFilename");
        const promptDisplay = document.getElementById("schedulePrompt");
        const banner = document.getElementById("instructorBanner");
        const fmtBadge = document.getElementById("scheduleFormatBadge");
        const btnReset = document.getElementById("btnResetSchedule");

        if (state.schedulePath) {
          const baseName = state.schedulePath.split(/[\\/]/).pop();
          promptDisplay.classList.add("d-none");
          filenameDisplay.classList.remove("d-none");
          filenameDisplay.innerText = baseName;
          dropzone.style.borderColor = "var(--accent-emerald)";

          const ext = baseName.toUpperCase().endsWith(".XLS")
            ? ".XLS"
            : ".XLSX";
          if (fmtBadge) {
            fmtBadge.innerText = ext;
            fmtBadge.classList.remove("d-none");
          }
          if (btnReset) btnReset.classList.remove("d-none");

          if (state.scheduleMeta) {
            banner.classList.remove("d-none");
            document.getElementById("instructorName").innerText =
              state.scheduleMeta.instructor || "Instructor";
            document.getElementById("instructorCollege").innerText =
              state.scheduleMeta.college ||
              "College of Engineering and Information Technology";
            document.getElementById("instructorSemPill").innerText =
              state.scheduleMeta.semester || "Semester Schedule";
            document.getElementById("instructorSlotsPill").innerText =
              `${state.scheduleMeta.total_slots || 0} Scheduled Slots`;

            const initials = (state.scheduleMeta.instructor || "DO")
              .split(" ")
              .filter((p) => p.length > 0)
              .map((p) => p[0])
              .slice(0, 2)
              .join("");
            document.getElementById("instructorInitials").innerText = initials;
          }
        } else {
          promptDisplay.classList.remove("d-none");
          filenameDisplay.classList.add("d-none");
          banner.classList.add("d-none");
          if (fmtBadge) fmtBadge.classList.add("d-none");
          if (btnReset) btnReset.classList.add("d-none");
          dropzone.style.borderColor = "var(--border-subtle)";
        }
      }

      async function resetSchedule() {
        if (
          window.pywebview &&
          window.pywebview.api &&
          window.pywebview.api.clear_schedule
        ) {
          try {
            await window.pywebview.api.clear_schedule();
          } catch (e) {
            console.error("Failed to clear schedule in backend:", e);
          }
        }
        state.schedulePath = "";
        state.scheduleMeta = null;
        renderScheduleStatus();
        await refreshClassDetection();
        updateStepperStatus();
        updateFileEstimate();
        showToast(
          "Schedule Reset",
          "Instructor master schedule cleared.",
          "info",
        );
      }

      // ── Step 1: Rosters Ingestion ─────────────────────────────────────────
      async function loadRosters() {
        if (!window.pywebview || !window.pywebview.api) return;
        const res = await window.pywebview.api.browse_rosters(
          state.rosterConfigs,
        );
        if (res && res.cancelled) return;
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
      }

      async function removeRoster(idx) {
        if (!window.pywebview || !window.pywebview.api) return;
        const res = await window.pywebview.api.remove_roster(
          idx,
          state.rosterConfigs,
        );
        if (res) {
          state.rosters = res.rosters || [];
          state.rosterReports = res.validation || [];
          renderRosterStatus();
          await refreshClassDetection();
          updateStepperStatus();
          updateFileEstimate();
        }
      }

      async function clearAllRosters() {
        if (!window.pywebview || !window.pywebview.api) return;
        if (state.rosters && state.rosters.length > 0) {
          const confirmed = await showAppleConfirm({
            title: "Clear All Rosters",
            message: `Are you sure you want to remove all ${state.rosters.length} imported rosters?`,
            confirmText: "Remove All",
            cancelText: "Cancel",
            isDestructive: true,
          });
          if (!confirmed) return;
        }
        const res = await window.pywebview.api.clear_rosters();
        state.rosters = [];
        state.rosterReports = [];
        renderRosterStatus();
        await refreshClassDetection();
        updateStepperStatus();
        updateFileEstimate();
        showToast(
          "Rosters Cleared",
          "All student rosters have been removed.",
          "info",
        );
      }

      function filterRostersList(query) {
        const q = (query || "").trim().toLowerCase();
        const rows = document.querySelectorAll(
          "#rosterRowsContainer .roster-row",
        );
        rows.forEach((row) => {
          const title = (
            row.querySelector(".roster-title")?.innerText || ""
          ).toLowerCase();
          row.style.display = !q || title.includes(q) ? "flex" : "none";
        });
      }

      function renderRosterStatus() {
        const dropzone = document.getElementById("rostersDropzone");
        const filenameDisplay = document.getElementById("rostersFilename");
        const promptDisplay = document.getElementById("rostersPrompt");
        const listBox = document.getElementById("rosterListBox");
        const container = document.getElementById("rosterRowsContainer");
        const badge = document.getElementById("rosterCountBadge");
        const totBadge = document.getElementById("rosterTotalStudentsBadge");
        const autoStrip = document.getElementById("autoStripCheck")
          ? document.getElementById("autoStripCheck").checked
          : true;

        if (state.rosters && state.rosters.length > 0) {
          promptDisplay.classList.add("d-none");
          filenameDisplay.classList.remove("d-none");
          filenameDisplay.innerText = `${state.rosters.length} files selected`;
          dropzone.style.borderColor = "var(--accent-emerald)";

          listBox.classList.remove("d-none");
          badge.innerText = state.rosters.length;
          container.innerHTML = "";

          let totalStudents = 0;
          state.rosterReports.forEach((rep, idx) => {
            if (rep.student_count) totalStudents += rep.student_count;

            const row = document.createElement("div");
            row.className = "roster-row";

            let statusBadge = `<span class="badge-status badge-valid">Ready</span>`;
            if (rep.issue === "incomplete_filename") {
              if (rep.suggested_matches && rep.suggested_matches.length > 0) {
                statusBadge = `<span class="badge-status badge-warning" title="Incomplete filename details. Matching timetable candidate found.">⚠️ Incomplete Details</span>`;
              } else {
                statusBadge = `<span class="badge-status badge-error" title="Incomplete filename details. Please supply schedule code and subject title.">⚠️ Incomplete Details</span>`;
              }
            } else if (rep.status === "warning") {
              if (autoStrip) {
                statusBadge = `<span class="badge-status badge-valid" title="Auto-Cleaned: Name &amp; Student number isolated safely">🛡️ Auto-Cleaned</span>`;
              } else {
                statusBadge = `<span class="badge-status badge-warning" title="Warning: ${rep.column_count} columns found. Roster files must strictly contain only Name and Student number.">⚠️ Extra Columns</span>`;
              }
            } else if (rep.status === "error") {
              statusBadge = `<span class="badge-status badge-error" title="${escapeHTML(rep.message)}">Invalid Name</span>`;
            }

            // CEIT department pill badge
            let ceitBadgeHtml = "";
            if (rep.ceit_metadata) {
              ceitBadgeHtml = `<span class="badge-ceit-pill" title="${escapeHTML(rep.ceit_metadata.department_name)}">${escapeHTML(rep.ceit_metadata.prefix)} · ${escapeHTML(rep.ceit_metadata.department_code)}</span>`;
            }

            // Custom config badge
            const config =
              (state.rosterConfigs && state.rosterConfigs[rep.filename]) ||
              null;
            let customConfigBadgeHtml = "";
            if (
              config &&
              (config.header_row !== undefined ||
                config.name_column !== undefined ||
                config.id_column !== undefined ||
                config.linked_schedule_code ||
                config.course_sec ||
                config.schedule_code ||
                config.subject_name)
            ) {
              customConfigBadgeHtml = `<span class="badge-custom-mapping" title="Custom class details and column mapping configured">⚙️ Configured</span>`;
            }

            // Quick timetable match button (if incomplete filename and match found)
            let matchBtnHtml = "";
            if (
              rep.issue === "incomplete_filename" &&
              rep.suggested_matches &&
              rep.suggested_matches.length > 0
            ) {
              const topMatch = rep.suggested_matches[0];
              matchBtnHtml = `
                <button type="button" class="btn-use-match" onclick="applySuggestedMatch(decodeURIComponent('${encodeURIComponent(rep.filename)}'), decodeURIComponent('${encodeURIComponent(topMatch.schedule_code)}'), decodeURIComponent('${encodeURIComponent(topMatch.course_sec)}'), decodeURIComponent('${encodeURIComponent(topMatch.subject_name)}'))" title="Auto-link with top timetable match: ${escapeHTML(topMatch.course_sec)} (${escapeHTML(topMatch.schedule_code)})">⚡ Match: ${escapeHTML(topMatch.course_sec)}</button>
              `;
            }

            // Class linking select (shown if invalid filename, incomplete, unmatched, or if already linked)
            let linkSelectHtml = "";
            const isUnmatchedOrLinked =
              rep.status === "error" ||
              rep.can_link ||
              rep.issue === "invalid_filename" ||
              rep.issue === "incomplete_filename" ||
              (config && config.linked_schedule_code);
            if (
              isUnmatchedOrLinked &&
              state.detectedClasses &&
              state.detectedClasses.length > 0
            ) {
              const activeLinkedCode =
                (config && config.linked_schedule_code) ||
                rep.linked_schedule_code ||
                "";
              let optionsHtml = `<option value="">🔗 Link to Class...</option>`;
              state.detectedClasses.forEach((cls) => {
                const isSelected =
                  activeLinkedCode === cls.schedule_code ? "selected" : "";
                optionsHtml += `<option value="${escapeHTML(cls.schedule_code)}" ${isSelected}>${escapeHTML(cls.schedule_code)} - ${escapeHTML(cls.course_sec)} (${escapeHTML(cls.subject_name)})</option>`;
              });
              linkSelectHtml = `
                <select class="roster-class-link-select" onchange="linkRosterToClass(decodeURIComponent('${encodeURIComponent(rep.filename)}'), this.value)" title="Manually link this roster to a timetable class">
                  ${optionsHtml}
                </select>
              `;
            }

            // Official naming recommendation notice under the row
            let recNoticeHtml = "";
            if (rep.issue === "incomplete_filename") {
              const recFilename =
                rep.recommended_filename ||
                "{CourseSec} List of Students for {ScheduleCode}-{Subject}.xlsx";
              recNoticeHtml = `
                <div class="roster-item-recommendation">
                  <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                      <span style="color: var(--accent-amber); font-size: 13px;">💡</span>
                      <span style="font-size: 11.5px; color: var(--text-secondary);">
                        <strong>Recommended:</strong> Rename to official format for zero-click automation:
                        <code class="selectable" style="font-size: 11px; background: var(--surface-subtle); padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border-subtle); color: var(--accent-emerald);">${escapeHTML(recFilename)}</code>
                      </span>
                    </div>
                    <button type="button" class="btn-copy-rec-sm" onclick="copyToClipboard('${escapeHTML(recFilename)}', 'Copied recommended official filename: ${escapeHTML(recFilename)}')" title="Copy recommended official filename">📋 Copy Name</button>
                  </div>
                </div>
              `;
            }

            row.innerHTML = `
              <div class="roster-row-main">
                <div class="roster-title" title="${escapeHTML(rep.filename)}">
                  <span>${escapeHTML(rep.filename)}</span>
                  ${ceitBadgeHtml}
                  ${customConfigBadgeHtml}
                </div>
                <div class="roster-row-actions">
                  ${matchBtnHtml}
                  ${linkSelectHtml}
                  ${statusBadge}
                  <button class="btn-map-columns" type="button" onclick="openColumnMappingModal(decodeURIComponent('${encodeURIComponent(rep.filename)}'))" title="Configure class details and column mapping">⚙️ Map</button>
                  <button class="btn-remove-roster" onclick="removeRoster(${idx})" title="Remove file">&times;</button>
                </div>
              </div>
              ${recNoticeHtml}
            `;
            container.appendChild(row);
          });

          if (totBadge) {
            if (totalStudents > 0) {
              totBadge.classList.remove("d-none");
              totBadge.innerText = `${totalStudents} Total Students`;
            } else {
              totBadge.classList.add("d-none");
            }
          }

          const searchInput = document.getElementById("rosterSearchInput");
          if (searchInput && searchInput.value) {
            filterRostersList(searchInput.value);
          }
        } else {
          promptDisplay.classList.remove("d-none");
          filenameDisplay.classList.add("d-none");
          listBox.classList.add("d-none");
          if (totBadge) totBadge.classList.add("d-none");
          dropzone.style.borderColor = "var(--border-subtle)";
        }
      }

      async function linkRosterToClass(filename, scheduleCode) {
        state.rosterConfigs[filename] = state.rosterConfigs[filename] || {};
        if (scheduleCode) {
          state.rosterConfigs[filename].linked_schedule_code = scheduleCode;
        } else {
          delete state.rosterConfigs[filename].linked_schedule_code;
          if (Object.keys(state.rosterConfigs[filename]).length === 0) {
            delete state.rosterConfigs[filename];
          }
        }
        saveRosterConfigs();
        if (window.pywebview && window.pywebview.api) {
          const reports = await window.pywebview.api.validate_rosters(
            state.rosterConfigs,
          );
          state.rosterReports = reports || [];
          renderRosterStatus();
          await refreshClassDetection();
          updateStepperStatus();
          updateFileEstimate();
          if (scheduleCode) {
            showToast(
              "Class Linked",
              `Linked ${filename} to schedule ${scheduleCode}`,
              "success",
            );
          } else {
            showToast(
              "Link Cleared",
              `Cleared manual class link for ${filename}`,
              "info",
            );
          }
        }
      }

      function copyToClipboard(text, message = "Copied to clipboard!") {
        if (!text) return;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard
            .writeText(text)
            .then(() => {
              showToast("Copied", message, "info", 2200);
            })
            .catch(() => {
              fallbackCopyText(text, message);
            });
        } else {
          fallbackCopyText(text, message);
        }
      }

      function fallbackCopyText(text, message) {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try {
          document.execCommand("copy");
          showToast("Copied", message, "info", 2200);
        } catch (e) {
          showToast("Copy Failed", "Please manually copy the text", "warning");
        }
        document.body.removeChild(ta);
      }

      function copyRecommendedFilename() {
        const codeEl = document.getElementById("mapModalRecommendedFilename");
        const text = codeEl ? codeEl.innerText.trim() : "";
        if (text) {
          copyToClipboard(text, `Copied official filename: ${text}`);
        }
      }

      async function applySuggestedMatch(
        filename,
        scheduleCode,
        courseSec,
        subjectName,
      ) {
        state.rosterConfigs[filename] = state.rosterConfigs[filename] || {};
        state.rosterConfigs[filename].linked_schedule_code = scheduleCode;
        state.rosterConfigs[filename].schedule_code = scheduleCode;
        if (courseSec) state.rosterConfigs[filename].course_sec = courseSec;
        if (subjectName)
          state.rosterConfigs[filename].subject_name = subjectName;
        saveRosterConfigs();
        if (window.pywebview && window.pywebview.api) {
          const reports = await window.pywebview.api.validate_rosters(
            state.rosterConfigs,
          );
          state.rosterReports = reports || [];
          renderRosterStatus();
          await refreshClassDetection();
          updateStepperStatus();
          updateFileEstimate();
          showToast(
            "Match Applied",
            `Linked ${filename} to ${courseSec} (${scheduleCode})`,
            "success",
          );
        }
      }
