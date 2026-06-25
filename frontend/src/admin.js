// Admin-only bundle: the Trix rich-text editor. Loaded only by dashboard pages,
// so the public site stays lean. Editor output is HTML and is sanitized
// server-side with nh3 on save (apps/content), so this stays a pure UI concern.
import "trix";
import "trix/dist/trix.css";
import "./admin.css";

// Media picker → Trix. The picker modal (dashboard/_media_picker.html) calls this
// to drop a library image into the active editor. Output is sanitized server-side
// (nh3 allows img src/alt), so inserting raw HTML here is safe.
window.cmstackInsertImage = function (url, alt) {
  const editor = document.querySelector("trix-editor");
  if (!editor || !editor.editor) return;
  const safeAlt = (alt || "").replace(/"/g, "&quot;");
  editor.editor.insertHTML(`<img src="${url}" alt="${safeAlt}">`);
};

// Accessible confirm dialog: intercept submits of destructive forms that opt in
// with data-dp-confirm="message" and hand off to the focus-trapped Alpine dialog
// in dashboard/_confirm_dialog.html. Capture phase so we run before submission.
document.addEventListener(
  "submit",
  (e) => {
    const form = e.target;
    const message = form instanceof HTMLFormElement && form.getAttribute("data-dp-confirm");
    if (!message) return;
    e.preventDefault();
    window.dispatchEvent(new CustomEvent("dp-confirm", { detail: { message, form } }));
  },
  true,
);

// Label the Trix toolbar's icon-only buttons for screen readers (U6 a11y). Trix
// renders them with a title but no accessible name; mirror title → aria-label.
document.addEventListener("trix-initialize", (e) => {
  const toolbar = e.target.toolbarElement;
  if (!toolbar) return;
  toolbar.querySelectorAll("button[title]").forEach((btn) => {
    if (!btn.getAttribute("aria-label")) btn.setAttribute("aria-label", btn.getAttribute("title"));
  });
});
