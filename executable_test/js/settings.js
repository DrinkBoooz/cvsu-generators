// ── Curriculum & Parser Configuration State & Logic ───────────────────
      let activeParserConfig = null;
      let activeConfigTab = "Prefixes";
      let prefixFilterQuery = "";

      async function openSettingsModal() {
        const modal = document.getElementById("modalParserSettingsBackdrop");
        if (!modal) return;
        const trigger = document.getElementById("btnOpenSettings") || document.activeElement;
        modal.classList.remove("d-none");
        document.body.style.overflow = "hidden";
        switchConfigTab(activeConfigTab || "Prefixes");
        if (typeof FocusTrapManager !== "undefined") {
          FocusTrapManager.trap(
            modal,
            document.getElementById("cfgSearchPrefix") || document.getElementById("cfgTabPrefixes"),
            trigger
          );
        }

        if (
          window.pywebview &&
          window.pywebview.api &&
          window.pywebview.api.get_parser_config
        ) {
          try {
            activeParserConfig = await window.pywebview.api.get_parser_config();
          } catch (err) {
            console.error("Failed to load parser config:", err);
          }
        }
        if (!activeParserConfig) {
          // Fallback defaults if in browser mock or offline preview
          activeParserConfig = {
            ceit_prefix_map: {
              COSC: {
                name: "Computer Science",
                dept: "Department of Information Technology",
                dept_code: "DIT",
                icon: "🖥️",
                badge: "🖥️ Computer Science",
              },
              DCIT: {
                name: "DIT Core / Common IT",
                dept: "Department of Information Technology",
                dept_code: "DIT",
                icon: "💻",
                badge: "💻 DIT Core",
              },
              ITEC: {
                name: "Information Technology",
                dept: "Department of Information Technology",
                dept_code: "DIT",
                icon: "🌐",
                badge: "🌐 Info Tech",
              },
            },
            base_subject_prefixes: [
              "CVSU",
              "DCIT",
              "COSC",
              "ITEC",
              "MATH",
              "GNED",
            ],
            known_lab_subjects: ["DCIT 21", "COSC 70", "ITEC 50"],
            program_aliases: { CS: "BSCS", IT: "BSIT" },
            roster_keywords: {
              name_tokens: ["name", "studentname", "fullname", "pangalan"],
              id_tokens: ["studentnumber", "studentno", "studentid", "lrn"],
            },
            schedule_config: {
              default_instructor: "DAN JOSEPH A. ORTEGA",
              default_semester: "FIRST SEMESTER, AY 2026 - 2027",
              default_college:
                "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY",
            },
          };
        }
        renderConfigUI();
      }

      function closeSettingsModal(event) {
        if (
          event &&
          event.target &&
          event.target.id !== "modalParserSettingsBackdrop" &&
          event.target.id !== "btnCloseSettingsModal"
        ) {
          return;
        }
        const modal = document.getElementById("modalParserSettingsBackdrop");
        if (modal) {
          modal.classList.add("d-none");
          document.body.style.overflow = "";
          if (typeof FocusTrapManager !== "undefined") {
            FocusTrapManager.release();
          }
        }
      }

      function switchConfigTab(tabName) {
        activeConfigTab = tabName;
        const tabs = [
          "Prefixes",
          "Lab",
          "Degrees",
          "Keywords",
          "Schedule",
          "TemplateSets",
          "CustomTemplates",
        ];
        tabs.forEach((t) => {
          const tabBtn = document.getElementById(`cfgTab${t}`);
          const pane = document.getElementById(`cfgPane${t}`);
          if (tabBtn) tabBtn.classList.toggle("active", t === tabName);
          if (pane) pane.classList.toggle("d-none", t !== tabName);
        });
        if (tabName === "TemplateSets" && typeof loadTemplateSetsUI === "function") {
          loadTemplateSetsUI();
        }
        if (tabName === "CustomTemplates") {
          loadCustomTemplatesUI();
        }
        if (tabName === "Schedule") {
          updateFacultyDefaultsPreview();
        }
      }

      function renderConfigUI() {
        if (!activeParserConfig) return;
        renderConfigPrefixes();
        renderConfigLabCodes();
        renderConfigDegreeAliases();
        renderConfigKeywords();
        renderConfigScheduleDefaults();
        loadCustomTemplatesUI();
      }

      function renderConfigPrefixes() {
        const tbody = document.getElementById("cfgPrefixTableBody");
        const countSpan = document.getElementById("cfgPrefixCount");
        if (!tbody || !activeParserConfig) return;

        const map = activeParserConfig.ceit_prefix_map || {};
        const q = (prefixFilterQuery || "").trim().toUpperCase();
        const entries = Object.entries(map).sort((a, b) =>
          a[0].localeCompare(b[0]),
        );

        let filtered = entries;
        if (q) {
          filtered = entries.filter(([p, m]) => {
            return (
              p.includes(q) ||
              (m.dept_code || "").toUpperCase().includes(q) ||
              (m.name || "").toUpperCase().includes(q)
            );
          });
        }

        if (countSpan)
          countSpan.innerText = `${filtered.length} of ${entries.length} Prefixes`;

        if (filtered.length === 0) {
          tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--text-muted);">No subject prefixes matched '${escapeHTML(q)}'</td></tr>`;
          return;
        }

        tbody.innerHTML = filtered
          .map(([p, m]) => {
            const icon = m.icon || "📚";
            const deptCode = m.dept_code || "";
            const deptName = m.name || m.dept || "";
            const badge = m.badge || `${icon} ${deptCode || p}`;
            return `
            <tr>
              <td><strong style="font-family: ui-monospace, monospace; color: var(--accent-emerald);">${escapeHTML(p)}</strong></td>
              <td><span class="badge-subtle-hint">${escapeHTML(deptCode)}</span></td>
              <td>${escapeHTML(deptName)}</td>
              <td><span class="badge-ceit-pill" style="display:inline-flex;">${escapeHTML(badge)}</span></td>
              <td style="text-align: right;">
                <button type="button" class="btn-table-action-delete" onclick="deleteConfigPrefix('${escapeHTML(p)}')" title="Delete Prefix">&times; Remove</button>
              </td>
            </tr>
          `;
          })
          .join("");
      }

      function filterConfigPrefixes(val) {
        prefixFilterQuery = val || "";
        renderConfigPrefixes();
      }

      function addConfigPrefix() {
        if (!activeParserConfig) return;
        const pInput = document.getElementById("cfgNewPrefix");
        const codeInput = document.getElementById("cfgNewDeptCode");
        const nameInput = document.getElementById("cfgNewDeptName");
        const iconInput = document.getElementById("cfgNewIcon");

        const prefix = (pInput.value || "").trim().toUpperCase();
        const deptCode = (codeInput.value || "").trim().toUpperCase();
        const deptName = (nameInput.value || "").trim();
        const icon = (iconInput.value || "📚").trim();

        if (!prefix) {
          showToast(
            "Validation Warning",
            "Subject prefix code cannot be empty.",
            "warning",
          );
          return;
        }

        if (!activeParserConfig.ceit_prefix_map)
          activeParserConfig.ceit_prefix_map = {};
        activeParserConfig.ceit_prefix_map[prefix] = {
          name: deptName || prefix,
          dept: deptName || prefix,
          dept_code: deptCode || prefix,
          icon: icon,
          badge: `${icon} ${deptCode || prefix}`,
        };

        if (!activeParserConfig.base_subject_prefixes)
          activeParserConfig.base_subject_prefixes = [];
        if (!activeParserConfig.base_subject_prefixes.includes(prefix)) {
          activeParserConfig.base_subject_prefixes.push(prefix);
        }

        pInput.value = "";
        codeInput.value = "";
        nameInput.value = "";
        renderConfigPrefixes();
        showToast(
          "Prefix Added",
          `Added '${prefix}' to recognized curriculum prefixes.`,
          "success",
        );
      }

      function deleteConfigPrefix(prefix) {
        if (!activeParserConfig || !activeParserConfig.ceit_prefix_map) return;
        delete activeParserConfig.ceit_prefix_map[prefix];
        if (activeParserConfig.base_subject_prefixes) {
          activeParserConfig.base_subject_prefixes =
            activeParserConfig.base_subject_prefixes.filter(
              (p) => p !== prefix,
            );
        }
        renderConfigPrefixes();
      }

      function renderConfigLabCodes() {
        const cloud = document.getElementById("cfgLabTagCloud");
        const countSpan = document.getElementById("cfgLabCount");
        if (!cloud || !activeParserConfig) return;

        const codes = (activeParserConfig.known_lab_subjects || []).sort();
        if (countSpan) countSpan.innerText = codes.length;

        if (codes.length === 0) {
          cloud.innerHTML = `<span style="color: var(--text-muted); font-size: 12px;">No laboratory subject codes configured.</span>`;
          return;
        }

        cloud.innerHTML = codes
          .map(
            (c) => `
          <span class="config-tag-chip">
            <span>${escapeHTML(c)}</span>
            <button type="button" class="btn-tag-remove" onclick="removeConfigLabCode('${escapeHTML(c)}')" title="Remove">&times;</button>
          </span>
        `,
          )
          .join("");
      }

      function addConfigLabCode() {
        if (!activeParserConfig) return;
        const input = document.getElementById("cfgNewLabCode");
        const raw = (input.value || "").trim().toUpperCase();
        if (!raw) return;

        if (!activeParserConfig.known_lab_subjects)
          activeParserConfig.known_lab_subjects = [];
        if (!activeParserConfig.known_lab_subjects.includes(raw)) {
          activeParserConfig.known_lab_subjects.push(raw);
          renderConfigLabCodes();
          showToast(
            "Lab Code Added",
            `Added '${raw}' to lab-bearing subject codes.`,
            "success",
          );
        }
        input.value = "";
      }

      function removeConfigLabCode(code) {
        if (!activeParserConfig || !activeParserConfig.known_lab_subjects)
          return;
        activeParserConfig.known_lab_subjects =
          activeParserConfig.known_lab_subjects.filter((c) => c !== code);
        renderConfigLabCodes();
      }

      function renderConfigDegreeAliases() {
        const tbody = document.getElementById("cfgDegreesTableBody");
        if (!tbody || !activeParserConfig) return;

        const aliases = activeParserConfig.program_aliases || {};
        const entries = Object.entries(aliases).sort((a, b) =>
          a[0].localeCompare(b[0]),
        );

        if (entries.length === 0) {
          tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; padding: 15px; color: var(--text-muted);">No degree aliases configured.</td></tr>`;
          return;
        }

        tbody.innerHTML = entries
          .map(
            ([short, full]) => `
          <tr>
            <td><code style="color: var(--accent-emerald);">${escapeHTML(short)}</code></td>
            <td><strong>${escapeHTML(full)}</strong></td>
            <td style="text-align: right;">
              <button type="button" class="btn-table-action-delete" onclick="deleteConfigDegreeAlias('${escapeHTML(short)}')">&times; Remove</button>
            </td>
          </tr>
        `,
          )
          .join("");
      }

      function addConfigDegreeAlias() {
        if (!activeParserConfig) return;
        const sInput = document.getElementById("cfgNewAliasShort");
        const fInput = document.getElementById("cfgNewAliasFull");
        const s = (sInput.value || "").trim().toUpperCase();
        const f = (fInput.value || "").trim().toUpperCase();
        if (!s || !f) {
          showToast(
            "Validation Warning",
            "Please provide both short acronym and full degree prefix.",
            "warning",
          );
          return;
        }
        if (!activeParserConfig.program_aliases)
          activeParserConfig.program_aliases = {};
        activeParserConfig.program_aliases[s] = f;
        sInput.value = "";
        fInput.value = "";
        renderConfigDegreeAliases();
        showToast("Alias Added", `Mapped '${s}' to '${f}'.`, "success");
      }

      function deleteConfigDegreeAlias(short) {
        if (!activeParserConfig || !activeParserConfig.program_aliases) return;
        delete activeParserConfig.program_aliases[short];
        renderConfigDegreeAliases();
      }

      function renderConfigKeywords() {
        if (!activeParserConfig) return;
        const rk = activeParserConfig.roster_keywords || {
          name_tokens: [],
          id_tokens: [],
        };

        const nameCloud = document.getElementById("cfgNameTokensCloud");
        if (nameCloud) {
          const names = (rk.name_tokens || []).sort();
          nameCloud.innerHTML = names
            .map(
              (t) => `
            <span class="config-tag-chip">
              <span>${escapeHTML(t)}</span>
              <button type="button" class="btn-tag-remove" onclick="removeConfigKeyword('name', '${escapeHTML(t)}')">&times;</button>
            </span>
          `,
            )
            .join("");
        }

        const idCloud = document.getElementById("cfgIdTokensCloud");
        if (idCloud) {
          const ids = (rk.id_tokens || []).sort();
          idCloud.innerHTML = ids
            .map(
              (t) => `
            <span class="config-tag-chip">
              <span>${escapeHTML(t)}</span>
              <button type="button" class="btn-tag-remove" onclick="removeConfigKeyword('id', '${escapeHTML(t)}')">&times;</button>
            </span>
          `,
            )
            .join("");
        }
      }

      function addConfigKeyword(type) {
        if (!activeParserConfig) return;
        if (!activeParserConfig.roster_keywords)
          activeParserConfig.roster_keywords = {
            name_tokens: [],
            id_tokens: [],
          };
        const inputId = type === "name" ? "cfgNewNameToken" : "cfgNewIdToken";
        const input = document.getElementById(inputId);
        const val = (input.value || "").trim().toLowerCase();
        if (!val) return;

        const key = type === "name" ? "name_tokens" : "id_tokens";
        if (!activeParserConfig.roster_keywords[key])
          activeParserConfig.roster_keywords[key] = [];
        if (!activeParserConfig.roster_keywords[key].includes(val)) {
          activeParserConfig.roster_keywords[key].push(val);
          renderConfigKeywords();
          showToast(
            "Token Added",
            `Added '${val}' to ${type} column detection tokens.`,
            "success",
          );
        }
        input.value = "";
      }

      function removeConfigKeyword(type, token) {
        if (!activeParserConfig || !activeParserConfig.roster_keywords) return;
        const key = type === "name" ? "name_tokens" : "id_tokens";
        if (activeParserConfig.roster_keywords[key]) {
          activeParserConfig.roster_keywords[key] =
            activeParserConfig.roster_keywords[key].filter((t) => t !== token);
          renderConfigKeywords();
        }
      }

      function updateFacultyDefaultsPreview() {
        const instr = document.getElementById("cfgDefaultInstructor");
        const college = document.getElementById("cfgDefaultCollege");
        const sem = document.getElementById("cfgDefaultSemester");

        const previewInstr = document.getElementById("previewHeaderInstructor");
        const previewCollege = document.getElementById("previewHeaderCollege");
        const previewSem = document.getElementById("previewHeaderSemester");

        if (previewInstr) {
          previewInstr.textContent =
            (instr?.value?.trim()) || "DAN JOSEPH A. ORTEGA";
        }
        if (previewCollege) {
          previewCollege.textContent =
            (college?.value?.trim()) ||
            "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY";
        }
        if (previewSem) {
          previewSem.textContent =
            (sem?.value?.trim()) || "FIRST SEMESTER, AY 2026 - 2027";
        }
      }

      function renderConfigScheduleDefaults() {
        if (!activeParserConfig) return;
        const sc = activeParserConfig.schedule_config || {};
        const instr = document.getElementById("cfgDefaultInstructor");
        const college = document.getElementById("cfgDefaultCollege");
        const sem = document.getElementById("cfgDefaultSemester");
        if (instr) instr.value = sc.default_instructor || "";
        if (college) college.value = sc.default_college || "";
        if (sem) sem.value = sc.default_semester || "";
        updateFacultyDefaultsPreview();
      }

      async function saveConfigSettings() {
        if (!activeParserConfig) return;
        const btn = document.getElementById("btnSaveSettings");
        if (btn) {
          btn.disabled = true;
          btn.innerText = "Applying...";
        }

        // Collect schedule defaults inputs
        const instr = document.getElementById("cfgDefaultInstructor");
        const college = document.getElementById("cfgDefaultCollege");
        const sem = document.getElementById("cfgDefaultSemester");
        if (!activeParserConfig.schedule_config)
          activeParserConfig.schedule_config = {};
        if (instr)
          activeParserConfig.schedule_config.default_instructor =
            instr.value.trim();
        if (college)
          activeParserConfig.schedule_config.default_college =
            college.value.trim();
        if (sem)
          activeParserConfig.schedule_config.default_semester =
            sem.value.trim();

        if (
          window.pywebview &&
          window.pywebview.api &&
          window.pywebview.api.save_parser_config
        ) {
          try {
            const res =
              await window.pywebview.api.save_parser_config(activeParserConfig);
            if (res && res.status === "success") {
              if (res.validation) state.rosterReports = res.validation;
              if (res.detected_classes)
                state.detectedClasses = res.detected_classes;
              renderRosterStatus();
              renderClassesSection();
              updateStepperStatus();
              showToast(
                "Settings Saved",
                "Custom curriculum and parser settings applied successfully.",
                "success",
              );
              closeSettingsModal();
            } else {
              showToast(
                "Save Error",
                (res && res.message) || "Failed to save configuration.",
                "error",
              );
            }
          } catch (err) {
            console.error("Error saving parser configuration:", err);
            showToast("Save Error", String(err), "error");
          } finally {
            if (btn) {
              btn.disabled = false;
              btn.innerText = "Save & Apply Changes";
            }
          }
        } else {
          // In browser / test mode
          showToast(
            "Settings Saved (Mock)",
            "Settings applied to browser state.",
            "success",
          );
          if (btn) {
            btn.disabled = false;
            btn.innerText = "Save & Apply Changes";
          }
          closeSettingsModal();
        }
      }

      async function resetConfigSettings() {
        const confirmed = await showAppleConfirm({
          title: "Revert Parser Settings",
          message: "Are you sure you want to revert all curriculum prefixes, lab codes, and keywords to factory defaults?",
          confirmText: "Revert Defaults",
          cancelText: "Cancel",
          isDestructive: true,
        });
        if (!confirmed) return;
        if (
          window.pywebview &&
          window.pywebview.api &&
          window.pywebview.api.reset_parser_config
        ) {
          try {
            const res = await window.pywebview.api.reset_parser_config();
            if (res && res.status === "success") {
              activeParserConfig = res.config;
              if (res.validation) state.rosterReports = res.validation;
              if (res.detected_classes)
                state.detectedClasses = res.detected_classes;
              renderConfigUI();
              renderRosterStatus();
              renderClassesSection();
              updateStepperStatus();
              showToast(
                "Reset Complete",
                "Reverted parser configuration to university presets.",
                "success",
              );
            }
          } catch (err) {
            console.error("Error resetting parser config:", err);
            showToast("Reset Error", String(err), "error");
          }
        }
      }

      async function exportConfigSettings() {
        if (
          window.pywebview &&
          window.pywebview.api &&
          window.pywebview.api.export_parser_config
        ) {
          try {
            const res = await window.pywebview.api.export_parser_config();
            if (res && res.status === "success") {
              showToast(
                "Export Successful",
                `Saved settings to ${res.path}`,
                "success",
              );
            }
          } catch (err) {
            console.error("Failed to export config:", err);
          }
        }
      }

      async function importConfigSettings() {
        if (
          window.pywebview &&
          window.pywebview.api &&
          window.pywebview.api.import_parser_config
        ) {
          try {
            const res = await window.pywebview.api.import_parser_config();
            if (res && res.status === "success") {
              activeParserConfig = res.config;
              if (res.validation) state.rosterReports = res.validation;
              if (res.detected_classes)
                state.detectedClasses = res.detected_classes;
              renderConfigUI();
              renderRosterStatus();
              renderClassesSection();
              updateStepperStatus();
              showToast(
                "Import Successful",
                "Custom configuration imported and applied.",
                "success",
              );
            }
          } catch (err) {
            console.error("Failed to import config:", err);
          }
        }
      }
