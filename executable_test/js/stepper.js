// ==========================================================================



// CvSU Gen — Contextual 6-Stage Navigation & Readiness Controller (stepper.js)



// Genuine single-active-stage workspace switching with full state preservation,



// accessible focus handoff, keyboard navigation, and pre-flight diagnostics.



// ==========================================================================







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







const STEP_HEADING_IDS = [



  "stageHeading1",



  "stageHeading2",



  "stageHeading3",



  "stageHeading4",



  "stageHeading5",



  "stageHeading6",



];







const STEP_NAMES = [



  "Schedule",



  "Rosters",



  "Packages",



  "Dates",



  "Output",



  "Generate",



];







window._activeStageIndex = 0;



window._scrollSpyLockedUntil = 0;











// ── Contextual Workflow Dock Action & Telemetry Engine ────────────────────



function handleDockAction() {



  const idx = window._activeStageIndex || 0;



  switch (idx) {



    case 0:



      if (state.schedulePath) {



        activateStage(2);



      } else if (typeof loadSchedule === "function") {



        loadSchedule();



      }



      break;



    case 1:



      if (state.rosters && state.rosters.length > 0) {



        activateStage(3);



      } else if (typeof loadRosters === "function") {



        loadRosters();



      }



      break;



    case 2:



      activateStage(4);



      break;



    case 3:



      activateStage(5);



      break;



    case 4:



      if (state.outputDir) {



        activateStage(6);



      } else if (typeof loadOutput === "function") {



        loadOutput();



      }



      break;



    default:



      break;



  }



}







function updateDockContext(stageIdx) {
  const idx = stageIdx !== undefined ? stageIdx : (window._activeStageIndex || 0);
  const title = document.getElementById("dockStageTitle");
  const statusMsg = document.getElementById("dockStatusMessage");

  const stageTitles = [
    "Master Schedule",
    "Student Rosters",
    "Packages Matrix",
    "Semester Dates",
    "Output Destination",
    "Review & Preflight"
  ];
  if (title) title.innerText = stageTitles[idx] || "Workbench";

  const readiness = typeof getGenerationReadiness === "function" ? getGenerationReadiness() : {};
  const s1Ready = !!readiness.schedule;
  const s2Ready = !!readiness.rosters;
  const s5Ready = !!readiness.output;
  const rCount = state.rosters ? state.rosters.length : 0;
  const totalClasses = Array.isArray(state.detectedClasses) ? state.detectedClasses.length : 0;
  const selectedClasses = document.querySelectorAll(".item-class-check:checked").length;

  let statusText = "";

  switch (idx) {
    case 0:
      if (s1Ready) {
        const fname = state.schedulePath.split(/[\/]/).pop();
        const inst = state.scheduleMeta?.instructor ? ` (${state.scheduleMeta.instructor})` : "";
        statusText = `Loaded: ${fname}${inst}`;
      } else {
        statusText = "Awaiting master schedule (.xlsx)";
      }
      break;
    case 1:
      if (s2Ready) {
        statusText = `${rCount} student roster file${rCount === 1 ? "" : "s"} loaded`;
      } else {
        statusText = "No student rosters loaded yet";
      }
      break;
    case 2:
      if (totalClasses > 0) {
        statusText = `${selectedClasses} of ${totalClasses} sections selected`;
      } else {
        statusText = s1Ready ? "No class sections found" : "Schedule required to view sections";
      }
      break;
    case 3:
      const sVal = document.getElementById("startDate")?.value;
      const eVal = document.getElementById("endDate")?.value;
      if (sVal && eVal) {
        statusText = readiness.dates !== false ? `Active Range: ${sVal} to ${eVal}` : "Invalid date range (End is before Start)";
      } else {
        statusText = "Standard semester (dates optional)";
      }
      break;
    case 4:
      if (s5Ready) {
        const outName = state.outputDir.split(/[\/]/).pop() || state.outputDir;
        statusText = `Target: ${outName}`;
      } else {
        statusText = "Select output folder destination";
      }
      break;
    case 5:
      statusText = "Preflight Review";
      break;
  }

  if (statusMsg) statusMsg.innerText = statusText;
}







