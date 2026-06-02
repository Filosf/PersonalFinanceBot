function normalizeValue(field) {
  if (field.type === "number" && field.value !== "") {
    return Number(field.value).toFixed(2);
  }
  return field.value;
}

function initializeDirtyTracking(root = document) {
  root.querySelectorAll(".row-form, .dirty-track-form, form[data-dirty-track='true']").forEach((form) => {
    form.querySelectorAll("input[name], select[name], textarea[name]").forEach((field) => {
      field.dataset.initialValue = normalizeValue(field);
      field.classList.remove("dirty-field");
    });
    form.classList.remove("dirty-row");
  });
}

function updateDirtyState(form) {
  let isDirty = false;
  form.querySelectorAll("input[name], select[name], textarea[name]").forEach((field) => {
    const changed = normalizeValue(field) !== field.dataset.initialValue;
    field.classList.toggle("dirty-field", changed);
    isDirty = isDirty || changed;
  });
  form.classList.toggle("dirty-row", isDirty);
}

document.addEventListener("DOMContentLoaded", () => initializeDirtyTracking());

document.addEventListener("input", (event) => {
  if (event.target.matches("[data-exclusive-amount]") && event.target.value !== "") {
    const form = event.target.closest("form");
    const counterpart = event.target.dataset.exclusiveAmount === "total" ? "payment" : "total";
    const other = form?.querySelector(`[data-exclusive-amount='${counterpart}']`);
    if (other) other.value = "";
  }
  const form = event.target.closest(".row-form, .dirty-track-form, form[data-dirty-track='true']");
  if (form) updateDirtyState(form);
});

document.addEventListener("change", (event) => {
  const form = event.target.closest(".row-form, .dirty-track-form, form[data-dirty-track='true']");
  if (form) updateDirtyState(form);
});

function scrollChartsToEnd(root = document) {
  root.querySelectorAll("[data-scroll-end='true']").forEach((chart) => {
    requestAnimationFrame(() => {
      chart.scrollLeft = chart.scrollWidth;
    });
  });
}

document.addEventListener("DOMContentLoaded", () => scrollChartsToEnd());

document.body.addEventListener("htmx:afterSwap", (event) => {
  initializeDirtyTracking(event.detail.target);
  scrollChartsToEnd(event.detail.target);
});
