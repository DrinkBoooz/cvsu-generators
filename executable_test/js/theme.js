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

      async function toggleTheme(event) {
        const doc = document.documentElement;
        doc.classList.add("theme-transitioning");
        const currentTheme = doc.getAttribute("data-theme") || "dark";
        const newTheme = currentTheme === "dark" ? "light" : "dark";

        const btn = document.getElementById("btnToggleTheme");
        const iconSpan = document.getElementById("themeIcon");
        if (iconSpan) {
          iconSpan.classList.add("spin-morph");
          setTimeout(() => iconSpan.classList.remove("spin-morph"), 400);
        }

        const applyTheme = () => {
          doc.classList.add("theme-transitioning");
          doc.setAttribute("data-theme", newTheme);
          updateThemeButtonState(newTheme);
          try {
            localStorage.setItem("cvsu_gen_theme", newTheme);
          } catch (e) {}
          // Force layout flush so new styles are registered in snapshot
          void doc.offsetHeight;
        };

        if (document.startViewTransition) {
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

          const endRadius = Math.hypot(
            Math.max(x, window.innerWidth - x),
            Math.max(y, window.innerHeight - y),
          );

          doc.style.setProperty("--vt-x", `${x}px`);
          doc.style.setProperty("--vt-y", `${y}px`);
          doc.style.setProperty("--vt-radius", `${endRadius}px`);

          try {
            const transition = document.startViewTransition(() => {
              applyTheme();
            });

            await transition.ready;

            const animation = doc.animate(
              {
                clipPath: [
                  `circle(0px at ${x}px ${y}px)`,
                  `circle(${endRadius}px at ${x}px ${y}px)`,
                ],
              },
              {
                duration: 650,
                easing: "cubic-bezier(0.25, 1, 0.5, 1)",
                pseudoElement: "::view-transition-new(root)",
              },
            );

            await animation.finished;
          } catch (err) {
            applyTheme();
          } finally {
            doc.classList.remove("theme-transitioning");
          }
        } else {
          applyTheme();
          requestAnimationFrame(() => {
            doc.classList.remove("theme-transitioning");
          });
        }
      }

      function loadSavedTheme() {
        const saved = localStorage.getItem("cvsu_gen_theme");
        const theme = saved || "dark";
        document.documentElement.setAttribute("data-theme", theme);
        updateThemeButtonState(theme);
      }