function setActiveStepChip(stepIndex) {



  const validIdx = Math.max(0, Math.min(STEP_CHIP_IDS.length - 1, Number(stepIndex) || 0));



  window._activeStageIndex = validIdx;







  STEP_CHIP_IDS.forEach((cid, cIdx) => {



    const chip = document.getElementById(cid);



    if (!chip) return;



    const isActive = cIdx === validIdx;



    chip.classList.toggle("active-step", isActive);



    if (isActive) {



      chip.setAttribute("aria-current", "step");



    } else {



      chip.removeAttribute("aria-current");



    }



  });







  STEP_CARD_IDS.forEach((cardId, cIdx) => {



    const card = document.getElementById(cardId);



    if (!card) return;



    card.classList.toggle("active-stage", cIdx === validIdx);



  });







  // Synchronize bottom status bar visibility: hide on Stage 6 (index 5) or while running



  const dock = document.getElementById("bottomActionBar");



  if (dock) {



    if (window._isGenerationRunning || validIdx === 5) {



      dock.classList.add("dock-hidden");



    } else {



      dock.classList.remove("dock-hidden");



    }



  }



  updateDockContext(validIdx);



}







function activateStage(stepNumber, options = {}) {



  const idx = Math.max(0, Math.min(STEP_CARD_IDS.length - 1, Number(stepNumber) - 1));



  setActiveStepChip(idx);







  if (!options.preserveScroll) {



    window.scrollTo({ top: 0, behavior: "auto" });



  }







  if (!options.skipFocus) {



    const headingId = STEP_HEADING_IDS[idx];



    const headingEl = headingId ? document.getElementById(headingId) : null;



    if (headingEl && typeof headingEl.focus === "function") {



      try {



        headingEl.focus({ preventScroll: true });



      } catch (e) {



        headingEl.focus();



      }



    }



  }







  if (typeof window.announceA11y === "function" && !options.silent) {



    window.announceA11y(`Stage ${idx + 1} of 6: ${STEP_NAMES[idx]}`);



  }



}







function scrollToStep(cardId) {



  const idx = STEP_CARD_IDS.indexOf(cardId);



  if (idx !== -1) {



    activateStage(idx + 1);



    return;



  }



  const el = document.getElementById(cardId);



  if (el) {



    el.scrollIntoView({ behavior: "smooth", block: "start" });



  }



}







// ── State-Dependent Stage Primary Actions ─────────────────────────────────



function handleStage1PrimaryAction() {



  if (state.schedulePath) {



    activateStage(2);



  } else if (typeof loadSchedule === "function") {



    loadSchedule();



  }



}







function handleStage2PrimaryAction() {



  if (state.rosters && state.rosters.length > 0) {



    activateStage(3);



  } else if (typeof loadRosters === "function") {



    loadRosters();



  }



}







function handleStage5PrimaryAction() {



  if (state.outputDir) {



    activateStage(6);



  } else if (typeof loadOutput === "function") {



    loadOutput();



  }



}







// ── Stage-Aware Bottom Status Bar ─────────────────────────────────────────



function initScrollAwareDock() {



  const dock = document.getElementById("bottomActionBar");



  if (!dock) return;



  if (window._isGenerationRunning || window._activeStageIndex === 5) {



    dock.classList.add("dock-hidden");



  } else {



    dock.classList.remove("dock-hidden");



  }



}







function triggerWorkflowFromDock() {



  const readiness = getGenerationReadiness();



  if (!readiness.schedule) {



    activateStage(1);



    startGeneration();



    return;



  }



  if (!readiness.rosters) {



    activateStage(2);



    startGeneration();



    return;



  }



  if (!readiness.classes || !readiness.engines) {



    activateStage(3);



    startGeneration();



    return;



  }



  if (!readiness.output) {



    activateStage(5);



    startGeneration();



    return;



  }



  activateStage(6);



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



  if (btn) {



    btn.disabled = isRunning;



    btn.setAttribute("aria-disabled", isRunning ? "true" : "false");



  }



  if (btnLabel) {



    btnLabel.innerText = isRunning



      ? labelText || "Compiling Documents..."



      : "Initialize Workflow";



  }







  if (dock) {



    if (isRunning || window._activeStageIndex === 5) {



      dock.classList.add("dock-hidden");



    } else {



      dock.classList.remove("dock-hidden");



    }



  }



}







