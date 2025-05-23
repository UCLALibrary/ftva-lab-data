let toggleAdvancedFields = document.getElementById("toggle-advanced-fields");
if (toggleAdvancedFields) {
  toggleAdvancedFields.addEventListener("click", function () {
    const advancedFields = document.getElementById("advanced-fields");
    if (advancedFields.style.display === "none") {
      advancedFields.style.display = "block";
      this.textContent = "Hide Advanced Fields";
    } else {
      advancedFields.style.display = "none";
      this.textContent = "Show Advanced Fields";
    }
  });
}

function clearSearchInput() {
  let input = document.getElementById('search-input');
  input.value = '';
  input.focus();
  // make sure `hx-get` is triggered after clearing input
  // as opposed to `keyup` event, `clear` triggers immediately
  htmx.trigger(input, 'clear');
}
