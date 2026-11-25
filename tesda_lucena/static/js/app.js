/* TESDA Lucena – pop-ups, password toggle, mobile menus. Plain JavaScript, no build step. */
(function () {
  "use strict";

  const ICON = {
    notify: "bi-bell-fill",
    success: "bi-check-lg",
    confirm: "bi-exclamation-lg",
    exit: "bi-box-arrow-right",
    info: "bi-info-lg",
    error: "bi-x-lg",
    course: "bi-book",
  };

  function h(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text; // textContent keeps user data safe from XSS
    return el;
  }

  let current = null;
  let lastFocus = null;

  function closeModal() {
    if (!current) return;
    current.remove();
    current = null;
    document.body.classList.remove("modal-open");
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
  }

  /**
   * showModal({type, title, message, body, buttons:[{label, ghost, href, onClick, keepOpen}]})
   * type: notify | success | confirm | exit | info | error | course
   */
  function showModal(opt) {
    closeModal();
    lastFocus = document.activeElement;

    const backdrop = h("div", "modal-backdrop");
    const modal = h("div", "modal modal-" + opt.type);
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-label", opt.title);

    const close = h("button", "modal-close");
    close.type = "button";
    close.setAttribute("aria-label", "Close");
    close.innerHTML = '<i class="bi bi-x-lg"></i>';
    close.addEventListener("click", closeModal);

    const head = h("div", "modal-head");
    const icon = h("span", "modal-icon");
    icon.innerHTML = '<i class="bi ' + (ICON[opt.type] || ICON.info) + '"></i>';
    head.append(icon, h("h3", null, opt.title));
    modal.append(close, head);

    if (opt.body) modal.append(opt.body);
    else modal.append(h("p", "modal-text", opt.message || ""));

    const actions = h("div", "modal-actions");
    (opt.buttons || [{ label: "OK" }]).forEach(function (b) {
      const btn = b.href ? h("a") : h("button");
      if (!b.href) btn.type = "button";
      else btn.href = b.href;
      btn.className = "btn " + (b.ghost ? "btn-soft" : "btn-primary");
      btn.textContent = b.label;
      btn.addEventListener("click", function () {
        if (b.onClick) b.onClick();
        if (!b.href && !b.keepOpen) closeModal();
      });
      actions.append(btn);
    });
    modal.append(actions);

    backdrop.append(modal);
    backdrop.addEventListener("mousedown", function (e) {
      if (e.target === backdrop) closeModal();
    });
    document.body.append(backdrop);
    document.body.classList.add("modal-open");
    current = backdrop;
    (actions.querySelector(".btn-primary") || close).focus();
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeModal();
  });

  // Confirmation / exit pop-ups on forms:  <form data-confirm ...>  <form data-exit ...>
  document.addEventListener("submit", function (e) {
    const form = e.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.confirmed) return;
    const isExit = form.hasAttribute("data-exit");
    if (!isExit && !form.hasAttribute("data-confirm")) return;
    e.preventDefault();
    showModal({
      type: isExit ? "exit" : "confirm",
      title: isExit ? "Exit" : form.dataset.confirmTitle || "Confirm Action",
      message: isExit
        ? "You will be redirected to the login page. Do you want to continue?"
        : form.dataset.confirmMessage || "Are you sure?",
      buttons: [
        { label: "Cancel", ghost: true },
        {
          label: isExit ? "Continue" : "Confirm",
          onClick: function () {
            form.dataset.confirmed = "1";
            form.submit();
          },
        },
      ],
    });
  });

  document.addEventListener("click", function (e) {
    // Information pop-up:  <button data-info="message" data-info-title="Title">
    const info = e.target.closest("[data-info]");
    if (info) {
      e.preventDefault();
      showModal({ type: "info", title: info.dataset.infoTitle || "Information", message: info.dataset.info });
      return;
    }
    // Course information pop-up
    const course = e.target.closest("[data-course]");
    if (course) {
      e.preventDefault();
      const d = course.dataset;
      const body = h("div", "modal-body");
      body.append(h("h4", null, d.courseName));
      const list = h("ul", "course-info-list");
      [d.courseNc, d.courseProvider, "Training Duration: " + d.courseHours + " Hours"].forEach(function (t) {
        if (t) list.append(h("li", null, t));
      });
      body.append(list);
      showModal({ type: "course", title: "Course Information", body: body, buttons: [{ label: "Got it" }] });
      return;
    }
    // Password visibility toggle
    const toggle = e.target.closest("[data-toggle-password]");
    if (toggle) {
      const input = toggle.parentElement.querySelector("input");
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      toggle.querySelector("i").className = "bi " + (show ? "bi-eye-slash" : "bi-eye");
      toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
      return;
    }
    // Mobile menus
    if (e.target.closest("[data-toggle-nav]")) {
      document.querySelector(".site-header").classList.toggle("open");
    }
    if (e.target.closest("[data-toggle-sidebar]")) {
      document.getElementById("sidebar").classList.toggle("open");
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    // Django messages -> success / error / information pop-ups
    const flashEl = document.getElementById("flash-data");
    const flash = flashEl ? JSON.parse(flashEl.textContent) : [];
    if (flash.length) {
      const m = flash[0];
      if (m.level === "success") showModal({ type: "success", title: "Success!", message: m.text });
      else if (m.level === "error") showModal({ type: "error", title: "Something went wrong", message: m.text });
      else showModal({ type: "info", title: "Information", message: m.text });
      return;
    }
    // "You have N new notifications" pop-up after login
    const count = parseInt(document.body.dataset.notifyCount || "0", 10);
    if (count > 0) {
      showModal({
        type: "notify",
        title: "Notifications",
        message: "You have " + count + " new " + (count === 1 ? "notification." : "notifications."),
        buttons: [{ label: "View All", href: document.body.dataset.notifyUrl }],
      });
    }
  });
})();
