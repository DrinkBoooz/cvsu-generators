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

function onBridgeReady() {
  console.log('CvSU Gen Desktop pywebview ready.');
  if (typeof syncInitialStateWithPython === 'function') {
    syncInitialStateWithPython();
  }
  if (typeof syncUserPreferencesWithNative === 'function') {
    syncUserPreferencesWithNative();
  }
  if (typeof loadWorkspaceListUI === 'function') {
    loadWorkspaceListUI();
  }
  if (typeof loadTemplateSetsUI === 'function') {
    loadTemplateSetsUI();
  }
  if (typeof loadCustomTemplatesUI === 'function') {
    loadCustomTemplatesUI();
  }
}

if (window.bridgeReadyPromise) {
  window.bridgeReadyPromise.then(onBridgeReady);
} else if (window.pywebview && window.pywebview.api) {
  onBridgeReady();
} else {
  window.addEventListener('pywebviewready', onBridgeReady, { once: true });
}
