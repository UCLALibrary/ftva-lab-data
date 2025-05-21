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
