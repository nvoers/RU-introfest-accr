// Renders <div data-qr="text"> as an SVG QR code (needs qrcode-generator).
window.addEventListener("load", () => {
  if (typeof window.qrcode !== "function") return;
  document.querySelectorAll("[data-qr]").forEach((el) => {
    const qr = window.qrcode(0, "M");
    qr.addData(el.dataset.qr);
    qr.make();
    el.innerHTML = qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
  });
});
