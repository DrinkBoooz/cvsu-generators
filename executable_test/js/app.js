// ── Application Bootstrapping & Lifecycle ─────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (typeof initTheme === 'function') initTheme();
  if (typeof setupScrollAwareActionBar === 'function') setupScrollAwareActionBar();
  if (typeof updateStepper === 'function') updateStepper(1);
  if (typeof loadParserSettingsDefaults === 'function') loadParserSettingsDefaults();
});

window.addEventListener('pywebviewready', () => {
  console.log('CvSU Gen Desktop pywebview ready.');
  if (typeof syncInitialStateWithPython === 'function') {
    syncInitialStateWithPython();
  }
});
