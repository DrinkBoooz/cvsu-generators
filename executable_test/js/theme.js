// ── Theme Management ──────────────────────────────────────────────────
      const SUN_ICON_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>`;

      const MOON_ICON_SVG = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>`;

      function updateThemeButtonState(theme) {
        const btn = document.getElementById("btnToggleTheme");
        const iconSpan = document.getElementById("themeIcon");
        const labelSpan = document.getElementById("themeLabel");
        if (!btn || !iconSpan || !labelSpan) return;

        if (theme === "dark") {
          iconSpan.innerHTML = SUN_ICON_SVG;
          labelSpan.textContent = "Light";
          btn.title = "Switch to Light Mode";
          btn.setAttribute("aria-label", "Switch to Light Mode");
        } else {
          iconSpan.innerHTML = MOON_ICON_SVG;
          labelSpan.textContent = "Dark";
          btn.title = "Switch to Dark Mode";
          btn.setAttribute("aria-label", "Switch to Dark Mode");
        }
      }

      // ── WAAPI iris duration token ──────────────────────────────────────────
      // This constant is the sole authoritative duration for the WAAPI circular
      // iris clip-path animation on ::view-transition-new(root).
      // It does NOT govern the icon animation (280ms @keyframes, modals.css).
      const THEME_TRANSITION_DURATION_MS = 450;

      // ── Accessibility Preferences State & Resolution ───────────────────────
      const CVSU_ACC_MOTION_KEY = "cvsu_acc_motion";
      const CVSU_ACC_TRANSPARENCY_KEY = "cvsu_acc_transparency";

      function getStoredAccessibilityMotion() {
        try {
          return localStorage.getItem(CVSU_ACC_MOTION_KEY) || "system";
        } catch (e) {
          return "system";
        }
      }

      function getEffectiveMotionPreference() {
        const userPref = getStoredAccessibilityMotion();
        if (userPref === "reduce") return "reduce";
        if (userPref === "full") return "no-preference";
        // "system" default: strictly respect OS media query
        const systemReduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        return systemReduce ? "reduce" : "no-preference";
      }

      function getStoredAccessibilityTransparency() {
        try {
          return localStorage.getItem(CVSU_ACC_TRANSPARENCY_KEY) || "system";
        } catch (e) {
          return "system";
        }
      }

      function getEffectiveTransparencyPreference() {
        const userPref = getStoredAccessibilityTransparency();
        if (userPref === "reduce") return "reduce";
        if (userPref === "glass") return "glass";
        // "system" default: check prefers-reduced-transparency
        try {
          const sysReduced = window.matchMedia("(prefers-reduced-transparency: reduce)").matches;
          return sysReduced ? "reduce" : "glass";
        } catch (e) {
          return "glass";
        }
      }

      function applyAccessibilityPreferences() {
        const doc = document.documentElement;
        const effectiveMotion = getEffectiveMotionPreference();
        const effectiveTrans = getEffectiveTransparencyPreference();

        doc.setAttribute("data-acc-motion", effectiveMotion);
        doc.setAttribute("data-acc-transparency", effectiveTrans);
      }

      // Initialize synchronously on script load
      try {
        applyAccessibilityPreferences();
      } catch (e) {}

      // Dynamically react if OS accessibility preferences change at runtime
      try {
        const sysMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
        if (sysMotionQuery && typeof sysMotionQuery.addEventListener === "function") {
          sysMotionQuery.addEventListener("change", () => {
            applyAccessibilityPreferences();
            if (typeof updateAccessibilitySettingsUI === "function") {
              updateAccessibilitySettingsUI();
            }
          });
        }
        const sysTransQuery = window.matchMedia("(prefers-reduced-transparency: reduce)");
        if (sysTransQuery && typeof sysTransQuery.addEventListener === "function") {
          sysTransQuery.addEventListener("change", () => {
            applyAccessibilityPreferences();
            if (typeof updateAccessibilitySettingsUI === "function") {
              updateAccessibilitySettingsUI();
            }
          });
        }
      } catch (e) {}

      async function toggleTheme(event) {
        const doc = document.documentElement;
        const currentTheme = doc.getAttribute("data-theme") || "dark";
        const newTheme = currentTheme === "dark" ? "light" : "dark";

        const btn = document.getElementById("btnToggleTheme");
        const iconSpan = document.getElementById("themeIcon");

        // ── PART 6/7: Evaluate effective motion preference FIRST ───────────────
        // Precedence: explicit app setting (reduce/full) > system preference (system).
        // Evaluated in JS before starting any View Transition or WAAPI animation.
        const reduceMotion = getEffectiveMotionPreference() === "reduce";

        // Suppress all DOM CSS transitions FIRST — before any class changes
        // that would trigger transitions (e.g. spin-morph → transform transition).
        // This is the critical ordering: suppress, then mutate.
        doc.classList.add("theme-transitioning");

        // Theme icon spin-morph: only when motion is acceptable.
        if (!reduceMotion && iconSpan) {
          iconSpan.classList.add("spin-morph");
          setTimeout(() => iconSpan.classList.remove("spin-morph"), 400);
        }

        // Apply theme update (data-theme attribute, button state, localStorage).
        const applyTheme = () => {
          doc.setAttribute("data-theme", newTheme);
          updateThemeButtonState(newTheme);
          try {
            localStorage.setItem("cvsu_gen_theme", newTheme);
          } catch (e) {}
          if (typeof syncCurrentPreferencesToNative === "function") {
            syncCurrentPreferencesToNative();
          }
        };

        if (!document.startViewTransition || reduceMotion) {
          if (reduceMotion) {
            console.warn(
              `[CvSU Gen][ThemeTransition] Effective motion preference is reduce (stored: ${getStoredAccessibilityMotion()}); skipping animation per accessibility preference`
            );
          }
          // Fallback 1: No VT API support.
          // Fallback 2: Reduced motion — apply theme directly, no animation.
          // (theme-transitioning already added above; remove after paint)
          applyTheme();
          requestAnimationFrame(() => {
            doc.classList.remove("theme-transitioning");
          });
          return;
        }

        // ── Normal flow: View Transition with WAAPI iris ──────────────────────
        //
        // Architecture (commit 196):
        //   WAAPI = sole owner of the circular iris clip-path animation
        //   CSS   = static specular/glass-like styling on VT pseudo-elements
        //   DOM   = no wavefront overlay (was incorrectly snapshotted into old-page)
        //
        // Critical: WAAPI must NOT start before transition.ready resolves.
        // The ::view-transition-new(root) pseudo-element does not exist until
        // the browser's VT pre-paint phase completes. Animating before .ready
        // produces a silent no-op or animates a non-existent target.

        // Compute click-origin geometry for the iris reveal.
        let x = window.innerWidth - 80;
        let y = 30;
        if (event && typeof event.clientX === "number" && event.clientX > 0) {
          x = event.clientX;
          y = event.clientY;
        } else if (btn) {
          const rect = btn.getBoundingClientRect();
          x = rect.left + rect.width / 2;
          y = rect.top + rect.height / 2;
        }

        // Compute the maximum radius needed to cover the full viewport from x,y.
        const endRadius = Math.hypot(
          Math.max(x, window.innerWidth - x),
          Math.max(y, window.innerHeight - y),
        );

        // Inject CSS custom properties so the static VT pseudo-element styling
        // (--vt-edge-specular) can reference the geometry if needed.
        doc.style.setProperty("--vt-x", `${x}px`);
        doc.style.setProperty("--vt-y", `${y}px`);
        doc.style.setProperty("--vt-radius", `${endRadius}px`);
        doc.style.setProperty("--vt-duration", `${THEME_TRANSITION_DURATION_MS}ms`);

        try {
          // Start the View Transition. The callback runs synchronously to swap
          // the theme before the new snapshot is taken.
          const transition = document.startViewTransition(() => {
            applyTheme();
          });

          // ── transition.ready: pseudo-elements now exist ───────────────────
          // Must await this before animating. The ::view-transition-new(root)
          // pseudo-element is only available after the browser's VT pre-paint
          // phase, which .ready signals. Starting before ready = no-op animation.
          await transition.ready;

          // ── WAAPI iris animation on ::view-transition-new(root) ───────────
          // This is the SOLE owner of the iris clip-path geometry.
          // CSS does NOT have a competing animation on this property.
          document.documentElement.animate(
            {
              clipPath: [
                `circle(0px at ${x}px ${y}px)`,
                `circle(${endRadius}px at ${x}px ${y}px)`,
              ],
            },
            {
              duration: THEME_TRANSITION_DURATION_MS,
              easing: "cubic-bezier(0.2, 0, 0, 1)",
              fill: "both",
              pseudoElement: "::view-transition-new(root)",
            }
          );

          // Wait for the transition to fully complete before cleanup.
          await transition.finished;
        } catch (err) {
          console.error(
            "[CvSU Gen][ThemeTransition]",
            err?.name,
            err?.message,
            err?.stack
          );
          // If VT or WAAPI fails for any reason, ensure theme is still applied.
          applyTheme();
        } finally {
          // Double-rAF: the VT compositor tears down asynchronously after
          // transition.finished resolves. A single rAF can fire before the
          // compositor has fully detached the VT layer, causing re-cascade.
          // Two nested rAFs guarantee the next fully-painted frame has cleared
          // the VT layer before CSS transitions are re-enabled.
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              doc.classList.remove("theme-transitioning");
            });
          });
        }
      }

      // ── Diagnostic probe for controlled execution inside native host ────────
      window.__runControlledThemeTransition = async function() {
        const result = {
          hasStartViewTransition: typeof document.startViewTransition === "function",
          hasElementAnimate: typeof Element.prototype.animate === "function",
          hasCSSSupports: typeof CSS !== "undefined" && typeof CSS.supports === "function",
          prefersReducedMotion: window.matchMedia("(prefers-reduced-motion: reduce)").matches,
          storedMotionPreference: getStoredAccessibilityMotion(),
          effectiveMotionPreference: getEffectiveMotionPreference(),
          storedTransparencyPreference: getStoredAccessibilityTransparency(),
          effectiveTransparencyPreference: getEffectiveTransparencyPreference(),
          userAgent: navigator.userAgent,
          brands: navigator.userAgentData?.brands || null,
          platform: navigator.platform,
          platformData: navigator.userAgentData?.platform || null,
          supportsVTName: typeof CSS !== "undefined" && CSS.supports("view-transition-name: root"),
          supportsClipPath: typeof CSS !== "undefined" && CSS.supports("clip-path: circle(10px at 10px 10px)"),
          transitionCreated: false,
          updateCallbackDone: { resolved: false, rejected: false, errorName: null, errorMessage: null },
          ready: { resolved: false, rejected: false, errorName: null, errorMessage: null },
          waapi: { created: false, errorName: null, errorMessage: null, playState: null, currentTime: null, timing: null },
          pseudoComputedStyle: null,
          finished: { resolved: false, rejected: false, errorName: null, errorMessage: null }
        };

        if (!result.hasStartViewTransition) return result;

        try {
          const transition = document.startViewTransition(() => {});
          result.transitionCreated = !!transition;

          try {
            await transition.updateCallbackDone;
            result.updateCallbackDone.resolved = true;
          } catch (e) {
            result.updateCallbackDone.rejected = true;
            result.updateCallbackDone.errorName = e?.name || "Error";
            result.updateCallbackDone.errorMessage = e?.message || String(e);
          }

          try {
            await transition.ready;
            result.ready.resolved = true;

            // Inspect pseudo-element styling during ready
            try {
              const ps = getComputedStyle(document.documentElement, "::view-transition-new(root)");
              result.pseudoComputedStyle = {
                display: ps.display,
                opacity: ps.opacity,
                clipPath: ps.clipPath,
                filter: ps.filter
              };
            } catch (psErr) {
              result.pseudoComputedStyle = { error: String(psErr) };
            }

            // Test WAAPI animate on ::view-transition-new(root)
            try {
              const anim = document.documentElement.animate(
                {
                  clipPath: ["circle(0px at 500px 300px)", "circle(1000px at 500px 300px)"]
                },
                {
                  duration: 450,
                  easing: "cubic-bezier(0.2, 0, 0, 1)",
                  fill: "both",
                  pseudoElement: "::view-transition-new(root)"
                }
              );
              result.waapi.created = !!anim;
              if (anim) {
                result.waapi.playState = anim.playState;
                result.waapi.currentTime = anim.currentTime;
                if (anim.effect && typeof anim.effect.getComputedTiming === "function") {
                  const timing = anim.effect.getComputedTiming();
                  result.waapi.timing = {
                    duration: timing.duration,
                    easing: timing.easing,
                    fill: timing.fill
                  };
                }
              }
            } catch (animErr) {
              result.waapi.errorName = animErr?.name || "Error";
              result.waapi.errorMessage = animErr?.message || String(animErr);
            }

          } catch (readyErr) {
            result.ready.rejected = true;
            result.ready.errorName = readyErr?.name || "Error";
            result.ready.errorMessage = readyErr?.message || String(readyErr);
          }

          try {
            await transition.finished;
            result.finished.resolved = true;
          } catch (finErr) {
            result.finished.rejected = true;
            result.finished.errorName = finErr?.name || "Error";
            result.finished.errorMessage = finErr?.message || String(finErr);
          }

        } catch (err) {
          result.error = String(err);
        }

        return result;
      };

      function loadSavedTheme() {
        const saved = localStorage.getItem("cvsu_gen_theme");
        const theme = saved || "dark";
        document.documentElement.setAttribute("data-theme", theme);
        updateThemeButtonState(theme);
        applyAccessibilityPreferences();
      }

      // Expose accessibility interfaces globally for UI controls and tests
      window.getStoredAccessibilityMotion = getStoredAccessibilityMotion;
      window.getEffectiveMotionPreference = getEffectiveMotionPreference;
      window.getStoredAccessibilityTransparency = getStoredAccessibilityTransparency;
      window.getEffectiveTransparencyPreference = getEffectiveTransparencyPreference;
      window.applyAccessibilityPreferences = applyAccessibilityPreferences;

      // ── Two-Tier Native Preferences Write-Through & Synchronization ──────────
      function syncCurrentPreferencesToNative() {
        if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.save_user_preferences !== "function") return;
        const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
        const prefs = {
          version: "1.0",
          theme: currentTheme,
          accessibility: {
            motion: getStoredAccessibilityMotion(),
            transparency: getStoredAccessibilityTransparency()
          }
        };
        window.pywebview.api.save_user_preferences(prefs).catch((e) => {
          console.warn("[Preferences] Write-through to native failed:", e);
        });
      }

      async function syncUserPreferencesWithNative() {
        if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.get_user_preferences !== "function") return;
        try {
          const nativePrefs = await window.pywebview.api.get_user_preferences();
          const localTheme = localStorage.getItem("cvsu_gen_theme");
          const localMotion = localStorage.getItem(CVSU_ACC_MOTION_KEY);
          const localTrans = localStorage.getItem(CVSU_ACC_TRANSPARENCY_KEY);

          if (nativePrefs && nativePrefs.theme && nativePrefs.accessibility) {
            const hasPersistedStore = nativePrefs._persisted === true;
            const alreadyMigrated = localStorage.getItem("cvsu_prefs_migrated") === "true";

            // Upward migration runs ONLY if Python disk store did not exist and migration hasn't run yet
            const canMigrate = !hasPersistedStore && !alreadyMigrated;
            const hasLocalCustom = (localTheme && localTheme !== "dark") ||
                                   (localMotion && localMotion !== "system") ||
                                   (localTrans && localTrans !== "system");

            if (canMigrate && hasLocalCustom) {
              const upwardPrefs = {
                version: "1.0",
                theme: localTheme || "dark",
                accessibility: {
                  motion: localMotion || "system",
                  transparency: localTrans || "system"
                }
              };
              localStorage.setItem("cvsu_prefs_migrated", "true");
              await window.pywebview.api.save_user_preferences(upwardPrefs);
            } else {
              // Authoritative native store updates local cache if different
              localStorage.setItem("cvsu_prefs_migrated", "true");
              if (nativePrefs.theme && nativePrefs.theme !== localTheme) {
                localStorage.setItem("cvsu_gen_theme", nativePrefs.theme);
                document.documentElement.setAttribute("data-theme", nativePrefs.theme);
                updateThemeButtonState(nativePrefs.theme);
              }
              if (nativePrefs.accessibility) {
                if (nativePrefs.accessibility.motion && nativePrefs.accessibility.motion !== localMotion) {
                  localStorage.setItem(CVSU_ACC_MOTION_KEY, nativePrefs.accessibility.motion);
                }
                if (nativePrefs.accessibility.transparency && nativePrefs.accessibility.transparency !== localTrans) {
                  localStorage.setItem(CVSU_ACC_TRANSPARENCY_KEY, nativePrefs.accessibility.transparency);
                }
                applyAccessibilityPreferences();
                if (typeof updateAccessibilitySettingsUI === "function") {
                  updateAccessibilitySettingsUI();
                }
              }
            }
          }
        } catch (e) {
          console.warn("[Preferences] Sync with native failed:", e);
        }
      }

      window.syncCurrentPreferencesToNative = syncCurrentPreferencesToNative;
      window.syncUserPreferencesWithNative = syncUserPreferencesWithNative;
