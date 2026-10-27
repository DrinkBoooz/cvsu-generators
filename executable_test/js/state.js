let state = {
        schedulePath: "",
        scheduleMeta: null,
        rosters: [],
        rosterReports: [],
        detectedClasses: [],
        rosterConfigs: (() => {
          try {
            return JSON.parse(
              localStorage.getItem("cvsu_roster_mappings") || "{}",
            );
          } catch (e) {
            return {};
          }
        })(),
        outputDir: localStorage.getItem("cvsu_output_dir") || "",
        engines: {
          attendance: true,
          ceit: true,
          grades: true,
        },
      };

      function saveRosterConfigs() {
        try {
          localStorage.setItem(
            "cvsu_roster_mappings",
            JSON.stringify(state.rosterConfigs || {}),
          );
        } catch (e) {
          console.error("Failed to save roster configs to localStorage:", e);
        }
      }

      window.elapsedTimerInterval = null;
      let generationStartTime = null;

function escapeHTML(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function resetDownstreamFromStep1() {
  state.rosters = [];
  state.rosterReports = [];
  state.detectedClasses = [];
  if (typeof renderRosterStatus === "function") renderRosterStatus();
  if (typeof refreshClassDetection === "function") refreshClassDetection();
  if (typeof updateStepperStatus === "function") updateStepperStatus();
  if (typeof updateFileEstimate === "function") updateFileEstimate();
  window.dispatchEvent(new CustomEvent("state:reset-downstream"));
}

window.state = state;
window.saveRosterConfigs = saveRosterConfigs;
window.escapeHTML = escapeHTML;
window.resetDownstreamFromStep1 = resetDownstreamFromStep1;

