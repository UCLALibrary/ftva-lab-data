function toggleAdvancedFields(el) {
  const advancedFields = document.getElementById("advanced-fields");
  const isHidden = (advancedFields.hidden = !advancedFields.hidden);
  el.textContent = isHidden ? "Show Advanced Fields" : "Hide Advanced Fields";
}

function clearSearchInput() {
  let input = document.getElementById("search-input");
  input.value = "";
  input.focus();
  // make sure `hx-get` is triggered after clearing input
  // as opposed to `keyup` event, `clear` triggers immediately
  htmx.trigger(input, "clear");
}

document.getElementById("assigned-users-form").onsubmit = function (e) {
  const checked = Array.from(
    document.querySelectorAll(".row-checkbox:checked")
  ).map((cb) => cb.value);
  let input = this.querySelector('input[name="ids"]');
  if (!input) {
    input = document.createElement("input");
    input.type = "hidden";
    input.name = "ids";
    this.appendChild(input);
  }
  input.value = checked.join(",");

  // Add current filters as hidden inputs
  const search = document.querySelector('input[name="search"]');
  const search_column = document.querySelector('select[name="search_column"]');
  const page = document.querySelector("#current-page")?.value;

  function setOrUpdate(name, value) {
    let el = this.querySelector(`input[name="${name}"]`);
    if (!el) {
      el = document.createElement("input");
      el.type = "hidden";
      el.name = name;
      this.appendChild(el);
    }
    el.value = value || "";
  }
  setOrUpdate.call(this, "search", search ? search.value : "");
  setOrUpdate.call(
    this,
    "search_column",
    search_column ? search_column.value : ""
  );
  setOrUpdate.call(this, "page", page || "");
};

document.addEventListener("htmx:afterSwap", function (e) {
  const selectAll = document.getElementById("select-all-checkbox");
  if (selectAll) {
    selectAll.addEventListener("change", function () {
      const checkboxes = document.querySelectorAll(".row-checkbox");
      checkboxes.forEach((cb) => (cb.checked = selectAll.checked));
    });
  }
});
