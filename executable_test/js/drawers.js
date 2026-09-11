// ── Drawers Controller ────────────────────────────────────────────────
      function openHelpDrawer() {
        closeAllDrawers();
        document.getElementById("helpDrawer").classList.add("active");
        document.getElementById("drawerBackdrop").classList.add("active");
      }

      function openLogsDrawer() {
        closeAllDrawers();
        document.getElementById("logsDrawer").classList.add("active");
        document.getElementById("drawerBackdrop").classList.add("active");
        refreshLogs();
      }

      function closeAllDrawers() {
        document
          .querySelectorAll(".drawer-panel")
          .forEach((d) => d.classList.remove("active"));
        document.getElementById("drawerBackdrop").classList.remove("active");
      }

      async function refreshLogs() {
        if (
          window.pywebview &&
          window.pywebview.api &&
          window.pywebview.api.get_recent_logs
        ) {
          const logs = await window.pywebview.api.get_recent_logs(120);
          document.getElementById("logContent").innerText = logs;
        } else {
          document.getElementById("logContent").innerText =
            "Log reader available inside desktop runtime.";
        }
      }

      function copyLogs() {
        const text = document.getElementById("logContent").innerText;
        navigator.clipboard.writeText(text);
        showToast(
          "Copied to Clipboard",
          "Diagnostics log content copied to clipboard.",
          "info",
        );
      }

      async function openLogFolder() {
        if (
          window.pywebview &&
          window.pywebview.api &&
          window.pywebview.api.open_log_folder
        ) {
          try {
            const res = await window.pywebview.api.open_log_folder();
            if (res && res.status === "error") {
              showToast("Logs Directory", res.message || "Logs folder does not exist", "error");
            }
          } catch (e) {
            showToast("Logs Directory", String(e), "error");
          }
        }
      }



      // ── Help Drawer Navigation & Search ───────────────────────────────────
      function switchHelpTab(tabName) {
        const tabs = ["Overview", "Naming", "Formats", "Faq"];
        tabs.forEach((t) => {
          const tabBtn = document.getElementById(`helpTab${t}`);
          const content = document.getElementById(`helpContent${t}`);
          if (tabBtn) tabBtn.classList.toggle("active", t === tabName);
          if (content) content.classList.toggle("d-none", t !== tabName);
        });
        const tabsContainer = document.querySelector(".drawer-tabs");
        if (tabsContainer) {
          tabsContainer.scrollTop = 0;
        }
      }

      function filterHelpContent(query) {
        const q = (query || "").trim().toLowerCase();
        const tabs = ["Overview", "Naming", "Formats", "Faq"];
        if (!q) {
          const activeTab = document.querySelector(".drawer-tab.active");
          const activeName = activeTab
            ? activeTab.id.replace("helpTab", "")
            : "Overview";
          switchHelpTab(activeName);
          document
            .querySelectorAll(".drawer-section")
            .forEach((s) => (s.style.display = ""));
          return;
        }

        tabs.forEach((t) => {
          const content = document.getElementById(`helpContent${t}`);
          if (content) content.classList.remove("d-none");
        });

        document.querySelectorAll(".drawer-section").forEach((sec) => {
          const txt = (sec.innerText || "").toLowerCase();
          sec.style.display = txt.includes(q) ? "" : "none";
        });
      }
