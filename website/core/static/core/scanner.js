// Check-in scanner: USB scanners (keyboard + Enter), camera QR scanning and name search.
(() => {
  "use strict";
  const root = document.getElementById("scanner");
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const input = $("code");
  const results = $("results");
  const checkpoint = $("checkpoint");
  let direction = "in";
  let busy = false;
  let lastCode = "";
  let lastAt = 0;

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const textOn = (hex) => {
    const m = /^#([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) return "#fff";
    const [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255);
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.58 ? "#111827" : "#fff";
  };
  const icon = (name) => `<svg class="icon"><use href="#i-${name}"></use></svg>`;

  document.querySelectorAll("#direction a").forEach((a) =>
    a.addEventListener("click", (e) => {
      e.preventDefault();
      direction = a.dataset.dir;
      document.querySelectorAll("#direction a").forEach((x) => x.removeAttribute("aria-current"));
      a.setAttribute("aria-current", "page");
      input.focus();
    })
  );

  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": root.dataset.csrf },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(res.status);
    return res.json();
  }

  function beep(ok) {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = ok ? 880 : 220;
      gain.gain.value = 0.08;
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + (ok ? 0.12 : 0.35));
    } catch {}
    if (navigator.vibrate) navigator.vibrate(ok ? 60 : [80, 60, 80]);
  }

  function show(data) {
    const box = $("result");
    box.hidden = false;
    box.className = `result ${data.result} flash`;
    void box.offsetWidth;
    $("result-icon").innerHTML = icon(data.result === "denied" ? "x" : data.result === "warning" ? "alert" : "check");
    $("result-name").textContent = data.name || "Unknown ticket";
    $("result-type").innerHTML = data.type
      ? `<span class="pill" style="--c:${esc(data.color)};color:${textOn(data.color)}">${esc(data.type)}</span> ${esc(data.company)}${data.role ? " · " + esc(data.role) : ""}`
      : "";
    const fallback = data.result === "ok" ? (direction === "in" ? "Welcome!" : "Checked out") : "";
    $("result-msg").textContent = data.message || fallback;
    $("result-zones").innerHTML = (data.zones || []).map((z) => `<span class="badge">${esc(z)}</span>`).join("");
    const link = $("result-link");
    link.hidden = !data.url;
    if (data.url) link.href = data.url;

    const items = (data.items || []).filter((i) => !i.issued);
    $("result-items").innerHTML = items.length && data.result !== "denied"
      ? `<div class="small muted" style="margin-bottom:.35rem">Hand out:</div><div class="row">` +
        items.map((i) => `<button class="btn btn-sm" data-handout="${i.id}">${icon("box")}${esc(i.label)}</button>`).join("") +
        `<button class="btn btn-sm btn-success" data-handout-all>${icon("check")}All handed out</button></div>`
      : "";
    beep(data.result !== "denied");
    addLog(data);
    if (data.first_time) bump("stat-arrived", 1);
    if (data.result !== "denied" && !checkpoint.value) bump("stat-inside", direction === "in" && data.result === "ok" ? 1 : direction === "out" && data.result === "ok" ? -1 : 0);
  }

  function bump(id, n) {
    const el = $(id);
    if (el && n) el.textContent = Math.max(0, parseInt(el.textContent, 10) + n);
  }

  function addLog(data) {
    const log = $("log");
    log.querySelector("[data-empty]")?.remove();
    const color = data.result === "ok" ? "var(--success)" : data.result === "warning" ? "var(--warning)" : "var(--danger)";
    const zone = checkpoint.value ? " · " + checkpoint.selectedOptions[0].text.replace("Zone check · ", "") : "";
    const now = new Date().toTimeString().slice(0, 5);
    log.insertAdjacentHTML(
      "afterbegin",
      `<li><span class="dot" style="--c:${color}"></span><span class="grow small"><b>${esc(data.name || "Unknown code")}</b><br><span class="muted">${direction === "in" ? "In" : "Out"}${esc(zone)}${data.message ? " · " + esc(data.message) : ""}</span></span><span class="small faint">${now}</span></li>`
    );
    while (log.children.length > 15) log.lastElementChild.remove();
  }

  async function scan(code) {
    code = (code || "").trim();
    if (!code || busy) return;
    // Ignore the same code read twice by the camera within 3 seconds.
    if (code === lastCode && Date.now() - lastAt < 3000) return;
    lastCode = code;
    lastAt = Date.now();
    busy = true;
    results.innerHTML = "";
    try {
      show(await post(root.dataset.scanUrl, { code, zone: checkpoint.value, direction }));
    } catch {
      show({ result: "denied", message: "Connection problem – try again" });
    } finally {
      busy = false;
      input.value = "";
      input.focus();
    }
  }

  // Items handed out
  $("result-items").addEventListener("click", async (e) => {
    const all = e.target.closest("[data-handout-all]");
    const one = e.target.closest("[data-handout]");
    const buttons = all ? [...$("result-items").querySelectorAll("[data-handout]")] : one ? [one] : [];
    for (const b of buttons) {
      await post(root.dataset.handoutUrl.replace(/0\/$/, `${b.dataset.handout}/`), {});
      b.disabled = true;
      b.innerHTML = icon("check") + b.textContent;
    }
    if (all) all.remove();
    input.focus();
  });

  // Typing: name search suggestions. Enter: treat as scanned code (or pick single result).
  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2 || /^[A-Za-z0-9_-]{20,}$/.test(q)) { results.innerHTML = ""; return; }
    timer = setTimeout(async () => {
      const res = await fetch(`${root.dataset.searchUrl}?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      if (input.value.trim() !== q) return;
      results.innerHTML = data.results.length
        ? data.results.map((r) =>
            `<button type="button" data-token="${esc(r.token)}"><span class="avatar" style="--c:${esc(r.color)};--t:${textOn(r.color)}">${esc(r.name.slice(0, 1))}</span><span class="grow"><b>${esc(r.name)}</b><br><span class="small muted">${esc(r.type)}${r.company ? " · " + esc(r.company) : ""}</span></span>${r.approved ? "" : `<span class="badge tone-warning">${esc(r.status)}</span>`}</button>`
          ).join("")
        : `<p class="muted small" style="padding:.5rem .8rem">No one found for “${esc(q)}”.</p>`;
    }, 200);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const options = results.querySelectorAll("[data-token]");
    if (options.length === 1) scan(options[0].dataset.token);
    else scan(input.value);
  });
  results.addEventListener("click", (e) => {
    const b = e.target.closest("[data-token]");
    if (b) { lastCode = ""; scan(b.dataset.token); }
  });

  // Camera scanning --------------------------------------------------------
  const video = $("video");
  let stream = null;
  let detector = null;
  let canvas = null;

  async function loadJsQR() {
    if (window.jsQR) return;
    await new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js";
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    } catch {
      show({ result: "denied", message: "Camera not available – allow camera access or use a USB scanner." });
      return;
    }
    video.srcObject = stream;
    await video.play();
    $("camera").hidden = false;
    if ("BarcodeDetector" in window) {
      try { detector = new window.BarcodeDetector({ formats: ["qr_code"] }); } catch { detector = null; }
    }
    if (!detector) {
      try { await loadJsQR(); } catch { show({ result: "denied", message: "QR library could not load (offline?)." }); }
      canvas = document.createElement("canvas");
    }
    requestAnimationFrame(tick);
  }

  function stopCamera() {
    stream?.getTracks().forEach((t) => t.stop());
    stream = null;
    $("camera").hidden = true;
  }

  let lastFrame = 0;
  async function tick(t) {
    if (!stream) return;
    if (t - lastFrame > 180 && video.readyState >= 2 && !busy) {
      lastFrame = t;
      try {
        let value = null;
        if (detector) {
          const codes = await detector.detect(video);
          value = codes[0]?.rawValue;
        } else if (window.jsQR) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          const ctx = canvas.getContext("2d", { willReadFrequently: true });
          ctx.drawImage(video, 0, 0);
          const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
          value = window.jsQR(img.data, img.width, img.height)?.data;
        }
        if (value) await scan(value);
      } catch {}
    }
    requestAnimationFrame(tick);
  }

  $("camera-toggle").addEventListener("click", () => (stream ? stopCamera() : startCamera()));
})();
