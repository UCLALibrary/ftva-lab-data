// enables tooltips
// see @https://getbootstrap.com/docs/5.2/components/tooltips/
const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))

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

// Utility function: Set or update a hidden input in a form
function setOrUpdate(form, name, value) {
  let el = form.querySelector(`input[name="${name}"]`);
  if (!el) {
    el = document.createElement("input");
    el.type = "hidden";
    el.name = name;
    form.appendChild(el);
  }
  el.value = value || "";
}

document.addEventListener("htmx:afterSwap", function (e) {
  const selectAll = document.getElementById("select-all-checkbox");
  if (selectAll) {
    selectAll.addEventListener("change", function () {
      const checkboxes = document.querySelectorAll(".row-checkbox");
      checkboxes.forEach((cb) => (cb.checked = selectAll.checked));
    });
  }
});

document.addEventListener("DOMContentLoaded", function () {
  const searchForm = document.querySelector('form[hx-get]');
  if (searchForm) {
    searchForm.addEventListener('submit', function (e) {
      e.preventDefault(); // Prevent form submission on Enter
    });
  }
});


document.addEventListener("DOMContentLoaded", function () {
  assignedUsersForm = document.getElementById("assigned-users-form");
  if (assignedUsersForm) {
    assignedUsersForm.addEventListener("submit", function () {
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

      setOrUpdate(this, "search", search ? search.value : "");
      setOrUpdate(
        this,
        "search_column",
        search_column ? search_column.value : ""
      );
      setOrUpdate(this, "page", page || "");
    });
  };
});
// Sync export form fields with search inputs
// This is necessary because the export form is a separate form and does not
// automatically get updated by HTMX when the search form changes.
function syncExportFormFields() {
  const searchInput = document.querySelector('input[name="search"]');
  const searchColumn = document.querySelector('select[name="search_column"]');
  const exportForm = document.querySelector('form[action$="export_search_results/"]');
  if (!exportForm) return;

  setOrUpdate(exportForm, "search", searchInput ? searchInput.value : "");
  setOrUpdate(exportForm, "search_column", searchColumn ? searchColumn.value : "");
}

// Sync on page load
document.addEventListener("DOMContentLoaded", syncExportFormFields);

// Sync after any HTMX swap (table/search form updates)
document.addEventListener("htmx:afterSwap", syncExportFormFields);

// Sync on search form input changes
document.addEventListener("input", function (e) {
  if (
    e.target.matches('input[name="search"]') ||
    e.target.matches('select[name="search_column"]')
  ) {
    syncExportFormFields();
  }
});

// Handle export button click - add spinner and submit export form
document.addEventListener("DOMContentLoaded", function () {
  const exportBtn = document.getElementById("export-button");
  const exportForm = document.getElementById("export-form");
  const spinner = document.getElementById("export-spinner");
  if (exportBtn && exportForm && spinner) {
    exportBtn.addEventListener("click", function () {
      spinner.style.display = "block";
      exportForm.submit();
      // Hide spinner after a constant 10s delay
      setTimeout(() => {
      spinner.style.display = "none";
      }, 10000);
    });
  }
});
