// Progressive enhancements. Pages keep working without JavaScript.
(() => {
  "use strict";
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  // Dialogs ---------------------------------------------------------------
  document.addEventListener("click", (e) => {
    const opener = e.target.closest("[data-open]");
    if (opener) {
      const dlg = document.getElementById(opener.dataset.open);
      if (dlg) {
        dlg.showModal();
        dlg.querySelector("input:not([type=hidden]):not([type=checkbox]):not([type=color]), select, textarea")?.focus();
      }
      return;
    }
    if (e.target.closest("[data-close]")) {
      e.target.closest("dialog")?.close();
      return;
    }
    if (e.target instanceof HTMLDialogElement) {
      const r = e.target.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) e.target.close();
    }
    if (e.target.closest("[data-nav-toggle]")) document.body.classList.toggle("nav-open");
    else if (document.body.classList.contains("nav-open") && !e.target.closest(".sidebar")) {
      document.body.classList.remove("nav-open");
    }
  });
  const reopen = document.body.dataset.openDialog;
  if (reopen) document.getElementById(reopen)?.showModal();

  // Confirmations: <form data-confirm="…"> or <button data-confirm="…">
  document.addEventListener("submit", (e) => {
    const msg = e.submitter?.dataset.confirm || e.target.dataset.confirm;
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // Auto-submit filter forms when a select changes.
  document.addEventListener("change", (e) => {
    if (e.target.matches("[data-autosubmit] select")) e.target.form.requestSubmit();
  });

  // Copy buttons: <button data-copy="#input-id">
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    const input = document.querySelector(btn.dataset.copy);
    try {
      await navigator.clipboard.writeText(input.value);
    } catch {
      input.select();
      document.execCommand("copy");
    }
    const old = btn.innerHTML;
    btn.textContent = "Copied!";
    setTimeout(() => (btn.innerHTML = old), 1400);
  });

  // Toasts ------------------------------------------------------------------
  $$(".toast").forEach((t, i) => {
    const hide = () => { t.classList.add("hide"); setTimeout(() => t.remove(), 260); };
    t.querySelector("button")?.addEventListener("click", hide);
    if (!t.matches(".error, .warning")) setTimeout(hide, 4500 + i * 600);
  });

  // Row selection + bulk bar ---------------------------------------------------
  $$("[data-bulk]").forEach((form) => {
    const boxes = $$("input[name=ids]", form);
    const alls = $$("[data-check-all]", form);
    const bar = form.querySelector(".bulkbar");
    const count = form.querySelector("[data-selected-count]");
    // Each "select all" box controls the rows of its own table.
    const scoped = (all) => $$("input[name=ids]", all.closest("table") || form);
    const sync = () => {
      const n = boxes.filter((b) => b.checked).length;
      boxes.forEach((b) => b.closest("tr")?.classList.toggle("selected", b.checked));
      if (bar) bar.hidden = n === 0;
      if (count) count.textContent = n;
      alls.forEach((all) => {
        const own = scoped(all);
        const k = own.filter((b) => b.checked).length;
        all.checked = k > 0 && k === own.length;
        all.indeterminate = k > 0 && k < own.length;
      });
    };
    alls.forEach((all) =>
      all.addEventListener("change", () => { scoped(all).forEach((b) => (b.checked = all.checked)); sync(); })
    );
    boxes.forEach((b) => b.addEventListener("change", sync));
    sync();
  });
})();
