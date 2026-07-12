// Admin-only bundle: the Trix rich-text editor. Loaded only by dashboard pages,
// so the public site stays lean. Editor output is HTML and is sanitized
// server-side with nh3 on save (apps/content), so this stays a pure UI concern.
import "trix";
import "trix/dist/trix.css";
import Sortable from "sortablejs";
import "./admin.css";

// Menu builder: drag-to-reorder as a PROGRESSIVE ENHANCEMENT. With JS off the
// server-rendered keyboard ↑/↓ move forms are the path; this never touches them.
// Reordering is sibling-scoped — onMove rejects drops into a different parent
// group, so a drag can only rearrange items that share a data-parent-id. On drop
// we POST the new order of THAT group's ids as JSON; the server renumbers them.
function initMenuReorder(list) {
  if (list.dataset.menuReorderReady) return;
  list.dataset.menuReorderReady = "1";
  // Reveal the drag handles now that JS is present (they're hidden by default,
  // so a no-JS user never sees an affordance that wouldn't work).
  list.querySelectorAll(".dp-drag-handle").forEach((h) => h.classList.remove("hidden"));

  const url = list.dataset.menuReorderUrl;
  const csrftoken = (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || "";

  Sortable.create(list, {
    handle: ".dp-drag-handle",
    animation: 150,
    draggable: "[data-menu-item]",
    // Only allow dropping next to a row in the same sibling group.
    onMove: (evt) =>
      evt.dragged.dataset.parentId === evt.related.dataset.parentId,
    onEnd: (evt) => {
      const parentId = evt.item.dataset.parentId;
      const order = Array.from(list.querySelectorAll("[data-menu-item]"))
        .filter((row) => row.dataset.parentId === parentId)
        .map((row) => Number(row.dataset.itemId));
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken },
        body: JSON.stringify({ order }),
      }).catch(() => {});
    },
  });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-menu-reorder]").forEach(initMenuReorder);
});

// Media picker → Trix. The picker modal (dashboard/_media_picker.html) calls this
// to drop a library image into the active editor. Output is sanitized server-side
// (nh3 allows img src/alt), so inserting raw HTML here is safe.
window.agenticCmsInsertImage = function (url, alt) {
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
