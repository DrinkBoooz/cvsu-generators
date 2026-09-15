// ── Application Bootstrapping & Lifecycle ─────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (typeof initTheme === 'function') initTheme();
  if (typeof initScrollAwareDock === 'function') initScrollAwareDock();
  if (typeof updateStepperStatus === 'function') updateStepperStatus();
  if (typeof loadParserSettingsDefaults === 'function') loadParserSettingsDefaults();
  if (typeof loadCustomTemplatesUI === 'function') loadCustomTemplatesUI();
});

window.addEventListener('pywebviewready', () => {
  console.log('CvSU Gen Desktop pywebview ready.');
  if (typeof syncInitialStateWithPython === 'function') {
    syncInitialStateWithPython();
  }
});
