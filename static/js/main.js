// enables tooltips
// see @https://getbootstrap.com/docs/5.2/components/tooltips/
const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

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

/** 
 * Handle the click event for the export button by triggering
 * an asynchronous fetch of the `export_search_results` endpoint.
 * Spinner styling is applied when the request is initiated,
 * then removed when the download completes via JavaScript,
 * which creates a phony anchor tag, and adds the spreadsheet data
 * to its attributes, then triggers download and removes the tag.
 * 
 * @param {HTMLButtonElement} button
 * @param {Event} event
 */
async function handleExportSearchResults(button, event) {
  event.preventDefault();

  // style button
  button.disabled = true;
  // display spinner
  const spinner = document.getElementById("export-spinner");
  spinner.classList.add("spinner-border");

  // get table filter form data
  const form = document.getElementById("table-filters-form");
  const formData = new FormData(form);
  const filterParams = new URLSearchParams(formData);

  try {
    // filter params have to be encoded in the query string,
    // because the endpoint is a `GET` endpoint
    const response = await fetch(`/export_search_results/?${filterParams.toString()}`);

    // handle bad responses by displaying browser alert
    if (response.status != 200) {
      throw Error(`An error occured while exporting data.\n\n${response.statusText} (${response.status})`)
    }

    const disposition = response.headers.get("Content-Disposition");
    // this is a sort of hacky way to get the filename that is encoded
    // in the response `Content-Disposition` returned by the Django view
    if (disposition && disposition.includes("filename=")) {
      filename = disposition.split("filename=")[1]
    }

    // use `createObjectURL` to encode spreadsheet data in URL
    // then download via temporary anchor tag
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    alert(error)
  } finally {
    // remove spinner and return button to functional state
    spinner.classList.remove("spinner-border");
    button.disabled = false;
  }
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


// Set Carrier Location page
// Support keyboard and mouse interaction, and form validation
document.addEventListener("DOMContentLoaded", function () {
  let carrierSelected = false;
  const carrierInput = document.getElementById("carrier");
  const suggestions = document.getElementById("carrier-suggestions");
  const form = carrierInput?.closest("form");
  let activeIndex = -1;

  function updateHighlight() {
    const items = suggestions.querySelectorAll(".carrier-suggestion");
    items.forEach((item, index) => {
      item.classList.toggle("active", index === activeIndex);
    });
  }
  function disableCarrierInputTrigger() {
    // Remove HTMX trigger so Enter doesn't fetch suggestions again
    carrierInput.removeAttribute("hx-get");
    carrierInput.removeAttribute("hx-trigger");
    carrierInput.removeAttribute("hx-target");
    carrierInput.removeAttribute("hx-params");
  }

  function enableCarrierInputTrigger() {
    // Resume HTMX operations
    // Restore values to defaults from template, plus saved hx-get URL
    carrierInput.setAttribute("hx-get", carrierInput.dataset.suggestionsUrl);
    carrierInput.setAttribute("hx-trigger", "keyup changed delay:300ms");
    carrierInput.setAttribute("hx-target", "#carrier-suggestions");
    carrierInput.setAttribute("hx-params", "*");
  }

  // Save the suggestions URL for re-enabling
  carrierInput.dataset.suggestionsUrl = carrierInput.getAttribute("hx-get");

  // Reset flag and highlight when user types, and re-enable HTMX input
  carrierInput.addEventListener("input", function () {
    carrierSelected = false;
    activeIndex = -1;
    updateHighlight();
    enableCarrierInputTrigger();
  });

  // Keyboard navigation
  carrierInput.addEventListener("keydown", function (e) {
    const items = suggestions.querySelectorAll(".carrier-suggestion");
    // if no suggestions, do nothing
    if (!items.length) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % items.length;
      updateHighlight();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + items.length) % items.length;
      updateHighlight();
    } else if (e.key === "Enter") {
      // Check that we've selected a valid item
      if (activeIndex >= 0 && activeIndex < items.length) {
        e.preventDefault();
        e.stopImmediatePropagation(); // Prevent HTMX from seeing this event
        carrierInput.value = items[activeIndex].textContent;
        carrierSelected = true;
        suggestions.innerHTML = "";
        disableCarrierInputTrigger();
        return false; // Stop further event handling
      }
    }
  });

  // Set flag when a suggestion is clicked
  suggestions.addEventListener("click", function (e) {
    if (e.target.classList.contains("carrier-suggestion")) {
      carrierInput.value = e.target.textContent;
      carrierSelected = true;
      suggestions.innerHTML = "";
      disableCarrierInputTrigger();
    }
  });

  // Mouse hover highlights
  suggestions.addEventListener("mouseover", function (e) {
    const items = Array.from(suggestions.querySelectorAll(".carrier-suggestion"));
    const idx = items.indexOf(e.target);
    if (idx !== -1) {
      activeIndex = idx;
      updateHighlight();
    }
  });

  // Prevent form submit if not selected from suggestions
  if (form) {
    form.addEventListener("submit", function (e) {
      if (!carrierSelected) {
        e.preventDefault();
        alert("Please select a carrier from the suggestions.");
        carrierInput.focus();
      }
    });
  }
});