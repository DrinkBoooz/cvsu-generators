// ── Application Bootstrapping & Lifecycle ─────────────────────────────
function bootstrapApp() {
  if (typeof initTheme === 'function') initTheme();
  if (typeof initScrollAwareDock === 'function') initScrollAwareDock();
  if (typeof updateStepperStatus === 'function') updateStepperStatus();
  if (typeof loadParserSettingsDefaults === 'function') loadParserSettingsDefaults();
  if (typeof loadCustomTemplatesUI === 'function') loadCustomTemplatesUI();

  // Observable telemetry sentinels for lifecycle verification
  window.__app_initialized__ = true;
  window.__app_bootstrap_runs = (window.__app_bootstrap_runs || 0) + 1;
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrapApp);
} else {
  bootstrapApp();
}

window.addEventListener('pywebviewready', () => {
  console.log('CvSU Gen Desktop pywebview ready.');
  if (typeof syncInitialStateWithPython === 'function') {
    syncInitialStateWithPython();
  }
});

