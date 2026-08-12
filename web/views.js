window.WorkbenchViews = {
  show(targetName) {
    document
      .querySelectorAll(".view-tab")
      .forEach((button) =>
        button.classList.toggle(
          "active",
          button.dataset.viewTarget === targetName,
        ),
      );
    document
      .querySelectorAll(".result-view")
      .forEach((view) =>
        view.classList.toggle("active", view.dataset.resultView === targetName),
      );
    const details = document.getElementById("pinDetailsSection");
    if (targetName === "pinDetailsSection" && details) details.open = true;
  },
};
