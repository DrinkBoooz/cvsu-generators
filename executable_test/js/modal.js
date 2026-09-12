// ── Apple HIG Confirmation Modal Engine ───────────────────────────────
      let activeConfirmResolve = null;

      function dismissAppleConfirm() {
        const backdrop = document.getElementById("modalAppleConfirmBackdrop");
        if (backdrop && !backdrop.classList.contains("d-none")) {
          backdrop.classList.add("d-none");
          if (activeConfirmResolve) {
            activeConfirmResolve(false);
            activeConfirmResolve = null;
          }
        }
      }

      function showAppleConfirm({
        title = "Confirm Action",
        message = "Are you sure you want to proceed?",
        confirmText = "Confirm",
        cancelText = "Cancel",
        isDestructive = true,
      } = {}) {
        return new Promise((resolve) => {
          activeConfirmResolve = resolve;
          const backdrop = document.getElementById("modalAppleConfirmBackdrop");
          const titleEl = document.getElementById("appleConfirmTitle");
          const msgEl = document.getElementById("appleConfirmMessage");
          const btnConfirm = document.getElementById("btnAppleConfirmProceed");
          const btnCancel = document.getElementById("btnAppleConfirmCancel");
          const iconWrapper = document.getElementById("appleConfirmIconWrapper");

          if (!backdrop || !titleEl || !msgEl || !btnConfirm || !btnCancel) {
            resolve(false);
            return;
          }

          titleEl.textContent = title;
          msgEl.textContent = message;
          btnConfirm.textContent = confirmText;
          btnCancel.textContent = cancelText;

          if (isDestructive) {
            btnConfirm.style.background = "var(--accent-rose)";
            btnConfirm.style.borderColor = "var(--accent-rose)";
            btnConfirm.style.boxShadow = "0 4px 14px rgba(239, 68, 68, 0.35)";
            if (iconWrapper) {
              iconWrapper.style.background = "rgba(239, 68, 68, 0.12)";
              iconWrapper.style.color = "var(--accent-rose)";
            }
          } else {
            btnConfirm.style.background = "var(--accent-emerald)";
            btnConfirm.style.borderColor = "var(--accent-emerald)";
            btnConfirm.style.boxShadow = "0 4px 14px var(--accent-emerald-glow)";

            if (iconWrapper) {
              iconWrapper.style.background = "var(--accent-emerald-glow)";
              iconWrapper.style.color = "var(--accent-emerald)";
            }
          }

          backdrop.classList.remove("d-none");
          document.body.style.overflow = "hidden";
          btnCancel.focus();

          const cleanup = (result) => {
            backdrop.classList.add("d-none");
            document.body.style.overflow = "";
            btnConfirm.onclick = null;
            btnCancel.onclick = null;
            activeConfirmResolve = null;
            resolve(result);
          };

          btnConfirm.onclick = () => cleanup(true);
          btnCancel.onclick = () => cleanup(false);
        });
      }
