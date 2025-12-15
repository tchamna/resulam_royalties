// Custom client-side behaviors for the Resulam dashboards.
//
// Smooth-scroll to the tab content on small screens even when the user taps
// the already-active tab (Dash callbacks don't fire if active_tab doesn't change).
(function () {
  function isSmallScreen() {
    try {
      return window.matchMedia("(max-width: 768px)").matches;
    } catch (e) {
      return false;
    }
  }

  function scrollToTabContentAnchor() {
    var anchor = document.getElementById("tab-view-anchor");
    if (!anchor) return;
    try {
      anchor.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      // Fallback for older browsers
      anchor.scrollIntoView(true);
    }
  }

  document.addEventListener(
    "click",
    function (ev) {
      if (!isSmallScreen()) return;

      var link = ev.target && ev.target.closest ? ev.target.closest(".nav-link") : null;
      if (!link) return;

      // Only react to clicks within the dashboard tabs component.
      if (!link.closest || !link.closest("#dashboard-tabs")) return;

      // Defer slightly to let Dash update the view when switching tabs.
      window.setTimeout(scrollToTabContentAnchor, 0);
    },
    true
  );
})();

