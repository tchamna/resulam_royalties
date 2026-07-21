// Custom client-side behaviors for the Resulam dashboards.
//
// Smooth-scroll to the tab content on small screens even when the user taps
// the already-active tab (Dash callbacks don't fire if active_tab doesn't change).
window.dash_clientside = Object.assign({}, window.dash_clientside, {
  url_sync: {
    filters_to_search: function (
      year,
      lang,
      category,
      book,
      author,
      bookType,
      tab,
      chart,
      currentSearch
    ) {
      var params = new URLSearchParams();

      if (year && year !== "lifetime") {
        params.set("year", String(year));
      }
      if (lang && lang !== "all") {
        params.set("lang", lang);
      }
      if (category && category !== "all") {
        params.set("category", category);
      }
      if (book && book !== "all") {
        params.set("book", book);
      }
      if (author && author !== "all") {
        params.set("author", author);
      }
      if (bookType && bookType !== "all") {
        params.set("type", bookType);
      }
      if (tab && tab !== "purchase") {
        params.set("tab", tab);
      }
      if (chart && chart !== "all_stacked") {
        params.set("chart", chart);
      }

      var query = params.toString();
      var newSearch = query ? "?" + query : "";
      var normalizedCurrent = currentSearch || "";

      if (newSearch === normalizedCurrent) {
        return window.dash_clientside.no_update;
      }
      return newSearch;
    },
  },
});

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

  // Animate KPI metric values when they update (adds a subtle "live" feel).
  function animateMetric(node) {
    if (!node) return;

    node.classList.remove("metric-pop");
    // Force reflow so the animation restarts
    void node.offsetWidth;
    node.classList.add("metric-pop");

    var card = node.closest ? node.closest(".card") : null;
    if (card) {
      card.classList.remove("card-pop");
      void card.offsetWidth;
      card.classList.add("card-pop");
    }
  }

  function attachMetricObserver(node) {
    if (!node || !node.dataset) return;
    if (node.dataset.metricObserved === "1") return;
    node.dataset.metricObserved = "1";

    var lastText = (node.textContent || "").trim();
    try {
      var observer = new MutationObserver(function () {
        var nextText = (node.textContent || "").trim();
        if (nextText && nextText !== lastText) {
          lastText = nextText;
          animateMetric(node);
        }
      });
      observer.observe(node, { childList: true, characterData: true, subtree: true });
    } catch (e) {
      // Ignore if MutationObserver not available
    }
  }

  function scanAndAttachMetricObservers(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll ? scope.querySelectorAll('[id^="metric-"]') : [];
    for (var i = 0; i < nodes.length; i++) {
      attachMetricObserver(nodes[i]);
    }
  }

  function initMetricAnimations() {
    scanAndAttachMetricObservers(document);

    // Re-scan when Dash swaps out tab content.
    try {
      var scheduled = false;
      var rootObserver = new MutationObserver(function () {
        if (scheduled) return;
        scheduled = true;
        window.requestAnimationFrame(function () {
          scheduled = false;
          scanAndAttachMetricObservers(document);
        });
      });
      rootObserver.observe(document.body, { childList: true, subtree: true });
    } catch (e) {
      // Ignore if MutationObserver not available
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMetricAnimations);
  } else {
    initMetricAnimations();
  }
})();
