function toggleAdvancedFields(el) {
  const advancedFields = document.getElementById("advanced-fields");
  const isHidden = advancedFields.hidden = !advancedFields.hidden;
  el.textContent = isHidden ? "Show Advanced Fields" : "Hide Advanced Fields";
}

function clearSearchInput() {
  let input = document.getElementById('search-input');
  input.value = '';
  input.focus();
  // make sure `hx-get` is triggered after clearing input
  // as opposed to `keyup` event, `clear` triggers immediately
  htmx.trigger(input, 'clear');
}
