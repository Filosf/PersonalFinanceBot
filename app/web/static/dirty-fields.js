function normalizeValue(field) {
  if (field.type === "number" && field.value !== "") {
    return Number(field.value).toFixed(2);
  }
  return field.value;
}

function initializeDirtyTracking(root = document) {
  root.querySelectorAll(".row-form").forEach((form) => {
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
  const form = event.target.closest(".row-form");
  if (form) updateDirtyState(form);
});

document.addEventListener("change", (event) => {
  const form = event.target.closest(".row-form");
  if (form) updateDirtyState(form);
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  initializeDirtyTracking(event.detail.target);
});
