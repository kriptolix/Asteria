(function () {
  "use strict";

  function setupDrawer(toggleBtn, panel, closeBtn, overlay) {
    if (!toggleBtn || !panel || !overlay) return;

    function isOpen() {
      return panel.classList.contains("is-open");
    }

    function open() {
      panel.classList.add("is-open");
      overlay.hidden = false;
      toggleBtn.setAttribute("aria-expanded", "true");
      document.body.classList.add("drawer-open");
      if (closeBtn) closeBtn.focus();
    }

    function close(returnFocus) {
      panel.classList.remove("is-open");
      overlay.hidden = true;
      toggleBtn.setAttribute("aria-expanded", "false");
      document.body.classList.remove("drawer-open");
      if (returnFocus) toggleBtn.focus();
    }

    toggleBtn.addEventListener("click", function () {
      if (isOpen()) {
        close(true);
      } else {
        open();
      }
    });

    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        close(true);
      });
    }

    overlay.addEventListener("click", function () {
      close(true);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && isOpen()) {
        close(true);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupDrawer(
      document.getElementById("menu-toggle"),
      document.getElementById("site-menu-drawer"),
      document.getElementById("menu-close"),
      document.getElementById("menu-overlay")
    );

    setupDrawer(
      document.getElementById("sidebar-toggle"),
      document.getElementById("sidebar-drawer"),
      document.getElementById("sidebar-close"),
      document.getElementById("sidebar-overlay")
    );
  });
})();