function isDateRangeValid() {



  const sVal = document.getElementById("startDate")?.value || "";



  const eVal = document.getElementById("endDate")?.value || "";



  if (sVal && eVal) {



    const d1 = new Date(sVal);



    const d2 = new Date(eVal);



    if (!isNaN(d1) && !isNaN(d2) && d2 < d1) {



      return false;



    }



  }



  return true;



}



window.isDateRangeValid = isDateRangeValid;







function getGenerationReadiness() {



  const selectedClasses = document.querySelectorAll(



    ".item-class-check:checked",



  ).length;



  const detectedClasses = Array.isArray(state.detectedClasses)



    ? state.detectedClasses.length



    : 0;



  const enginesReady = !!(



    document.getElementById("checkAttendance")?.checked ||



    document.getElementById("checkCeit")?.checked ||



    document.getElementById("checkGrades")?.checked



  );



  const datesValid = isDateRangeValid();



  const readiness = {



    schedule: !!state.schedulePath,



    rosters: !!(state.rosters && state.rosters.length > 0),



    classes: detectedClasses > 0 && selectedClasses > 0,



    engines: enginesReady,



    dates: datesValid,



    output: !!state.outputDir,



  };



  readiness.ready = Object.values(readiness).every(Boolean);



  return readiness;



}







