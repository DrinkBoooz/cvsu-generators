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
          "Accessibility",
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
        if (tabName === "Accessibility") {
          updateAccessibilitySettingsUI();
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
        updateAccessibilitySettingsUI();
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

      function getActiveSignatories() {
        if (!activeParserConfig) return [];
        if (!activeParserConfig.organization_preset) {
          activeParserConfig.organization_preset = {
            version: "1.0",
            campus: activeParserConfig.schedule_config?.default_campus || "Don Severino de las Alas Campus",
            college: activeParserConfig.schedule_config?.default_college || "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY",
            department: activeParserConfig.schedule_config?.default_department || "Department of Information Technology",
            signatories: [
              { slot_id: "prepared_by", label: "Prepared by:", name: activeParserConfig.schedule_config?.default_instructor || "DAN JOSEPH A. ORTEGA", title: "Instructor" },
              { slot_id: "reviewed_by", label: "Reviewed by:", name: activeParserConfig.department_chair || "ENGR. EMIL C. ALVAREZ", title: "Department Chairperson" },
              { slot_id: "approved_by", label: "Approved by:", name: activeParserConfig.college_dean || "DR. MARLON R. PERA", title: "College Dean" }
            ]
          };
        }
        if (!Array.isArray(activeParserConfig.organization_preset.signatories)) {
          activeParserConfig.organization_preset.signatories = [];
        }
        return activeParserConfig.organization_preset.signatories;
      }

      function renderSignatoryRows() {
        const container = document.getElementById("cfgSignatoriesListContainer");
        if (!container) return;
        const sigs = getActiveSignatories();
        if (sigs.length === 0) {
          container.innerHTML = `
            <div style="font-size: 11.5px; color: var(--text-muted); text-align: center; padding: 12px; border: 1px dashed var(--border-subtle); border-radius: var(--radius-sm);">
              No signatory tiers configured. Click "+ Add Tier" or "Import Preset" above.
            </div>
          `;
          updateFacultyDefaultsPreview();
          return;
        }

        container.innerHTML = sigs.map((sig, idx) => `
          <div style="display: flex; gap: 8px; align-items: center; background: var(--surface-subtle); padding: 6px 10px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); flex-wrap: wrap;">
            <div style="flex: 1; min-width: 140px;">
              <label style="font-size: 10px; color: var(--text-muted); display: block; margin-bottom: 2px;">Role Label</label>
              <input type="text" class="form-control-custom" style="padding: 4px 8px; font-size: 11.5px;" value="${escapeHTML(sig.label || '')}" placeholder="e.g. Prepared by:" oninput="updateSignatoryField(${idx}, 'label', this.value)" />
            </div>
            <div style="flex: 2; min-width: 180px;">
              <label style="font-size: 10px; color: var(--text-muted); display: block; margin-bottom: 2px;">Signatory Full Name</label>
              <input type="text" class="form-control-custom" style="padding: 4px 8px; font-size: 11.5px; font-weight: 600;" value="${escapeHTML(sig.name || '')}" placeholder="e.g. DR. JUAN DELA CRUZ" oninput="updateSignatoryField(${idx}, 'name', this.value)" />
            </div>
            <div style="flex: 1.5; min-width: 150px;">
              <label style="font-size: 10px; color: var(--text-muted); display: block; margin-bottom: 2px;">Designation / Title</label>
              <input type="text" class="form-control-custom" style="padding: 4px 8px; font-size: 11.5px;" value="${escapeHTML(sig.title || '')}" placeholder="e.g. Campus Administrator" oninput="updateSignatoryField(${idx}, 'title', this.value)" />
            </div>
            <button type="button" class="btn-config-delete" style="align-self: flex-end; margin-bottom: 4px; padding: 4px 8px; font-size: 11px;" title="Remove Tier" onclick="removeSignatoryRow(${idx})">✕</button>
          </div>
        `).join("");

        updateFacultyDefaultsPreview();
      }

      function updateSignatoryField(idx, field, val) {
        const sigs = getActiveSignatories();
        if (sigs[idx]) {
          sigs[idx][field] = val;
          updateFacultyDefaultsPreview();
        }
      }

      function addSignatoryRow() {
        const sigs = getActiveSignatories();
        sigs.push({
          slot_id: `signatory_${sigs.length + 1}`,
          label: "Noted by:",
          name: "",
          title: "Designated Official"
        });
        renderSignatoryRows();
      }

      function removeSignatoryRow(idx) {
        const sigs = getActiveSignatories();
        sigs.splice(idx, 1);
        renderSignatoryRows();
      }

      async function exportOrgPresetFromUI() {
        if (!activeParserConfig) return;
        const campus = document.getElementById("cfgDefaultCampus")?.value?.trim() || "";
        const college = document.getElementById("cfgDefaultCollege")?.value?.trim() || "";
        const dept = document.getElementById("cfgDefaultDepartment")?.value?.trim() || "";
        const sigs = getActiveSignatories();

        const presetData = {
          version: "1.0",
          campus: campus,
          college: college,
          department: dept,
          signatories: sigs
        };

        if (window.pywebview?.api?.export_org_preset) {
          try {
            const res = await window.pywebview.api.export_org_preset(null, presetData);
            if (res && res.status === "success") {
              showToast("Preset Exported", `Saved preset to ${res.file_path}`, "success");
            } else if (res && res.status !== "cancelled") {
              showToast("Export Error", res.message || "Failed to export preset", "error");
            }
          } catch (e) {
            showToast("Export Error", String(e), "error");
          }
        }
      }

      async function importOrgPresetFromUI() {
        if (!activeParserConfig) return;
        if (window.pywebview?.api?.import_org_preset) {
          try {
            const res = await window.pywebview.api.import_org_preset(null);
            if (res && res.status === "success" && res.preset) {
              const p = res.preset;
              const campusEl = document.getElementById("cfgDefaultCampus");
              const collegeEl = document.getElementById("cfgDefaultCollege");
              const deptEl = document.getElementById("cfgDefaultDepartment");
              if (campusEl && p.campus !== undefined) campusEl.value = p.campus;
              if (collegeEl && p.college !== undefined) collegeEl.value = p.college;
              if (deptEl && p.department !== undefined) deptEl.value = p.department;

              if (!activeParserConfig.organization_preset) activeParserConfig.organization_preset = {};
              activeParserConfig.organization_preset.campus = p.campus || "";
              activeParserConfig.organization_preset.college = p.college || "";
              activeParserConfig.organization_preset.department = p.department || "";
              activeParserConfig.organization_preset.signatories = p.signatories || [];

              renderSignatoryRows();
              showToast("Preset Imported", `Applied organization preset for ${p.campus || p.department || 'preset'}`, "success");
            } else if (res && res.status !== "cancelled") {
              showToast("Import Error", res.message || "Failed to import preset", "error");
            }
          } catch (e) {
            showToast("Import Error", String(e), "error");
          }
        }
      }

      function updateFacultyDefaultsPreview() {
        const instr = document.getElementById("cfgDefaultInstructor");
        const campus = document.getElementById("cfgDefaultCampus");
        const college = document.getElementById("cfgDefaultCollege");
        const dept = document.getElementById("cfgDefaultDepartment");
        const sem = document.getElementById("cfgDefaultSemester");

        const previewInstr = document.getElementById("previewHeaderInstructor");
        const previewCampus = document.getElementById("previewHeaderCampus");
        const previewCollege = document.getElementById("previewHeaderCollege");
        const previewDept = document.getElementById("previewHeaderDepartment");
        const previewSem = document.getElementById("previewHeaderSemester");
        const previewSigs = document.getElementById("previewHeaderSignatories");

        if (previewInstr) {
          previewInstr.textContent = (instr?.value?.trim()) || "DAN JOSEPH A. ORTEGA";
        }
        if (previewCampus) {
          previewCampus.textContent = (campus?.value?.trim()) || "Don Severino de las Alas Campus";
        }
        if (previewCollege) {
          const collVal = college?.value?.trim();
          previewCollege.textContent = collVal || "COLLEGE OF ENGINEERING AND INFORMATION TECHNOLOGY";
          previewCollege.style.display = collVal === "" ? "none" : "block";
        }
        if (previewDept) {
          previewDept.textContent = (dept?.value?.trim()) || "Department of Information Technology";
        }
        if (previewSem) {
          previewSem.textContent = (sem?.value?.trim()) || "FIRST SEMESTER, AY 2026 - 2027";
        }
        if (previewSigs) {
          const sigs = getActiveSignatories();
          if (sigs.length === 0) {
            previewSigs.innerHTML = `<span style="color: var(--text-muted);">No signatories configured</span>`;
          } else {
            previewSigs.innerHTML = sigs.map((s) => `
              <div style="flex: 1; padding: 0 4px;">
                <div style="color: var(--text-muted); font-size: 9.5px;">${escapeHTML(s.label || '')}</div>
                <div style="font-weight: 700; color: var(--text-primary); text-decoration: underline; margin: 4px 0 2px;">${escapeHTML(s.name || 'SIGNATORY NAME')}</div>
                <div style="font-size: 9.5px; color: var(--text-secondary);">${escapeHTML(s.title || '')}</div>
              </div>
            `).join("");
          }
        }
      }

      function renderConfigScheduleDefaults() {
        if (!activeParserConfig) return;
        const sc = activeParserConfig.schedule_config || {};
        const org = activeParserConfig.organization_preset || {};
        const instr = document.getElementById("cfgDefaultInstructor");
        const campus = document.getElementById("cfgDefaultCampus");
        const college = document.getElementById("cfgDefaultCollege");
        const dept = document.getElementById("cfgDefaultDepartment");
        const sem = document.getElementById("cfgDefaultSemester");

        if (instr) instr.value = sc.default_instructor || "";
        if (campus) campus.value = org.campus || sc.default_campus || "Don Severino de las Alas Campus";
        if (college) college.value = org.college || sc.default_college || "";
        if (dept) dept.value = org.department || sc.default_department || "Department of Information Technology";
        if (sem) sem.value = sc.default_semester || "";

        renderSignatoryRows();
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
        const campus = document.getElementById("cfgDefaultCampus");
        const college = document.getElementById("cfgDefaultCollege");
        const dept = document.getElementById("cfgDefaultDepartment");
        const sem = document.getElementById("cfgDefaultSemester");

        if (!activeParserConfig.schedule_config)
          activeParserConfig.schedule_config = {};
        if (instr)
          activeParserConfig.schedule_config.default_instructor =
            instr.value.trim();
        if (campus)
          activeParserConfig.schedule_config.default_campus =
            campus.value.trim();
        if (college)
          activeParserConfig.schedule_config.default_college =
            college.value.trim();
        if (dept)
          activeParserConfig.schedule_config.default_department =
            dept.value.trim();
        if (sem)
          activeParserConfig.schedule_config.default_semester =
            sem.value.trim();

        if (!activeParserConfig.organization_preset)
          activeParserConfig.organization_preset = {};
        activeParserConfig.organization_preset.campus = campus ? campus.value.trim() : "";
        activeParserConfig.organization_preset.college = college ? college.value.trim() : "";
        activeParserConfig.organization_preset.department = dept ? dept.value.trim() : "";
        activeParserConfig.organization_preset.signatories = getActiveSignatories();

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

      // ── Accessibility Settings Handlers ────────────────────────────────────
      function updateAccessibilitySettingsUI() {
        const motionSelect = document.getElementById("accMotionSelect");
        const transSelect = document.getElementById("accTransparencySelect");

        const currentMotion = (typeof getStoredAccessibilityMotion === "function")
          ? getStoredAccessibilityMotion()
          : (localStorage.getItem("cvsu_acc_motion") || "system");
        const currentTrans = (typeof getStoredAccessibilityTransparency === "function")
          ? getStoredAccessibilityTransparency()
          : (localStorage.getItem("cvsu_acc_transparency") || "system");

        if (motionSelect) motionSelect.value = currentMotion;
        if (transSelect) transSelect.value = currentTrans;

        // Update live diagnostic status indicators
        const sysMotionMatches = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        const effectiveMotion = (typeof getEffectiveMotionPreference === "function")
          ? getEffectiveMotionPreference()
          : (currentMotion === "reduce" ? "reduce" : (currentMotion === "full" ? "no-preference" : (sysMotionMatches ? "reduce" : "no-preference")));
        const effectiveTrans = (typeof getEffectiveTransparencyPreference === "function")
          ? getEffectiveTransparencyPreference()
          : (currentTrans === "reduce" ? "reduce" : "glass");

        const elSysMotion = document.getElementById("accStatusSysMotion");
        const elEffectiveMotion = document.getElementById("accStatusEffectiveMotion");
        const elVTEngine = document.getElementById("accStatusVTEngine");
        const elEffectiveSurface = document.getElementById("accStatusEffectiveSurface");

        if (elSysMotion) {
          elSysMotion.textContent = sysMotionMatches ? "Disabled (prefers-reduced-motion)" : "Active (Full Motion)";
          elSysMotion.style.color = sysMotionMatches ? "var(--accent-amber)" : "var(--accent-emerald)";
        }
        if (elEffectiveMotion) {
          elEffectiveMotion.textContent = effectiveMotion === "reduce" ? "Reduced Motion" : "Full Motion";
          elEffectiveMotion.style.color = effectiveMotion === "reduce" ? "var(--accent-amber)" : "var(--accent-emerald)";
        }
        if (elVTEngine) {
          const hasVT = typeof document.startViewTransition === "function";
          elVTEngine.textContent = hasVT ? "Available (startViewTransition)" : "Not Available (Fallback)";
          elVTEngine.style.color = hasVT ? "var(--accent-emerald)" : "var(--accent-amber)";
        }
        if (elEffectiveSurface) {
          elEffectiveSurface.textContent = effectiveTrans === "reduce" ? "Solid Opaque (Reduced Transparency)" : "Standard (Frosted Glass)";
          elEffectiveSurface.style.color = effectiveTrans === "reduce" ? "var(--accent-blue)" : "var(--accent-emerald)";
        }
      }

      function onAccessibilityMotionChange(val) {
        const cleanVal = typeof sanitizeMotionPreference === "function" ? sanitizeMotionPreference(val) : (val || "system");
        try {
          localStorage.setItem("cvsu_acc_motion", cleanVal);
        } catch (e) {}
        if (typeof applyAccessibilityPreferences === "function") {
          applyAccessibilityPreferences();
        }
        updateAccessibilitySettingsUI();
        if (typeof syncCurrentPreferencesToNative === "function") {
          syncCurrentPreferencesToNative();
        }
        if (typeof showToast === "function") {
          const label = cleanVal === "system" ? "Follow System" : (cleanVal === "reduce" ? "Reduced Motion" : "Full Motion (Override)");
          showToast("Accessibility Updated", `Motion preference set to: ${label}`, "info");
        }
      }

      function onAccessibilityTransparencyChange(val) {
        const cleanVal = typeof sanitizeTransparencyPreference === "function" ? sanitizeTransparencyPreference(val) : (val || "system");
        try {
          localStorage.setItem("cvsu_acc_transparency", cleanVal);
        } catch (e) {}
        if (typeof applyAccessibilityPreferences === "function") {
          applyAccessibilityPreferences();
        }
        updateAccessibilitySettingsUI();
        if (typeof syncCurrentPreferencesToNative === "function") {
          syncCurrentPreferencesToNative();
        }
        if (typeof showToast === "function") {
          const label = cleanVal === "system" ? "Follow System" : (cleanVal === "reduce" ? "Reduced Transparency (Solid)" : "Standard Transparency (Frosted Glass)");
          showToast("Accessibility Updated", `Transparency preference set to: ${label}`, "info");
        }
      }

      function resetAccessibilityPreferences() {
        try {
          localStorage.setItem("cvsu_acc_motion", "system");
          localStorage.setItem("cvsu_acc_transparency", "system");
          localStorage.setItem("cvsu_prefs_migrated", "true");
        } catch (e) {}
        if (typeof applyAccessibilityPreferences === "function") {
          applyAccessibilityPreferences();
        }
        updateAccessibilitySettingsUI();
        if (typeof syncCurrentPreferencesToNative === "function") {
          syncCurrentPreferencesToNative();
        }
      }

      // Expose globally for testing
      window.updateAccessibilitySettingsUI = updateAccessibilitySettingsUI;
      window.onAccessibilityMotionChange = onAccessibilityMotionChange;
      window.onAccessibilityTransparencyChange = onAccessibilityTransparencyChange;
      window.resetAccessibilityPreferences = resetAccessibilityPreferences;
