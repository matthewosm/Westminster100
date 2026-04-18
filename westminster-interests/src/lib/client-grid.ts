/** Shared Grid.js post-render enhancements.
 *
 * Sets `data-label` on every rendered `<td>` from the text of the matching
 * `<th>` in the same table. Mobile CSS (theme.css, below 640px) uses
 * `data-label` to stack each row into a labelled card without changing
 * any page-level code.
 *
 * Runs once on page load for every `.gridjs-wrapper` that exists, then
 * re-runs whenever a tbody mutates (Grid.js re-renders on sort, filter,
 * pagination, forceRender, etc.).
 */

const LABELLED_FLAG = "wiLabelled";

function labelCellsIn(wrapper: HTMLElement): void {
  const headers = wrapper.querySelectorAll<HTMLElement>("thead th");
  if (headers.length === 0) return;
  const labels = Array.from(headers, (h) => (h.textContent ?? "").trim());
  const rows = wrapper.querySelectorAll<HTMLElement>("tbody tr");
  rows.forEach((row) => {
    const cells = row.querySelectorAll<HTMLElement>("td");
    cells.forEach((td, i) => {
      const label = labels[i] ?? "";
      if (label) td.setAttribute("data-label", label);
    });
  });
}

function attach(wrapper: HTMLElement): void {
  if ((wrapper.dataset as DOMStringMap)[LABELLED_FLAG] === "1") return;
  (wrapper.dataset as DOMStringMap)[LABELLED_FLAG] = "1";
  labelCellsIn(wrapper);
  // Re-label after every re-render. Debounced so Grid.js's
  // multi-mutation renders (header swap + body swap) only trigger one
  // labelling pass.
  let pending = false;
  const observer = new MutationObserver(() => {
    if (pending) return;
    pending = true;
    queueMicrotask(() => {
      pending = false;
      labelCellsIn(wrapper);
    });
  });
  observer.observe(wrapper, { childList: true, subtree: true });
}

export function enableMobileGridLabels(): void {
  const scan = () => {
    document
      .querySelectorAll<HTMLElement>(".gridjs-wrapper")
      .forEach((el) => attach(el));
  };
  scan();
  // Grid.js mounts are in page <script> modules that may run after this
  // helper. Observe the document body so newly-inserted wrappers pick
  // up labelling automatically, then disconnect once everything is
  // stable (after a short idle window).
  const rootObserver = new MutationObserver(() => scan());
  rootObserver.observe(document.body, { childList: true, subtree: true });
}
