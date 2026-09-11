// ── Non-Blocking Toast Notification Engine ────────────────────────────
      function showToast(title, message, type = "info", duration = 4000) {
        const container = document.getElementById("toastContainer");
        if (!container) return;

        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        let iconSvg = "";
        if (type === "success") {
          iconSvg =
            '<svg class="toast-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-emerald)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>';
        } else if (type === "warning") {
          iconSvg =
            '<svg class="toast-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-amber)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
        } else if (type === "error") {
          iconSvg =
            '<svg class="toast-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-rose)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>';
        } else {
          iconSvg =
            '<svg class="toast-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent-blue)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
        }

        toast.innerHTML = `
          ${iconSvg}
          <div class="toast-content">
            <div class="toast-title">${escapeHTML(title)}</div>
            <div class="toast-message">${escapeHTML(message)}</div>
          </div>
          <button class="toast-close" type="button" onclick="this.parentElement.remove()">&times;</button>
        `;

        container.appendChild(toast);

        setTimeout(() => {
          toast.style.opacity = "0";
          toast.style.transform = "translateX(110%)";
          setTimeout(() => {
            if (toast.parentElement) toast.remove();
          }, 260);
        }, duration);
      }
