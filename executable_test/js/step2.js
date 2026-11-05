// ── Step 2: Engine Selection ──────────────────────────────────────────
      function toggleEngine(name) {
        state.engines[name] = !state.engines[name];
        document.getElementById(
          `check${name.charAt(0).toUpperCase() + name.slice(1)}`,
        ).checked = state.engines[name];
        document
          .getElementById(`chip${name.charAt(0).toUpperCase() + name.slice(1)}`)
          .classList.toggle("active", state.engines[name]);
        updateStepperStatus();
        updateFileEstimate();
      }

      // ── Step 2: Class Detection & 8-Column Packages Matrix ────────────────
      window._currentInspectedClassId = null;

      function findRosterReportForClass(cls) {
        const reports = state.rosterReports || state.rosterValidation || [];
        if (!cls || !Array.isArray(reports) || reports.length === 0) return null;
        const norm = (p) => String(p || "").replace(/\\/g, "/").trim().toLowerCase();

        // 1. Primary: exact normalized full path match on cls.roster_file
        if (cls.roster_file) {
          const targetPath = norm(cls.roster_file);
          const byPath = reports.find((r) => r.path && norm(r.path) === targetPath);
          if (byPath) return byPath;
        }

        // 2. Secondary: match via explicit schedule_code linkage in state.rosterConfigs or report
        if (cls.schedule_code) {
          const byLink = reports.find((r) => {
            const cfg = (state.rosterConfigs && state.rosterConfigs[r.filename]) || {};
            return (
              cfg.linked_schedule_code === cls.schedule_code ||
              cfg.schedule_code === cls.schedule_code ||
              r.linked_schedule_code === cls.schedule_code
            );
          });
          if (byLink) return byLink;
        }

        // 3. Tertiary: match via matched_class prefix if unambiguous
        if (cls.course_sec && cls.schedule_code) {
          const byMatched = reports.filter(
            (r) =>
              r.matched_class &&
              String(r.matched_class).includes(cls.course_sec)
          );
          if (byMatched.length === 1) return byMatched[0];
        }

        // 4. Fallback: basename match ONLY when unambiguous (exactly 1 report shares that filename)
        if (cls.roster_file) {
          const baseName = String(cls.roster_file).split(/[\\/]/).pop();
          const matches = reports.filter(
            (r) => r.filename === baseName || r.file === baseName
          );
          if (matches.length === 1) return matches[0];
        }
        return null;
      }

      async function refreshClassDetection() {
        if (!window.pywebview || !window.pywebview.api) return;
        try {
          const classes = await window.pywebview.api.detect_classes(
            state.rosterConfigs,
          );
          state.detectedClasses = classes || [];
          renderClassesSection();
        } catch (e) {
          console.error("Failed to detect classes:", e);
        }
      }

      function renderClassesSection() {
        const section = document.getElementById("classesSection");
        const emptyState = document.getElementById("classesEmptyState");
        const container = document.getElementById("classesListContainer");
        const countDisplay = document.getElementById("classesCountDisplay");
        const readyBadge = document.getElementById("classesReadyBadge");

        if (!state.detectedClasses || state.detectedClasses.length === 0) {
          if (section) section.classList.add("d-none");
          if (emptyState) emptyState.classList.remove("d-none");
          if (container) container.innerHTML = "";
          updateStepperStatus();
          updateFileEstimate();
          return;
        }

        if (emptyState) emptyState.classList.add("d-none");
        if (section) section.classList.remove("d-none");
        if (countDisplay) countDisplay.innerText = state.detectedClasses.length;
        if (readyBadge) readyBadge.innerText = `${state.detectedClasses.length} Ready`;

        let rowsHtml = "";
        state.detectedClasses.forEach((cls) => {
          const isLab = cls.detected_type === "lecture_lab";
          const rep = findRosterReportForClass(cls);
          const studentCount =
            rep && typeof rep.student_count === "number"
              ? rep.student_count
              : typeof cls.student_count === "number"
                ? cls.student_count
                : null;

          const autoStrip = document.getElementById("autoStripCheck")
            ? document.getElementById("autoStripCheck").checked
            : true;
          let statusBadgeHtml = `<span class="badge-status badge-valid">Ready</span>`;
          if (rep) {
            if (rep.status === "error") {
              statusBadgeHtml = `<span class="badge-status badge-error" title="${escapeHTML(rep.message || 'Validation issue')}">Needs Review</span>`;
            } else if (rep.issue === "incomplete_filename" || (rep.status === "warning" && !autoStrip)) {
              statusBadgeHtml = `<span class="badge-status badge-warning" title="${escapeHTML(rep.message || 'Check roster columns')}">Warning</span>`;
            }
          }

          let ceitPill = "";
          if (cls.ceit_metadata) {
            ceitPill = `<span class="badge-ceit-pill" style="margin-top: 3px;" title="${escapeHTML(cls.ceit_metadata.department_name)}">${escapeHTML(cls.ceit_metadata.prefix)} · ${escapeHTML(cls.ceit_metadata.department_code)}</span>`;
          }

          const countCellHtml =
            studentCount !== null
              ? `<span class="student-count-value">${studentCount}</span> <span class="student-count-unit">students</span>`
              : `<span class="student-count-unit">Linked</span>`;

          const isInspected = window._currentInspectedClassId === cls.id ? "row-inspected" : "";

          rowsHtml += `
            <tr class="class-card class-table-row row-selected ${isInspected}" id="card_${escapeHTML(cls.id)}" data-class-id="${escapeHTML(cls.id)}">
              <td class="col-select">
                <input
                  type="checkbox"
                  id="sel_${escapeHTML(cls.id)}" class="class-select-check item-class-check"
                  data-class-id="${escapeHTML(cls.id)}"
                  aria-label="Select ${escapeHTML(cls.course_sec)} (${escapeHTML(cls.subject_name)})"
                  checked
                  onchange="updateSelectCount()"
                />
              </td>
              <td class="col-section">
                <div class="class-header-row" style="margin-bottom: 0;">
                  <span class="course-badge">${escapeHTML(cls.course_sec)}</span>
                  <span class="sched-badge">Sched: ${escapeHTML(cls.schedule_code)}</span>
                  ${ceitPill}
                </div>
              </td>
              <td class="col-subject">
                <div class="subject-title" title="${escapeHTML(cls.subject_name)}">${escapeHTML(cls.subject_name)}</div>
              </td>
              <td class="col-schedule">
                <div class="sched-schedule-line" title="${escapeHTML(cls.schedule_desc)}">${escapeHTML(cls.schedule_desc)}</div>
              </td>
              <td class="col-classification">
                <div class="class-type-wrapper">
                  <select id="type_${escapeHTML(cls.id)}" class="type-dropdown class-type-select" data-class-id="${escapeHTML(cls.id)}" aria-label="Classification for ${escapeHTML(cls.course_sec)}">
                    <option value="lecture_lab" ${isLab ? "selected" : ""}>Lecture and Lab</option>
                    <option value="lecture_only" ${!isLab ? "selected" : ""}>Lecture only</option>
                  </select>
                </div>
              </td>
              <td class="col-students">
                ${countCellHtml}
              </td>
              <td class="col-status">
                ${statusBadgeHtml}
              </td>
              <td class="col-actions">
                <button
                  type="button"
                  id="btnInspect_${escapeHTML(cls.id)}" class="btn-inspect-row"
                  onclick="openClassInspector('${escapeHTML(cls.id)}')"
                  aria-label="Inspect ${escapeHTML(cls.course_sec)}"
                >
                  Inspect
                </button>
              </td>
            </tr>
          `;
        });

        container.innerHTML = `
          <div class="table-scroll-container" role="region" aria-label="Detected classes batch matrix" tabindex="0">
            <table id="packagesMatrixTable" class="packages-matrix-table">
              <thead>
                <tr>
                  <th scope="col" class="col-select" title="Select section for batch generation">✓</th>
                  <th scope="col" class="col-section" title="Course and Section">Section</th>
                  <th scope="col" class="col-subject">Subject Title</th>
                  <th scope="col" class="col-schedule">Schedule &amp; Room</th>
                  <th scope="col" class="col-classification">Classification</th>
                  <th scope="col" class="col-students">Enrolled</th>
                  <th scope="col" class="col-status">Status</th>
                  <th scope="col" class="col-actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                ${rowsHtml}
              </tbody>
            </table>
          </div>
          <div class="table-scroll-hint" aria-hidden="true">
            <span>&larr; Scroll horizontally to access the Actions (Inspect) column &rarr;</span>
            <span>Min width: 942px</span>
          </div>
        `;

        applyClassTypeOverrides();
        const selects = document.querySelectorAll(".class-type-select");
        selects.forEach((s) =>
          s.addEventListener("change", () => {
            saveClassTypeOverrides();
            if (window._currentInspectedClassId === s.getAttribute("data-class-id")) {
              const inspSel = document.getElementById("inspClassTypeSelect");
              if (inspSel) inspSel.value = s.value;
            }
          }),
        );
        updateSelectCount();
      }

      // ── On-Demand Privacy-Conscious Section Inspector Controller ──────────
      function openClassInspector(classId) {
        const cls = (state.detectedClasses || []).find((c) => c.id === classId);
        if (!cls) return;
        window._currentInspectedClassId = classId;

        document.querySelectorAll("tr.class-table-row").forEach((tr) => {
          tr.classList.toggle("row-inspected", tr.getAttribute("data-class-id") === classId);
        });

        const rep = findRosterReportForClass(cls);
        const rosterFile =
          (rep && (rep.filename || rep.file)) ||
          (cls.roster_file ? String(cls.roster_file).split(/[\\/]/).pop() : "Auto-matched roster");
        const studentCount =
          rep && typeof rep.student_count === "number"
            ? rep.student_count
            : typeof cls.student_count === "number"
              ? cls.student_count
              : null;

        const setElText = (id, txt) => {
          const el = document.getElementById(id);
          if (el) el.innerText = txt;
        };
        setElText("classInspectorTitle", `Inspect: ${cls.course_sec}`);
        setElText("inspCourseSec", cls.course_sec || "-");
        setElText("inspScheduleCode", cls.schedule_code || "-");
        setElText("inspSubjectName", cls.subject_name || "-");
        setElText("inspScheduleDesc", cls.schedule_desc || "-");
        setElText("inspStudentCount", studentCount !== null ? `${studentCount} Students` : "Verified Roster");
        setElText("inspRosterFilename", rosterFile);

        const statusEl = document.getElementById("inspStatusBadge");
        const autoStrip = document.getElementById("autoStripCheck")
          ? document.getElementById("autoStripCheck").checked
          : true;
        if (statusEl) {
          if (rep && rep.status === "error") {
            statusEl.innerHTML = `<span class="badge-status badge-error">Needs Review</span>`;
          } else if (rep && (rep.issue === "incomplete_filename" || (rep.status === "warning" && !autoStrip))) {
            statusEl.innerHTML = `<span class="badge-status badge-warning">Warning</span>`;
          } else {
            statusEl.innerHTML = `<span class="badge-status badge-valid">Ready</span>`;
          }
        }

        const rowSelect = document.querySelector(`.class-type-select[data-class-id="${CSS.escape ? CSS.escape(classId) : classId}"]`);
        const inspSelect = document.getElementById("inspClassTypeSelect");
        if (inspSelect) {
          inspSelect.value = rowSelect ? rowSelect.value : cls.detected_type || "lecture_lab";
        }

        // Reset student preview disclosure to collapsed by default (privacy-by-default)
        const disclosure = document.getElementById("inspectorStudentDisclosure");
        const previewContainer = document.getElementById("inspectorStudentPreviewContainer");
        if (disclosure) {
          disclosure.open = false;
        }
        if (previewContainer) {
          previewContainer.innerHTML = `
            <div style="padding: 12px; font-size: 12px; color: var(--color-text-secondary);">
              Expand to inspect up to 8 verified student records (Student Number and Name only).
            </div>
          `;
        }

        const trigger = document.activeElement;
        if (typeof closeAllDrawers === "function") closeAllDrawers();
        const drawer = document.getElementById("classInspectorDrawer");
        const backdrop = document.getElementById("drawerBackdrop");
        if (drawer) drawer.classList.add("active");
        if (backdrop) backdrop.classList.add("active");
        if (typeof FocusTrapManager !== "undefined" && drawer) {
          FocusTrapManager.trap(
            drawer,
            document.getElementById("btnCloseClassInspector") || drawer.querySelector("button"),
            trigger,
          );
        }
      }

      function closeClassInspector() {
        window._currentInspectedClassId = null;
        document.querySelectorAll("tr.class-table-row.row-inspected").forEach((tr) => {
          tr.classList.remove("row-inspected");
        });
        if (typeof closeAllDrawers === "function") {
          closeAllDrawers();
        }
      }

      function onInspectorClassTypeChange(newVal) {
        const cid = window._currentInspectedClassId;
        if (!cid) return;
        const rowSelect = document.querySelector(`.class-type-select[data-class-id="${CSS.escape ? CSS.escape(cid) : cid}"]`);
        if (rowSelect) {
          rowSelect.value = newVal;
          saveClassTypeOverrides();
          updateFileEstimate();
        }
      }

      async function replaceInspectedRoster() {
        closeClassInspector();
        if (typeof loadRosters === "function") {
          await loadRosters();
        }
      }

      function remapInspectedRoster() {
        const cid = window._currentInspectedClassId;
        const cls = (state.detectedClasses || []).find((c) => c.id === cid);
        if (!cls) return;
        const rep = findRosterReportForClass(cls);
        const filename =
          (rep && (rep.filename || rep.file)) ||
          (cls.roster_file ? String(cls.roster_file).split(/[\\/]/).pop() : null) ||
          (state.rosters && state.rosters[0] ? String(state.rosters[0]).split(/[\\/]/).pop() : null);
        closeClassInspector();
        if (filename && typeof openColumnMappingModal === "function") {
          openColumnMappingModal(filename);
        }
      }

      function diffInspectedRoster() {
        const cid = window._currentInspectedClassId;
        if (!cid) return;
        closeClassInspector();
        if (typeof triggerRosterDiff === "function") {
          triggerRosterDiff(cid);
        }
      }

      async function onInspectorStudentDisclosureToggle(detailsEl) {
        if (!detailsEl || !detailsEl.open) return;
        const cid = window._currentInspectedClassId;
        const cls = (state.detectedClasses || []).find((c) => c.id === cid);
        const container = document.getElementById("inspectorStudentPreviewContainer");
        if (!cls || !container) return;

        const rep = findRosterReportForClass(cls);
        const targetPathOrName =
          cls.roster_file ||
          (rep && (rep.path || rep.filename || rep.file)) ||
          (state.rosters && state.rosters[0]) ||
          "";
        const baseName = String(targetPathOrName).split(/[\\/]/).pop();
        const config = (state.rosterConfigs && state.rosterConfigs[baseName]) || null;

        container.innerHTML = `<div style="padding: 12px; font-size: 12px; color: var(--color-text-secondary);">Loading sample student records...</div>`;

        try {
          if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.inspect_roster === "function" && targetPathOrName) {
            const res = await window.pywebview.api.inspect_roster(targetPathOrName, config);
            const students = (res && (res.parsed_students || res.parsed_preview || res.preview_students)) || [];
            if (students.length > 0) {
              const slice = students.slice(0, 8);
              let trs = "";
              slice.forEach((s, idx) => {
                const sName = s.name !== undefined ? s.name : Array.isArray(s) ? s[0] : "-";
                const sId =
                  s.student_number !== undefined
                    ? s.student_number
                    : s.id !== undefined
                      ? s.id
                      : Array.isArray(s)
                        ? s[1]
                        : "-";
                trs += `
                  <tr>
                    <td style="width: 32px; color: var(--color-text-muted);">${idx + 1}</td>
                    <td class="col-stud-no">${escapeHTML(String(sId))}</td>
                    <td><strong>${escapeHTML(String(sName))}</strong></td>
                  </tr>
                `;
              });
              container.innerHTML = `
                <table class="inspector-student-table" aria-label="Sample enrolled students (Student Number and Name only)">
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">Student No.</th>
                      <th scope="col">Student Name</th>
                    </tr>
                  </thead>
                  <tbody id="inspectorStudentTbody">${trs}</tbody>
                </table>
                <div style="padding: 8px 12px; font-size: 11px; color: var(--color-text-muted); background: var(--color-surface-2);">
                  Showing ${slice.length} of ${res.student_count || students.length} verified records (Student Number &amp; Name only).
                </div>
              `;
              return;
            }
          }
          container.innerHTML = `<div style="padding: 12px; font-size: 12px; color: var(--color-text-secondary);">Use "Remap Columns" above to inspect raw spreadsheet rows and custom column mappings.</div>`;
        } catch (err) {
          container.innerHTML = `<div style="padding: 12px; font-size: 12px; color: var(--color-danger);">Could not load student preview: ${escapeHTML(String(err))}</div>`;
        }
      }

      window.findRosterReportForClass = findRosterReportForClass;
      window.openClassInspector = openClassInspector;
      window.closeClassInspector = closeClassInspector;
      window.onInspectorClassTypeChange = onInspectorClassTypeChange;
      window.replaceInspectedRoster = replaceInspectedRoster;
      window.remapInspectedRoster = remapInspectedRoster;
      window.diffInspectedRoster = diffInspectedRoster;
      window.onInspectorStudentDisclosureToggle = onInspectorStudentDisclosureToggle;

      // ── Step 2: Interactive Column Mapping Modal ─────────────────────────
      let currentMappingFilename = null;
      let currentInspectionData = null;

      async function openColumnMappingModal(filename) {
        if (!window.pywebview || !window.pywebview.api) return;
        currentMappingFilename = filename;
        const modal = document.getElementById("modalRosterMappingBackdrop");
        if (!modal) return;

        document.getElementById("mapModalFilename").innerText = filename;
        const config =
          (state.rosterConfigs && state.rosterConfigs[filename]) || {};

        try {
          const res = await window.pywebview.api.inspect_roster(
            filename,
            config,
          );
          if (!res || res.status === "error") {
            showToast(
              "Inspection Error",
              res?.message || "Could not read roster file",
              "error",
            );
            return;
          }
          currentInspectionData = res;

          // Badges
          const ceitBadge = document.getElementById("mapModalCeitBadge");
          if (res.ceit_metadata) {
            const dCode =
              res.ceit_metadata.department_code ||
              res.ceit_metadata.dept_code ||
              "";
            ceitBadge.innerText = dCode
              ? `${res.ceit_metadata.prefix} · ${dCode}`
              : res.ceit_metadata.prefix;
            ceitBadge.title =
              res.ceit_metadata.department_name || res.ceit_metadata.dept || "";
            ceitBadge.classList.remove("d-none");
          } else {
            ceitBadge.classList.add("d-none");
          }

          const formatBadge = document.getElementById("mapModalFormatBadge");
          if (formatBadge) {
            const fmt = res.format || (res.is_excel ? "XLSX" : "CSV");
            formatBadge.innerText = fmt.toUpperCase();
          }

          // Pre-populate manual metadata inputs from config or hints
          const hints = res.filename_hints || {};
          const inSec = document.getElementById("mapInputCourseSec");
          const inCode = document.getElementById("mapInputScheduleCode");
          const inSubj = document.getElementById("mapInputSubjectName");
          if (inSec) inSec.value = config.course_sec || hints.course_sec || "";
          if (inCode)
            inCode.value =
              config.schedule_code ||
              config.linked_schedule_code ||
              hints.schedule_code ||
              "";
          if (inSubj)
            inSubj.value = config.subject_name || hints.subject_name || "";

          // Populate Class Link Select
          const selClass = document.getElementById("mapSelectClassLink");
          selClass.innerHTML = `<option value="">-- Manual / Auto-Detect by Filename --</option>`;
          const activeLinkedCode =
            config.linked_schedule_code ||
            config.schedule_code ||
            res.linked_schedule_code ||
            "";
          if (state.detectedClasses && state.detectedClasses.length > 0) {
            state.detectedClasses.forEach((cls) => {
              const isSel =
                activeLinkedCode === cls.schedule_code ? "selected" : "";
              selClass.innerHTML += `<option value="${escapeHTML(cls.schedule_code)}" ${isSel}>${escapeHTML(cls.schedule_code)} - ${escapeHTML(cls.course_sec)} (${escapeHTML(cls.subject_name)})</option>`;
            });
          }

          // Update dynamic recommended filename banner
          updateModalRecommendedFilename(res.recommended_filename);

          // Populate Header Row Select
          const selHeader = document.getElementById("mapSelectHeaderRow");
          selHeader.innerHTML = "";
          const previewRows = res.raw_rows || res.raw_preview || [];
          const detectedHeader =
            res.detected_header_row !== undefined
              ? res.detected_header_row
              : res.auto_header_row !== undefined
                ? res.auto_header_row
                : 0;
          previewRows.forEach((r, idx) => {
            const rowArr = Array.isArray(r)
              ? r
              : r.cells
                ? Object.values(r.cells)
                : Object.values(r);
            const previewText = rowArr.slice(0, 4).filter(Boolean).join(" | ");
            const isSel = idx === detectedHeader ? "selected" : "";
            selHeader.innerHTML += `<option value="${idx}" ${isSel}>Row ${idx + 1}: ${escapeHTML(previewText.slice(0, 45))}${previewText.length > 45 ? "..." : ""}</option>`;
          });

          // Populate Column Selects
          const selName = document.getElementById("mapSelectNameCol");
          const selId = document.getElementById("mapSelectIdCol");
          selName.innerHTML = "";
          selId.innerHTML = "";

          const rawCols = res.available_columns || res.columns || [];
          const availableCols = rawCols.map((c, i) => {
            if (typeof c === "object" && c !== null) return c;
            return { index: i, col_ref: c, name: `Col ${c}` };
          });

          const detectedName =
            res.detected_name_column !== undefined
              ? res.detected_name_column
              : res.auto_name_col !== undefined
                ? typeof res.auto_name_col === "number"
                  ? res.auto_name_col
                  : 0
                : 0;
          const detectedId =
            res.detected_id_column !== undefined
              ? res.detected_id_column
              : res.auto_id_col !== undefined
                ? typeof res.auto_id_col === "number"
                  ? res.auto_id_col
                  : 1
                : 1;

          availableCols.forEach((col) => {
            const isNameSel = col.index === detectedName ? "selected" : "";
            const isIdSel = col.index === detectedId ? "selected" : "";
            selName.innerHTML += `<option value="${col.index}" ${isNameSel}>${escapeHTML(col.name)}</option>`;
            selId.innerHTML += `<option value="${col.index}" ${isIdSel}>${escapeHTML(col.name)}</option>`;
          });

          // Render Raw Grid and Parsed Students
          renderSpreadsheetGrid(
            previewRows,
            availableCols,
            detectedHeader,
            detectedName,
            detectedId,
          );
          const parsedList = res.parsed_students || res.parsed_preview || res.preview_students || [];
          renderParsedPreview(parsedList, res.student_count || 0);

          const previousFocus = document.activeElement;
          modal.classList.remove("d-none");
          if (typeof FocusTrapManager !== "undefined") {
            FocusTrapManager.trap(
              modal,
              document.getElementById("mapSelectHeaderRow") || document.getElementById("btnCloseMappingModal"),
              previousFocus
            );
          }
        } catch (err) {
          console.error("Failed to open column mapping modal:", err);
          showToast(
            "Inspection Error",
            "Failed to inspect roster: " + err,
            "error",
          );
        }
      }

      function closeColumnMappingModal(event) {
        if (
          event &&
          event.target &&
          event.target.id !== "modalRosterMappingBackdrop" &&
          event.target.id !== "btnCloseMappingModal"
        ) {
          return;
        }
        const modal = document.getElementById("modalRosterMappingBackdrop");
        if (modal) {
          modal.classList.add("d-none");
          if (typeof FocusTrapManager !== "undefined") {
            FocusTrapManager.release();
          }
        }
        currentMappingFilename = null;
        currentInspectionData = null;
      }

      function onClassLinkSelectChanged() {
        const code = document.getElementById("mapSelectClassLink")?.value;
        if (code && state.detectedClasses) {
          const matched = state.detectedClasses.find(
            (c) => c.schedule_code === code,
          );
          if (matched) {
            if (matched.course_sec)
              document.getElementById("mapInputCourseSec").value =
                matched.course_sec;
            if (matched.schedule_code)
              document.getElementById("mapInputScheduleCode").value =
                matched.schedule_code;
            if (matched.subject_name)
              document.getElementById("mapInputSubjectName").value =
                matched.subject_name;
          }
        }
        updateModalRecommendedFilename();
        onMappingConfigChanged();
      }

      function onManualMetadataChanged() {
        updateModalRecommendedFilename();
      }

      function updateModalRecommendedFilename(explicitFallback) {
        const inSec = document.getElementById("mapInputCourseSec");
        const inCode = document.getElementById("mapInputScheduleCode");
        const inSubj = document.getElementById("mapInputSubjectName");
        const cSec = (inSec ? inSec.value : "").trim().replace(/\s+/g, "");
        const sCode = (inCode ? inCode.value : "").trim();
        const sName = (inSubj ? inSubj.value : "").trim();
        const recEl = document.getElementById("mapModalRecommendedFilename");
        if (!recEl) return;
        if (cSec && sCode && sName) {
          recEl.innerText = `${cSec} List of Students for ${sCode}-${sName}.xlsx`;
        } else if (explicitFallback) {
          recEl.innerText = explicitFallback;
        } else if (
          currentInspectionData &&
          currentInspectionData.filename_hints &&
          currentInspectionData.filename_hints.recommended_filename
        ) {
          recEl.innerText =
            currentInspectionData.filename_hints.recommended_filename;
        } else {
          recEl.innerText = `${cSec || "CourseSec"} List of Students for ${sCode || "ScheduleCode"}-${sName || "Subject"}.xlsx`;
        }
      }

      async function onMappingConfigChanged() {
        if (
          !currentMappingFilename ||
          !window.pywebview ||
          !window.pywebview.api
        )
          return;
        const headerRowVal =
          document.getElementById("mapSelectHeaderRow").value;
        const nameColVal = document.getElementById("mapSelectNameCol").value;
        const idColVal = document.getElementById("mapSelectIdCol").value;
        const linkedCode = document.getElementById("mapSelectClassLink").value;

        const headerRow = parseInt(headerRowVal, 10);
        const nameCol = parseInt(nameColVal, 10);
        const idCol = parseInt(idColVal, 10);

        const overrides = {
          header_row: isNaN(headerRow) ? null : headerRow,
          name_column: isNaN(nameCol) ? null : nameCol,
          id_column: isNaN(idCol) ? null : idCol,
          linked_schedule_code: linkedCode || null,
        };

        try {
          const res = await window.pywebview.api.inspect_roster(
            currentMappingFilename,
            overrides,
          );
          if (res && res.status !== "error") {
            currentInspectionData = res;
            const previewRows = res.raw_rows || res.raw_preview || [];
            const rawCols = res.available_columns || res.columns || [];
            const availableCols = rawCols.map((c, i) => {
              if (typeof c === "object" && c !== null) return c;
              return { index: i, col_ref: c, name: `Col ${c}` };
            });
            renderSpreadsheetGrid(
              previewRows,
              availableCols,
              overrides.header_row,
              overrides.name_column,
              overrides.id_column,
            );
            const parsedList = res.parsed_students || res.parsed_preview || res.preview_students || [];
            renderParsedPreview(parsedList, res.student_count || 0);
          }
        } catch (err) {
          console.error("Failed to live re-inspect roster:", err);
        }
      }

      function renderSpreadsheetGrid(
        previewRows,
        availableCols,
        activeHeader,
        activeName,
        activeId,
      ) {
        const container = document.getElementById(
          "mapSpreadsheetTableContainer",
        );
        if (!container) return;
        if (!previewRows || previewRows.length === 0) {
          container.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-muted);">No raw rows available to display.</div>`;
          return;
        }

        let maxCols = 0;
        previewRows.forEach((r) => {
          const rowArr = Array.isArray(r)
            ? r
            : r.cells
              ? Object.values(r.cells)
              : Object.values(r);
          if (rowArr.length > maxCols) maxCols = rowArr.length;
        });
        if (availableCols && availableCols.length > maxCols) {
          maxCols = availableCols.length;
        }

        let tableHtml = `<table class="spreadsheet-preview-table" aria-label="Raw Spreadsheet Preview Grid"><thead><tr><th scope="col" style="width: 48px;">#</th>`;
        for (let c = 0; c < maxCols; c++) {
          const colLetter = String.fromCharCode(65 + c);
          let colClass = "";
          let colTag = "";
          if (c === activeName) {
            colClass = "col-name-highlight";
            colTag = " (Name)";
          } else if (c === activeId) {
            colClass = "col-id-highlight";
            colTag = " (ID)";
          }
          tableHtml += `<th scope="col" class="${colClass}">Col ${colLetter}${colTag}</th>`;
        }
        tableHtml += `</tr></thead><tbody>`;

        previewRows.forEach((row, rIdx) => {
          const isHeaderRow = rIdx === activeHeader;
          const rowClass = isHeaderRow ? "row-header-highlight" : "";
          const rowArr = Array.isArray(row)
            ? row
            : row.cells
              ? Object.values(row.cells)
              : Object.values(row);
          tableHtml += `<tr class="${rowClass}"><th scope="row" style="font-weight: 700; color: var(--text-muted); text-align: left; padding: 4px 8px;">${rIdx + 1}${isHeaderRow ? " [H]" : ""}</th>`;
          for (let c = 0; c < maxCols; c++) {
            let colClass = "";
            if (c === activeName) colClass = "col-name-highlight";
            else if (c === activeId) colClass = "col-id-highlight";
            const val =
              rowArr[c] !== undefined && rowArr[c] !== null
                ? String(rowArr[c])
                : "";
            tableHtml += `<td class="${colClass}" title="${escapeHTML(val)}">${escapeHTML(val)}</td>`;
          }
          tableHtml += `</tr>`;
        });

        tableHtml += `</tbody></table>`;
        container.innerHTML = tableHtml;
      }

      function renderParsedPreview(parsedStudents, count) {
        const countDisplay = document.getElementById("mapParsedCount");
        const previewBox = document.getElementById("mapParsedStudentsPreview");
        if (countDisplay) countDisplay.innerText = count || 0;
        if (!previewBox) return;

        if (!parsedStudents || parsedStudents.length === 0) {
          previewBox.innerHTML = `<div style="padding: 12px; color: var(--accent-rose); font-weight: 600;">⚠️ No valid students extracted with current column mapping. Adjust Header row, Name, or ID column.</div>`;
          return;
        }

        let itemsHtml = "";
        parsedStudents.slice(0, 15).forEach((s) => {
          const sName =
            s.name !== undefined ? s.name : Array.isArray(s) ? s[0] : "";
          const sId =
            s.student_number !== undefined
              ? s.student_number
              : s.id !== undefined
                ? s.id
                : Array.isArray(s)
                  ? s[1]
                  : "";
          itemsHtml += `
            <div class="parsed-student-item">
              <span class="parsed-student-name">${escapeHTML(sName)}</span>
              <span class="parsed-student-id">${escapeHTML(sId)}</span>
            </div>
          `;
        });
        if (parsedStudents.length > 15) {
          itemsHtml += `<div style="font-size: 11px; color: var(--text-muted); padding: 4px 8px;">... and ${parsedStudents.length - 15} more students parsed successfully.</div>`;
        }
        previewBox.innerHTML = itemsHtml;
      }

      async function applyRosterMapping() {
        if (
          !currentMappingFilename ||
          !window.pywebview ||
          !window.pywebview.api
        )
          return;
        const headerRowVal =
          document.getElementById("mapSelectHeaderRow").value;
        const nameColVal = document.getElementById("mapSelectNameCol").value;
        const idColVal = document.getElementById("mapSelectIdCol").value;
        const linkedCode =
          document.getElementById("mapSelectClassLink")?.value || "";
        const courseSec = (
          document.getElementById("mapInputCourseSec")?.value || ""
        ).trim();
        const scheduleCode = (
          document.getElementById("mapInputScheduleCode")?.value || ""
        ).trim();
        const subjectName = (
          document.getElementById("mapInputSubjectName")?.value || ""
        ).trim();
        const rememberSimilar = document.getElementById(
          "mapCheckRememberSimilar",
        )?.checked;

        const headerRow = parseInt(headerRowVal, 10);
        const nameCol = parseInt(nameColVal, 10);
        const idCol = parseInt(idColVal, 10);
        const cols = (currentInspectionData && currentInspectionData.columns) || [];
        const isExcel = !!(currentInspectionData && currentInspectionData.is_excel);
        const resolvedNameCol = isNaN(nameCol) ? null : (isExcel && cols[nameCol] ? cols[nameCol] : nameCol);
        const resolvedIdCol = isNaN(idCol) ? null : (isExcel && cols[idCol] ? cols[idCol] : idCol);

        const config = {
          header_row: isNaN(headerRow) ? null : headerRow,
          name_column: isNaN(nameCol) ? null : nameCol,
          id_column: isNaN(idCol) ? null : idCol,
          name_col: resolvedNameCol,
          id_col: resolvedIdCol,
          course_sec: courseSec || null,
          schedule_code: scheduleCode || null,
          subject_name: subjectName || null,
          linked_schedule_code: linkedCode || scheduleCode || null,
        };

        state.rosterConfigs[currentMappingFilename] = config;
        saveRosterConfigs();

        if (rememberSimilar) {
          try {
            localStorage.setItem(
              "cvsu_parsing_rules",
              JSON.stringify({
                header_row: config.header_row,
                name_column: config.name_column,
                id_column: config.id_column,
              }),
            );
          } catch (e) {}
        }

        try {
          const reports = await window.pywebview.api.validate_rosters(
            state.rosterConfigs,
          );
          state.rosterReports = reports || [];
          renderRosterStatus();
          await refreshClassDetection();
          updateStepperStatus();
          updateFileEstimate();
          showToast(
            "Configuration Applied",
            `Saved class details and column mapping for ${currentMappingFilename}`,
            "success",
          );
        } catch (err) {
          console.error(
            "Failed to validate rosters after applying mapping:",
            err,
          );
        }

        closeColumnMappingModal();
      }

      async function resetToAutoMapping() {
        if (
          !currentMappingFilename ||
          !window.pywebview ||
          !window.pywebview.api
        )
          return;
        delete state.rosterConfigs[currentMappingFilename];
        saveRosterConfigs();

        try {
          const res = await window.pywebview.api.inspect_roster(
            currentMappingFilename,
            {},
          );
          if (res && res.status !== "error") {
            currentInspectionData = res;
            if (res.detected_header_row !== undefined) {
              document.getElementById("mapSelectHeaderRow").value =
                res.detected_header_row;
            }
            if (res.detected_name_column !== undefined) {
              document.getElementById("mapSelectNameCol").value =
                res.detected_name_column;
            }
            if (res.detected_id_column !== undefined) {
              document.getElementById("mapSelectIdCol").value =
                res.detected_id_column;
            }
            if (document.getElementById("mapSelectClassLink")) {
              document.getElementById("mapSelectClassLink").value = "";
            }
            const hints = res.filename_hints || {};
            if (document.getElementById("mapInputCourseSec")) {
              document.getElementById("mapInputCourseSec").value =
                hints.course_sec || "";
            }
            if (document.getElementById("mapInputScheduleCode")) {
              document.getElementById("mapInputScheduleCode").value =
                hints.schedule_code || "";
            }
            if (document.getElementById("mapInputSubjectName")) {
              document.getElementById("mapInputSubjectName").value =
                hints.subject_name || "";
            }
            updateModalRecommendedFilename(res.recommended_filename);

            const previewRows = res.raw_rows || [];
            const availableCols = res.available_columns || [];
            renderSpreadsheetGrid(
              previewRows,
              availableCols,
              res.detected_header_row,
              res.detected_name_column,
              res.detected_id_column,
            );
            renderParsedPreview(
              res.parsed_students || [],
              res.student_count || 0,
            );

            const reports = await window.pywebview.api.validate_rosters(
              state.rosterConfigs,
            );
            state.rosterReports = reports || [];
            renderRosterStatus();
            await refreshClassDetection();
            updateStepperStatus();
            updateFileEstimate();
            showToast(
              "Defaults Restored",
              `Reset ${currentMappingFilename} to automatic detection`,
              "info",
            );
          }
        } catch (err) {
          console.error("Failed to reset mapping:", err);
        }
      }

      function toggleSelectAllClasses(checked) {
        document
          .querySelectorAll(".item-class-check")
          .forEach((c) => (c.checked = checked));
        updateSelectCount();
      }

      function updateSelectCount() {
        const allChecks = document.querySelectorAll(".item-class-check");
        const total = allChecks.length;
        const selected = document.querySelectorAll(
          ".item-class-check:checked",
        ).length;

        const masterCheck = document.getElementById("selectAllClasses");
        if (masterCheck) {
          masterCheck.checked = total > 0 && selected === total;
          masterCheck.indeterminate = selected > 0 && selected < total;
        }

        allChecks.forEach((cb) => {
          const tr = cb.closest("tr.class-table-row");
          if (tr) {
            tr.classList.toggle("row-selected", cb.checked);
            tr.classList.toggle("row-unselected", !cb.checked);
          }
        });

        const readyBadge = document.getElementById("classesReadyBadge");
        if (readyBadge) {
          readyBadge.innerText = `${selected} / ${total} Selected`;
        }

        const bulkBtn = document.getElementById("btnApplyBulkType");
        if (bulkBtn) {
          bulkBtn.disabled = selected === 0;
        }

        updateStepperStatus();
        updateFileEstimate();
      }

      function applyBulkClassType() {
        const bulkSelect = document.getElementById("bulkClassTypeSelect");
        if (!bulkSelect) return;
        const targetType = bulkSelect.value;
        let updatedCount = 0;

        document.querySelectorAll(".item-class-check:checked").forEach((cb) => {
          const cid = cb.getAttribute("data-class-id");
          const rowSelect = document.querySelector(
            `.class-type-select[data-class-id="${CSS.escape ? CSS.escape(cid) : cid}"]`
          );
          if (rowSelect) {
            rowSelect.value = targetType;
            updatedCount++;
          }
        });

        if (updatedCount > 0) {
          saveClassTypeOverrides();
          updateFileEstimate();
          const label = targetType === "lecture_lab" ? "Lecture and Lab" : "Lecture only";
          showToast(
            "Batch Classification Applied",
            `Set ${updatedCount} selected section${updatedCount === 1 ? "" : "s"} to "${label}".`,
            "info",
            2200,
          );
        }
      }
      window.applyBulkClassType = applyBulkClassType;

      function filterClassCards(type) {
        document
          .querySelectorAll(".filter-pill")
          .forEach((p) => p.classList.remove("active"));
        if (type === "all")
          document.getElementById("filterAllClasses")?.classList.add("active");
        else if (type === "lab")
          document.getElementById("filterLabClasses")?.classList.add("active");
        else if (type === "lec")
          document.getElementById("filterLecClasses")?.classList.add("active");

        const cards = document.querySelectorAll(
          "#classesListContainer .class-card",
        );
        cards.forEach((card) => {
          const select = card.querySelector(".class-type-select");
          const val = select ? select.value : "";
          const visibleDisplay = card.tagName === "TR" ? "" : "flex";
          if (type === "all") {
            card.style.display = visibleDisplay;
          } else if (type === "lab") {
            card.style.display = val === "lecture_lab" ? visibleDisplay : "none";
          } else if (type === "lec") {
            card.style.display = val === "lecture_only" ? visibleDisplay : "none";
          }
        });
      }

      function updateFileEstimate() {
        const estimateBadge = document.getElementById("fileEstimateBadge");
        if (!estimateBadge) return;

        const selectedClasses = document.querySelectorAll(
          ".item-class-check:checked",
        ).length;
        if (selectedClasses === 0) {
          estimateBadge.classList.add("d-none");
          return;
        }

        const customActiveCount = state.customTemplates
          ? state.customTemplates.filter((t) => t.enabled !== false).length
          : 0;
        const ceitCount = state.engines.ceit ? 7 + customActiveCount : 0;
        const gradesCount = state.engines.grades ? 1 : 0;

        let monthsCount = 5;
        const sVal = document.getElementById("startDate")
          ? document.getElementById("startDate").value
          : "";
        const eVal = document.getElementById("endDate")
          ? document.getElementById("endDate").value
          : "";
        if (sVal && eVal) {
          const d1 = new Date(sVal);
          const d2 = new Date(eVal);
          if (!isNaN(d1) && !isNaN(d2) && d2 >= d1) {
            monthsCount = Math.max(
              1,
              (d2.getFullYear() - d1.getFullYear()) * 12 +
                (d2.getMonth() - d1.getMonth()) +
                1,
            );
          }
        }
        const attCount = state.engines.attendance ? monthsCount : 0;

        const perClass = ceitCount + gradesCount + attCount;
        const totalEstimated = selectedClasses * perClass;

        if (totalEstimated > 0) {
          estimateBadge.classList.remove("d-none");
          estimateBadge.innerText = `Estimated Output: ~${totalEstimated} Files (${selectedClasses} classes \u00d7 ${perClass} docs)`;
        } else {
          estimateBadge.classList.add("d-none");
        }
      }

      function saveClassTypeOverrides() {
        try {
          const overrides = {};
          document.querySelectorAll(".class-type-select").forEach((sel) => {
            const cid = sel.getAttribute("data-class-id");
            if (cid) overrides[cid] = sel.value;
          });
          localStorage.setItem("classTypeOverrides", JSON.stringify(overrides));
        } catch (e) {
          console.warn(
            "Unable to save class type overrides to localStorage:",
            e,
          );
        }
      }

      function applyClassTypeOverrides() {
        const str = localStorage.getItem("classTypeOverrides");
        if (!str) return;
        try {
          const overrides = JSON.parse(str);
          document.querySelectorAll(".class-type-select").forEach((sel) => {
            const cid = sel.getAttribute("data-class-id");
            if (cid && overrides[cid]) sel.value = overrides[cid];
          });
        } catch (e) {}
      }

      // ── Step 2: Date Boundaries & Output ──────────────────────────────────
      function renderActiveMonths() {
        const container = document.getElementById("includedMonthsContainer");
        if (!container) return;

        const sVal = document.getElementById("startDate").value;
        const eVal = document.getElementById("endDate").value;
        const monthNames = [
          "Jan",
          "Feb",
          "Mar",
          "Apr",
          "May",
          "Jun",
          "Jul",
          "Aug",
          "Sep",
          "Oct",
          "Nov",
          "Dec",
        ];

        if (sVal && eVal) {
          const d1 = new Date(sVal);
          const d2 = new Date(eVal);
          if (!isNaN(d1) && !isNaN(d2) && d2 < d1) {
            container.innerHTML = `<span class="month-chip" style="border-color: var(--color-danger); color: var(--color-danger);">⚠️ Invalid Date Range: End Date must be on or after Start Date</span>`;
            updateFileEstimate();
            return;
          }
          if (!isNaN(d1) && !isNaN(d2) && d2 >= d1) {
            let chipsHtml = "";
            let curr = new Date(d1.getFullYear(), d1.getMonth(), 1);
            const end = new Date(d2.getFullYear(), d2.getMonth(), 1);
            let count = 0;
            while (curr <= end && count < 12) {
              chipsHtml += `<span class="month-chip">📅 ${monthNames[curr.getMonth()]} ${curr.getFullYear()}</span>`;
              curr.setMonth(curr.getMonth() + 1);
              count++;
            }
            container.innerHTML =
              chipsHtml ||
              `<span class="month-chip text-secondary">📅 Standard Semester (~5 Months)</span>`;
            updateFileEstimate();
            return;
          }
        }
        container.innerHTML = `<span class="month-chip text-secondary">📅 Standard Semester (~5 Months)</span>`;
        updateFileEstimate();
      }

      function saveDates() {
        localStorage.setItem(
          "cvsu_startDate",
          document.getElementById("startDate").value,
        );
        localStorage.setItem(
          "cvsu_endDate",
          document.getElementById("endDate").value,
        );
        renderActiveMonths();
        updateStepperStatus();
      }

      function loadSavedDates() {
        const s = localStorage.getItem("cvsu_startDate");
        const e = localStorage.getItem("cvsu_endDate");
        if (s) document.getElementById("startDate").value = s;
        if (e) document.getElementById("endDate").value = e;
        renderActiveMonths();
        updateStepperStatus();
      }

      function setSemesterPreset(type) {
        const currentYear = new Date().getFullYear();
        if (type === "1st") {
          document.getElementById("startDate").value = `${currentYear}-08-01`;
          document.getElementById("endDate").value = `${currentYear}-12-18`;
        } else {
          document.getElementById("startDate").value = `${currentYear}-01-15`;
          document.getElementById("endDate").value = `${currentYear}-05-30`;
        }
        saveDates();
      }

      function clearDatePresets() {
        document.getElementById("startDate").value = "";
        document.getElementById("endDate").value = "";
        saveDates();
      }

      async function loadOutput() {
        if (!window.pywebview || !window.pywebview.api) return;
        const res = await window.pywebview.api.browse_output();
        if (res) {
          state.outputDir = res;
          document.getElementById("outputDisplay").value = res;
          localStorage.setItem("cvsu_output_dir", res);
          const statusDisplay = document.getElementById("outputPathStatus");
          if (statusDisplay) {
            statusDisplay.innerHTML = `<span style="color: var(--accent-emerald);">✔ Ready:</span> ${escapeHTML(res)}`;
          }
          updateStepperStatus();
          showToast("Output Folder Set", res, "info");
        }
      }

      async function openOutputFolder() {
        if (!window.pywebview || !window.pywebview.api) return;
        try {
          const res = await window.pywebview.api.open_output_folder(state.outputDir);
          if (res && res.status === "error") {
            showToast("Directory Error", res.message || "Target folder does not exist", "error");
          }
        } catch (e) {
          showToast("Directory Error", String(e), "error");
        }
      }
