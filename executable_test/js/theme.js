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

      // ── Single shared duration token ──────────────────────────────────────
      // All timing (WAAPI iris, CSS custom property, icon animation) derives
      // from this one constant. Do NOT duplicate or hardcode elsewhere.
      const THEME_TRANSITION_DURATION_MS = 450;

      async function toggleTheme(event) {
        const doc = document.documentElement;
        const currentTheme = doc.getAttribute("data-theme") || "dark";
        const newTheme = currentTheme === "dark" ? "light" : "dark";

        const btn = document.getElementById("btnToggleTheme");
        const iconSpan = document.getElementById("themeIcon");

        // ── PART 6/7: Evaluate motion preference FIRST before any animation ──
        // The iris animation is JS-owned (WAAPI), so accessibility must be
        // evaluated in JS, not CSS.
        const reduceMotion = window.matchMedia(
          "(prefers-reduced-motion: reduce)"
        ).matches;

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
        };

        if (!document.startViewTransition || reduceMotion) {
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

      function loadSavedTheme() {
        const saved = localStorage.getItem("cvsu_gen_theme");
        const theme = saved || "dark";
        document.documentElement.setAttribute("data-theme", theme);
        updateThemeButtonState(theme);
      }
