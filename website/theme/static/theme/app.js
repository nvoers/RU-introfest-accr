// Small progressive enhancements. Every page works without this file.
(() => {
  "use strict";

  // Dialogs: <button data-open="dialog-id">, <button data-close>
  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-open]");
    if (opener) {
      const dialog = document.getElementById(opener.dataset.open);
      if (dialog) {
        dialog.showModal();
        const first = dialog.querySelector(
          "input:not([type=hidden]):not([type=color]), select, textarea"
        );
        if (first) first.focus();
      }
      return;
    }
    if (event.target.closest("[data-close]")) {
      event.target.closest("dialog")?.close();
      return;
    }
    // Click on the backdrop closes the dialog.
    if (event.target instanceof HTMLDialogElement) {
      const r = event.target.getBoundingClientRect();
      const inside =
        event.clientX >= r.left &&
        event.clientX <= r.right &&
        event.clientY >= r.top &&
        event.clientY <= r.bottom;
      if (!inside) event.target.close();
    }
  });

  // Re-open a dialog after a failed form submission.
  const reopen = document.body.dataset.openDialog;
  if (reopen) document.getElementById(reopen)?.showModal();

  // Confirmation for destructive forms: <form data-confirm="Sure?">
  document.addEventListener("submit", (event) => {
    const message = event.target.dataset?.confirm;
    if (message && !window.confirm(message)) event.preventDefault();
  });

  // Toasts auto-dismiss.
  document.querySelectorAll(".toast").forEach((toast, i) => {
    const hide = () => {
      toast.classList.add("hide");
      setTimeout(() => toast.remove(), 260);
    };
    toast.querySelector("button")?.addEventListener("click", hide);
    const persistent = toast.classList.contains("warning") || toast.classList.contains("error");
    if (!persistent) setTimeout(hide, 4500 + i * 500);
  });

  // Client-side filtering: [data-filter-scope] containing
  //   inputs/selects with data-filter="<key>" and items with data-<key>.
  //   data-filter="q" matches against data-search (substring, accent-insensitive).
  const normalize = (s) =>
    (s || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");

  document.querySelectorAll("[data-filter-scope]").forEach((scope) => {
    const controls = [...scope.querySelectorAll("[data-filter]")];
    const items = [...scope.querySelectorAll("[data-item]")];
    const count = scope.querySelector("[data-filter-count]");
    const empty = scope.querySelector("[data-filter-empty]");
    items.forEach((item) => (item._search = normalize(item.dataset.search)));

    const apply = () => {
      const active = controls
        .map((c) => [c.dataset.filter, c.value])
        .filter(([, v]) => v !== "");
      let shown = 0;
      items.forEach((item) => {
        const match = active.every(([key, value]) => {
          if (key === "q") {
            return normalize(value)
              .split(/\s+/)
              .every((word) => item._search.includes(word));
          }
          return item.dataset[key] === value;
        });
        item.hidden = !match;
        if (match) shown++;
      });
      if (count) count.textContent = shown === items.length
        ? `${items.length} total`
        : `Showing ${shown} of ${items.length}`;
      if (empty) empty.hidden = shown !== 0 || items.length === 0;
      scope._visible = items.filter((i) => !i.hidden);
    };

    controls.forEach((c) => {
      c.addEventListener(c.tagName === "SELECT" ? "change" : "input", apply);
    });

    // Enter in the search box: act on the single remaining result.
    const search = scope.querySelector('[data-filter="q"]');
    search?.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        search.value = "";
        apply();
      }
      if (event.key !== "Enter") return;
      event.preventDefault();
      const visible = scope._visible || [];
      if (visible.length !== 1) return;
      const primary = visible[0].querySelector("[data-primary]");
      if (primary) primary.click();
    });

    apply();
  });

  // "/" focuses the main search box.
  document.addEventListener("keydown", (event) => {
    if (event.key !== "/" || event.metaKey || event.ctrlKey) return;
    const tag = document.activeElement?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    const search = document.querySelector("[data-search-main]");
    if (search) {
      event.preventDefault();
      search.focus();
      search.select();
    }
  });
})();