function updateStepperStatus() {



  const readiness = getGenerationReadiness();



  const s1Ready = readiness.schedule;



  const s2Ready = readiness.rosters;



  const s3Ready = readiness.engines && (state.detectedClasses?.length > 0 ? readiness.classes : true);



  const s5Ready = readiness.output;



  const s6Ready = readiness.ready;







  const stepNames = {



    chipStep1: "Schedule",



    chipStep2: "Rosters",



    chipStep3: "Packages",



    chipStep4: "Dates",



    chipStep5: "Output",



    chipStep6: "Generate",



  };



  const stepNumbers = {



    chipStep1: 1,



    chipStep2: 2,



    chipStep3: 3,



    chipStep4: 4,



    chipStep5: 5,



    chipStep6: 6,



  };



  const setChip = (chipId, statusId, isReady, okIcon = "✓") => {



    const chip = document.getElementById(chipId);



    const st = document.getElementById(statusId);



    if (chip) {



      chip.classList.toggle("ready", isReady);



      const num = stepNumbers[chipId] || 1;



      const name = stepNames[chipId] || "";



      const statusText = isReady ? "Ready" : "Incomplete";



      chip.setAttribute("aria-label", `Step ${num}: ${name} - ${statusText}`);



    }



    if (st) {



      st.innerHTML = isReady ? okIcon : '<span style="opacity: 0.45; font-size: 13px;">•</span>';



      st.setAttribute("aria-hidden", "true");



    }



  };







  const s4Ready = !!(



    document.getElementById("startDate")?.value &&



    document.getElementById("endDate")?.value &&



    readiness.dates !== false



  );



  setChip("chipStep1", "statusStep1", s1Ready);



  setChip("chipStep2", "statusStep2", s2Ready);



  setChip("chipStep3", "statusStep3", s3Ready);



  setChip("chipStep4", "statusStep4", s4Ready, "✓");



  setChip("chipStep5", "statusStep5", s5Ready);



  setChip("chipStep6", "statusStep6", s6Ready, "✓");







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







  // Update Stage Footer Buttons & Status Labels (State-Dependent Useful Actions)



  const btnStage1 = document.getElementById("btnStage1Primary");



  const statusStage1 = document.getElementById("stage1FooterStatus");



  if (btnStage1) {



    btnStage1.innerText = s1Ready ? "Continue to Rosters →" : "Browse File";



  }



  if (statusStage1) {



    statusStage1.innerText = s1Ready



      ? `Loaded: ${state.schedulePath.split(/[\\/]/).pop()}`



      : "Select your official faculty master schedule (.xls or .xlsx) to begin.";



  }







  const btnStage2 = document.getElementById("btnStage2Primary");



  const statusStage2 = document.getElementById("stage2FooterStatus");



  const rCount = state.rosters ? state.rosters.length : 0;



  if (btnStage2) {



    btnStage2.innerText = s2Ready ? "Continue to Packages →" : "Browse Data";



  }



  if (statusStage2) {



    statusStage2.innerText = s2Ready



      ? `${rCount} student roster file${rCount === 1 ? "" : "s"} ready.`



      : "No roster files loaded yet.";



  }







  const btnStage5 = document.getElementById("btnStage5Primary");



  const statusStage5 = document.getElementById("stage5FooterStatus");



  if (btnStage5) {



    btnStage5.innerText = s5Ready ? "Review & Preflight →" : "Browse Path";



  }



  if (statusStage5) {



    statusStage5.innerText = s5Ready



      ? `Target output directory set.`



      : "Choose a local destination folder for generated files.";



  }







  // Update Stage 6 Pre-Flight Summary & Blocker Box



  const totalClasses = Array.isArray(state.detectedClasses) ? state.detectedClasses.length : 0;



  const selectedClasses = document.querySelectorAll(".item-class-check:checked").length;



  const activeEngines = ["attendance", "ceit", "grades"].filter((k) => state.engines[k]);







  const pfSched = document.getElementById("preflightStatSchedule");



  const pfSec = document.getElementById("preflightStatSections");



  const pfPkg = document.getElementById("preflightStatPackages");



  const pfOut = document.getElementById("preflightStatOutput");







  if (pfSched) {



    pfSched.innerText = s1Ready



      ? state.scheduleMeta?.instructor || state.schedulePath.split(/[\\/]/).pop()



      : "Not Loaded";



  }



  if (pfSec) {



    if (!s1Ready || totalClasses === 0) {



      pfSec.innerText = "No Classes Available";



    } else {



      pfSec.innerText = `${selectedClasses} of ${totalClasses} Selected`;



    }



  }



  if (pfPkg) {



    pfPkg.innerText = activeEngines.length > 0 ? `${activeEngines.length} Active` : "None Selected";



  }



  if (pfOut) {



    pfOut.innerText = s5Ready ? state.outputDir : "Not Selected";



  }







  const blockerBox = document.getElementById("preflightBlockerBox");



  const blockerList = document.getElementById("preflightBlockerList");



  if (blockerBox && blockerList) {



    const blockers = [];



    if (!s1Ready) {



      blockers.push(`<li>Master Schedule is not loaded — <button type="button" class="btn-subtle-reset" onclick="activateStage(1)">Go to Stage 1: Schedule</button></li>`);



    }



    if (!s2Ready) {



      blockers.push(`<li>Student Rosters are not loaded — <button type="button" class="btn-subtle-reset" onclick="activateStage(2)">Go to Stage 2: Rosters</button></li>`);



    }



    if (s1Ready && s2Ready && selectedClasses === 0) {



      blockers.push(`<li>Zero class sections are selected — <button type="button" class="btn-subtle-reset" onclick="activateStage(3)">Go to Stage 3: Packages</button></li>`);



    }



    if (!readiness.engines) {



      blockers.push(`<li>No document packages are enabled — <button type="button" class="btn-subtle-reset" onclick="activateStage(3)">Go to Stage 3: Packages</button></li>`);



    }



    if (readiness.dates === false) {



      blockers.push(`<li>Semester End Date is earlier than Start Date — <button type="button" class="btn-subtle-reset" onclick="activateStage(4)">Go to Stage 4: Dates</button></li>`);



    }



    if (!s5Ready) {



      blockers.push(`<li>Target Output Folder is not selected — <button type="button" class="btn-subtle-reset" onclick="activateStage(5)">Go to Stage 5: Output</button></li>`);



    }







    if (blockers.length > 0) {



      blockerList.innerHTML = blockers.join("");



      blockerBox.classList.remove("d-none");



    } else {



      blockerList.innerHTML = "";



      blockerBox.classList.add("d-none");



    }



  }







  // Genuinely disable/enable Stage 6 Generate CTA based on strict pre-flight readiness



  const processBtn = document.getElementById("processBtn");



  if (processBtn && !window._isGenerationRunning) {



    if (!s6Ready) {



      processBtn.disabled = true;



      processBtn.setAttribute("aria-disabled", "true");



      processBtn.setAttribute("aria-describedby", "preflightBlockerBox");



      processBtn.title = "Generation blocked: please resolve pre-flight requirements above.";



    } else {



      processBtn.disabled = false;



      processBtn.removeAttribute("aria-disabled");



      processBtn.removeAttribute("aria-describedby");



      processBtn.title = "Initialize document generation workflow";



    }



  }







  // Synchronize Compact Bottom Status Bar Readiness Indicators (Status-Only)



  const pillSched = document.getElementById("actionPillSchedule");



  const pillRost = document.getElementById("actionPillRosters");



  const pillOut = document.getElementById("actionPillOutput");



  const pillClasses = document.getElementById("actionPillClasses");



  if (pillSched) {



    pillSched.classList.toggle("ready", s1Ready);



    const schedLabel = s1Ready



      ? state.scheduleMeta?.instructor



        ? state.scheduleMeta.instructor.split(" ")[0]



        : "Schedule Ready"



      : "Schedule Incomplete";



    pillSched.innerHTML = `<span class="pill-dot"></span> ${schedLabel}`;



    pillSched.setAttribute("title", s1Ready ? `Master Schedule: ${state.schedulePath}` : "Master Schedule not loaded");



  }



  if (pillRost) {



    pillRost.classList.toggle("ready", s2Ready);



    pillRost.innerHTML = `<span class="pill-dot"></span> ${rCount} Roster${rCount === 1 ? "" : "s"}`;



    pillRost.setAttribute("title", s2Ready ? `${rCount} student rosters loaded` : "No rosters loaded");



  }



  if (pillOut) {



    pillOut.classList.toggle("ready", s5Ready);



    pillOut.innerHTML = `<span class="pill-dot"></span> ${s5Ready ? "Output Ready" : "Output Folder"}`;



    pillOut.setAttribute("title", s5Ready ? `Output: ${state.outputDir}` : "Target output folder not set");



  }



  if (pillClasses) {



    const totalStuds = state.rosterReports



      ? state.rosterReports.reduce((acc, r) => acc + (r.student_count || 0), 0)



      : 0;



    const hasSelection = selectedClasses > 0;



    pillClasses.classList.toggle("ready", hasSelection);



    pillClasses.innerHTML = `<span class="pill-dot"></span> ${selectedClasses} Selected (${totalStuds} Stud.)`;



    pillClasses.setAttribute("title", `${selectedClasses} of ${totalClasses} sections selected (${totalStuds} students total)`);



  }



  updateDockContext(window._activeStageIndex);



}







