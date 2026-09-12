// ── Stepper Readiness Tracker ─────────────────────────────────────────
      const STEP_CARD_IDS = [
        "cardStep1",
        "cardStep2",
        "cardStep3",
        "cardStep4",
        "cardStep5",
        "cardStep6",
      ];
      const STEP_CHIP_IDS = [
        "chipStep1",
        "chipStep2",
        "chipStep3",
        "chipStep4",
        "chipStep5",
        "chipStep6",
      ];

      function setActiveStepChip(stepIndex) {
        STEP_CHIP_IDS.forEach((cid, cIdx) => {
          const chip = document.getElementById(cid);
          if (chip) chip.classList.toggle("active-step", cIdx === stepIndex);
        });
      }

      function scrollToStep(cardId) {
        const el = document.getElementById(cardId);
        if (!el) return;

        const idx = STEP_CARD_IDS.indexOf(cardId);
        if (idx !== -1) {
          setActiveStepChip(idx);
          window._scrollSpyLockedUntil = Date.now() + 650;
        }

        // Spotlight highlight on target card
        document.querySelectorAll(".glass-card.card-spotlight").forEach((c) => {
          c.classList.remove("card-spotlight");
        });
        el.classList.add("card-spotlight");
        setTimeout(() => el.classList.remove("card-spotlight"), 1400);

        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      // ── Scroll-Aware Floating Bottom Action Bar ───────────────────────────
      function initScrollAwareDock() {
        const dock = document.getElementById("bottomActionBar");
        const step6 = document.getElementById("cardStep6");
        if (!dock || !step6) return;

        const observer = new IntersectionObserver(
          (entries) => {
            if (window._isGenerationRunning) {
              dock.classList.add("dock-hidden");
              return;
            }
            if (entries[0].isIntersecting) {
              dock.classList.add("dock-hidden");
            } else {
              dock.classList.remove("dock-hidden");
            }
          },
          { threshold: 0.05 } // Hide as soon as 5% of Step 6 is visible
        );
        
        observer.observe(step6);
      }

      function triggerWorkflowFromDock() {
        const step6 = document.getElementById("cardStep6");
        const dock = document.getElementById("bottomActionBar");
        if (dock) {
          dock.classList.add("dock-hidden");
        }
        if (step6) {
          step6.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        startGeneration();
      }

      function setGenerationRunningState(
        isRunning,
        labelText = "Initialize Workflow",
      ) {
        window._isGenerationRunning = !!isRunning;
        const btn = document.getElementById("processBtn");
        const btnLabel = document.getElementById("processBtnLabel");
        const dock = document.getElementById("bottomActionBar");
        const dockBtn = document.getElementById("btnDockProcess");
        const dockLabel = document.getElementById("btnDockProcessLabel");

        if (btn) btn.disabled = isRunning;
        if (btnLabel)
          btnLabel.innerText = isRunning
            ? labelText || "Compiling Documents..."
            : "Initialize Workflow";
        if (dockBtn) {
          dockBtn.disabled = isRunning;
          dockBtn.classList.toggle("ready-pulse", !isRunning);
        }
        if (dockLabel)
          dockLabel.innerText = isRunning
            ? labelText || "Compiling Documents..."
            : "Initialize Workflow";

        if (dock && isRunning) {
          dock.classList.add("dock-hidden");
        }
      }

      function updateStepperStatus() {
        const s1Ready = !!state.schedulePath;
        const s2Ready = state.rosters && state.rosters.length > 0;
        const selectedClasses = document.querySelectorAll(
          ".item-class-check:checked",
        ).length;
        const hasEngines =
          document.getElementById("checkAttendance")?.checked ||
          document.getElementById("checkCeit")?.checked ||
          document.getElementById("checkGrades")?.checked;
        const s3Ready = !!hasEngines;
        const s4Ready = true;
        const s5Ready = !!state.outputDir;
        const s6Ready =
          s1Ready &&
          s2Ready &&
          s3Ready &&
          s5Ready &&
          (state.detectedClasses.length === 0 || selectedClasses > 0);

        const setChip = (chipId, statusId, isReady, okIcon = "✓") => {
          const chip = document.getElementById(chipId);
          const st = document.getElementById(statusId);
          if (chip) chip.classList.toggle("ready", isReady);
          if (st) {
             st.innerHTML = isReady ? okIcon : '<span style="opacity: 0.3; font-size: 14px;">•</span>';
          }
        };

        setChip("chipStep1", "statusStep1", s1Ready);
        setChip("chipStep2", "statusStep2", s2Ready);
        setChip("chipStep3", "statusStep3", s3Ready);
        setChip(
          "chipStep4",
          "statusStep4",
          !!(
            document.getElementById("startDate").value ||
            document.getElementById("endDate").value
          ),
          "📅",
        );
        setChip("chipStep5", "statusStep5", s5Ready);
        setChip("chipStep6", "statusStep6", s6Ready, "🚀");

        // Stepper Navigation Lines (Dynamic Connectors)
        const setConnector = (connId, isReady) => {
          const conn = document.getElementById(connId);
          if (conn) conn.classList.toggle("ready", isReady);
        };
        setConnector("connector1to2", s1Ready);
        setConnector("connector2to3", s1Ready && s2Ready);
        setConnector("connector3to4", s1Ready && s2Ready && s3Ready);
        setConnector("connector4to5", s1Ready && s2Ready && s3Ready);
        setConnector("connector5to6", s6Ready);

        // Synchronize Floating Bottom Action Deck
        const pillSched = document.getElementById("actionPillSchedule");
        const pillRost = document.getElementById("actionPillRosters");
        const pillOut = document.getElementById("actionPillOutput");
        const barHint = document.getElementById("actionBarHint");
        const dockBtn = document.getElementById("btnDockProcess");

        if (pillSched) {
          pillSched.classList.toggle("ready", s1Ready);
          const schedLabel = s1Ready
            ? state.scheduleMeta?.instructor
              ? state.scheduleMeta.instructor.split(" ")[0]
              : "Schedule Ready"
            : "Schedule";
          pillSched.innerHTML = `<span class="pill-dot"></span> ${schedLabel}`;
        }
        if (pillRost) {
          const rCount = state.rosters ? state.rosters.length : 0;
          pillRost.classList.toggle("ready", s2Ready);
          pillRost.innerHTML = `<span class="pill-dot"></span> ${rCount} Roster${rCount === 1 ? "" : "s"}`;
        }
        if (pillOut) {
          pillOut.classList.toggle("ready", s5Ready);
          pillOut.innerHTML = `<span class="pill-dot"></span> ${s5Ready ? "Output Ready" : "Output Folder"}`;
        }
        if (barHint) {
          if (s6Ready) {
            const totalStuds = state.rosterReports
              ? state.rosterReports.reduce(
                  (acc, r) => acc + (r.student_count || 0),
                  0,
                )
              : 0;
            barHint.innerText = `Ready to compile: 1 Schedule · ${state.rosters.length} Rosters (${totalStuds} Students)`;
          } else if (!s1Ready) {
            barHint.innerText =
              "Select or drop master schedule (.xls / .xlsx) to begin";
          } else if (!s2Ready) {
            barHint.innerText = "Add class student rosters (.xlsx / .csv)";
          } else if (!s5Ready) {
            barHint.innerText = "Select a target output folder";
          } else {
            barHint.innerText = "Configure document packages or verify classes";
          }
        }
        if (dockBtn) {
          dockBtn.classList.toggle("ready-pulse", s6Ready);
        }
      }

      function initStepperScrollSpy() {
        let isTicking = false;

        const computeActiveStep = () => {
          if (
            window._scrollSpyLockedUntil &&
            Date.now() < window._scrollSpyLockedUntil
          ) {
            return;
          }

          const scrollY = window.scrollY || window.pageYOffset || 0;
          const windowHeight = window.innerHeight || 800;
          const docHeight =
            document.documentElement.scrollHeight || document.body.scrollHeight;

          // If at the very top of the page, Step 1 is the primary step
          if (scrollY < 60) {
            setActiveStepChip(0);
            return;
          }

          // If near the very bottom of the page, Step 6 (Execution Deck) is active
          if (scrollY + windowHeight >= docHeight - 80) {
            setActiveStepChip(5);
            return;
          }

          // 2-Column Dashboard Focal Line: 120px from top (immediately below 95px sticky header)
          const focalY = 120;
          let bestIdx = -1;
          let minDistance = Infinity;

          for (let i = 0; i < STEP_CARD_IDS.length; i++) {
            const card = document.getElementById(STEP_CARD_IDS[i]);
            if (!card) continue;
            const rect = card.getBoundingClientRect();

            // Completely off-screen
            if (rect.bottom <= 90 || rect.top >= windowHeight - 40) continue;

            let dist = Infinity;
            if (rect.top >= 80) {
              // Card top is below header: measure distance from reading focal line
              dist = Math.abs(rect.top - focalY);
            } else if (rect.bottom > focalY) {
              // Card spans across the focal line: prioritize active reading card
              dist = (focalY - rect.top) * 1.3;
            }

            if (dist < minDistance) {
              minDistance = dist;
              bestIdx = i;
            }
          }

          if (bestIdx !== -1) {
            setActiveStepChip(bestIdx);
          }
        };

        window.addEventListener(
          "scroll",
          () => {
            if (!isTicking) {
              window.requestAnimationFrame(() => {
                computeActiveStep();
                isTicking = false;
              });
              isTicking = true;
            }
          },
          { passive: true },
        );

        // Track delegated clicks on cards to immediately activate the clicked step
        document.addEventListener("click", (e) => {
          const card = e.target.closest(".glass-card");
          if (card && card.id && card.id.startsWith("cardStep")) {
            const idx = STEP_CARD_IDS.indexOf(card.id);
            if (idx !== -1) {
              setActiveStepChip(idx);
            }
          }
        });

        // Initial computation
        computeActiveStep();
      }
