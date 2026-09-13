// ── Accessible Focus Trap & Focus Return Manager ─────────────────────────
const FocusTrapManager = {
  stack: [],

  // Preserves this.activeContainer and this.previousTrigger accessors for inspection
  get activeContainer() {
    return this.stack.length > 0 ? this.stack[this.stack.length - 1].container : null;
  },

  get previousTrigger() {
    return this.stack.length > 0 ? this.stack[this.stack.length - 1].previousTrigger : null;
  },

  trap(container, initialFocusEl, triggerEl) {
    if (!container) return;

    // If an overlay is already active, pause its keydown listener while sub-overlay is open
    if (this.stack.length > 0) {
      const currentTop = this.stack[this.stack.length - 1];
      if (currentTop.handleKeyDown) {
        document.removeEventListener("keydown", currentTop.handleKeyDown);
      }
    }

    const previousTrigger = triggerEl || document.activeElement;

    const getFocusables = () => {
      const selector =
        'button:not([disabled]):not([aria-hidden="true"]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
      return Array.from(container.querySelectorAll(selector)).filter((el) => {
        return el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement;
      });
    };

    requestAnimationFrame(() => {
      if (initialFocusEl && typeof initialFocusEl.focus === "function") {
        initialFocusEl.focus();
      } else {
        const focusables = getFocusables();
        if (focusables.length > 0) {
          focusables[0].focus();
        } else {
          container.setAttribute("tabindex", "-1");
          container.focus();
        }
      }
    });

    const handleKeyDown = (e) => {
      if (e.key !== "Tab") return;
      const focusables = getFocusables();
      if (focusables.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first || !container.contains(document.activeElement)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last || !container.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    this.stack.push({ container, previousTrigger, handleKeyDown });
  },

  release(container = null) {
    if (this.stack.length === 0) return;

    let popped = null;
    if (container) {
      const idx = this.stack.findIndex((item) => item.container === container);
      if (idx !== -1) {
        popped = this.stack.splice(idx, 1)[0];
        if (popped.handleKeyDown) {
          document.removeEventListener("keydown", popped.handleKeyDown);
        }
      }
    }

    if (!popped && this.stack.length > 0) {
      popped = this.stack.pop();
      if (popped.handleKeyDown) {
        document.removeEventListener("keydown", popped.handleKeyDown);
      }
    }

    if (!popped) return;

    // Resume keydown listener on the remaining top of the stack if present
    if (this.stack.length > 0) {
      const top = this.stack[this.stack.length - 1];
      if (top.handleKeyDown) {
        document.addEventListener("keydown", top.handleKeyDown);
      }
    }

    const trigger = popped.previousTrigger;
    if (trigger && typeof trigger.focus === "function") {
      requestAnimationFrame(() => {
        try {
          trigger.focus();
        } catch (err) {
          // Trigger may have been removed or unmounted
        }
      });
    }
  },

  releaseAll() {
    while (this.stack.length > 0) {
      this.release();
    }
  },
};

// ── Apple HIG Confirmation Modal Engine ───────────────────────────────
let activeConfirmResolve = null;

function dismissAppleConfirm() {
  const backdrop = document.getElementById("modalAppleConfirmBackdrop");
  if (backdrop && !backdrop.classList.contains("d-none")) {
    backdrop.classList.add("d-none");
    document.body.style.overflow = "";
    FocusTrapManager.release();
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
  triggerElement = null,
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

    const previousFocus = triggerElement || document.activeElement;

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

    // Trap focus within confirmation modal
    FocusTrapManager.trap(backdrop, btnCancel, previousFocus);

    const cleanup = (result) => {
      backdrop.classList.add("d-none");
      document.body.style.overflow = "";
      btnConfirm.onclick = null;
      btnCancel.onclick = null;
      activeConfirmResolve = null;
      FocusTrapManager.release();
      resolve(result);
    };

    btnConfirm.onclick = () => cleanup(true);
    btnCancel.onclick = () => cleanup(false);
  });
}