function initStepperScrollSpy() {



  // Initialize Stage 1 as active stage without stealing initial focus



  activateStage(1, { skipFocus: true, preserveScroll: true, silent: true });







  // Attach keyboard navigation (ArrowRight, ArrowLeft, Home, End) to stepper chips



  const stepperNav = document.getElementById("workflowStepper");



  if (stepperNav && !stepperNav._kbBound) {



    stepperNav._kbBound = true;



    stepperNav.addEventListener("keydown", (e) => {



      const targetChip = e.target.closest(".step-chip");



      if (!targetChip) return;



      const currentIdx = STEP_CHIP_IDS.indexOf(targetChip.id);



      if (currentIdx === -1) return;







      let nextIdx = -1;



      if (e.key === "ArrowRight") {



        nextIdx = (currentIdx + 1) % STEP_CHIP_IDS.length;



      } else if (e.key === "ArrowLeft") {



        nextIdx = (currentIdx - 1 + STEP_CHIP_IDS.length) % STEP_CHIP_IDS.length;



      } else if (e.key === "Home") {



        nextIdx = 0;



      } else if (e.key === "End") {



        nextIdx = STEP_CHIP_IDS.length - 1;



      }







      if (nextIdx !== -1) {



        e.preventDefault();



        const nextChip = document.getElementById(STEP_CHIP_IDS[nextIdx]);



        if (nextChip) {



          nextChip.focus();



          activateStage(nextIdx + 1, { skipFocus: true });



        }



      }



    });



  }



}







window.scrollToStep = scrollToStep;



window.setActiveStepChip = setActiveStepChip;



window.activateStage = activateStage;



window.handleStage1PrimaryAction = handleStage1PrimaryAction;



window.handleStage2PrimaryAction = handleStage2PrimaryAction;



window.handleStage5PrimaryAction = handleStage5PrimaryAction;



window.initScrollAwareDock = initScrollAwareDock;



window.triggerWorkflowFromDock = triggerWorkflowFromDock;



window.setGenerationRunningState = setGenerationRunningState;



window.getGenerationReadiness = getGenerationReadiness;



window.updateStepperStatus = updateStepperStatus;



window.initStepperScrollSpy = initStepperScrollSpy;







window.updateDockContext = updateDockContext;



window.handleDockAction = handleDockAction;



