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

      // ── Step 2: Class Detection & Table ───────────────────────────────────
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
        const container = document.getElementById("classesListContainer");
        const countDisplay = document.getElementById("classesCountDisplay");
        const readyBadge = document.getElementById("classesReadyBadge");

        if (!state.detectedClasses || state.detectedClasses.length === 0) {
          section.classList.add("d-none");
          container.innerHTML = "";
          updateStepperStatus();
          updateFileEstimate();
          return;
        }

        section.classList.remove("d-none");
        countDisplay.innerText = state.detectedClasses.length;
        readyBadge.innerText = `${state.detectedClasses.length} Ready`;
        container.innerHTML = "";

        state.detectedClasses.forEach((cls) => {
          const isLab = cls.detected_type === "lecture_lab";
          const card = document.createElement("div");
          card.className = "class-card";
          card.id = `card_${cls.id}`;

          let ceitPill = "";
          if (cls.ceit_metadata) {
            ceitPill = `<span class="badge-ceit-pill" title="${escapeHTML(cls.ceit_metadata.department_name)}">${escapeHTML(cls.ceit_metadata.prefix)} · ${escapeHTML(cls.ceit_metadata.department_code)}</span>`;
          }

          card.innerHTML = `
            <input type="checkbox" class="class-select-check item-class-check" data-class-id="${escapeHTML(cls.id)}" checked onchange="updateSelectCount()">
            <div class="class-details">
              <div class="class-header-row">
                <span class="course-badge">${escapeHTML(cls.course_sec)}</span>
                <span class="sched-badge">Sched: ${escapeHTML(cls.schedule_code)}</span>
                ${ceitPill}
              </div>
              <div class="subject-title">${escapeHTML(cls.subject_name)}</div>
              <div class="sched-schedule-line">${escapeHTML(cls.schedule_desc)}</div>
            </div>
            <div>
              <select class="type-dropdown class-type-select" data-class-id="${escapeHTML(cls.id)}">
                <option value="lecture_lab" ${isLab ? "selected" : ""}>Lecture and Lab</option>
                <option value="lecture_only" ${!isLab ? "selected" : ""}>Lecture only</option>
              </select>
            </div>
          `;
          container.appendChild(card);
        });

        applyClassTypeOverrides();
        const selects = document.querySelectorAll(".class-type-select");
        selects.forEach((s) =>
          s.addEventListener("change", saveClassTypeOverrides),
        );
        updateStepperStatus();
        updateFileEstimate();
      }

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
          const parsedList = res.parsed_students || res.parsed_preview || [];
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
            const parsedList = res.parsed_students || res.parsed_preview || [];
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

        const config = {
          header_row: isNaN(headerRow) ? null : headerRow,
          name_column: isNaN(nameCol) ? null : nameCol,
          id_column: isNaN(idCol) ? null : idCol,
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
        const total = document.querySelectorAll(".item-class-check").length;
        const selected = document.querySelectorAll(
          ".item-class-check:checked",
        ).length;
        document.getElementById("classesReadyBadge").innerText =
          `${selected} / ${total} Selected`;
        updateStepperStatus();
        updateFileEstimate();
      }

      function filterClassCards(type) {
        document
          .querySelectorAll(".filter-pill")
          .forEach((p) => p.classList.remove("active"));
        if (type === "all")
          document.getElementById("filterAllClasses").classList.add("active");
        else if (type === "lab")
          document.getElementById("filterLabClasses").classList.add("active");
        else if (type === "lec")
          document.getElementById("filterLecClasses").classList.add("active");

        const cards = document.querySelectorAll(
          "#classesListContainer .class-card",
        );
        cards.forEach((card) => {
          const select = card.querySelector(".class-type-select");
          const val = select ? select.value : "";
          if (type === "all") {
            card.style.display = "flex";
          } else if (type === "lab") {
            card.style.display = val === "lecture_lab" ? "flex" : "none";
          } else if (type === "lec") {
            card.style.display = val === "lecture_only" ? "flex" : "none";
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
