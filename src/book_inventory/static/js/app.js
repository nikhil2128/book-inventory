// Loading states for the server-rendered pages: a spinner on the submit button while a form is
// being processed, and a progress bar at the top while navigating between pages.
(function () {
  "use strict";

  var bar = document.createElement("div");
  bar.className = "progress-bar";
  bar.setAttribute("role", "progressbar");
  bar.setAttribute("aria-label", "Loading page");
  bar.hidden = true;
  document.body.prepend(bar);

  function reset() {
    bar.hidden = true;
    document.documentElement.classList.remove("is-loading");
    document.querySelectorAll("button.loading").forEach(function (button) {
      button.classList.remove("loading");
      button.disabled = false;
      button.removeAttribute("aria-busy");
    });
  }

  function startNavigation() {
    bar.hidden = false;
    document.documentElement.classList.add("is-loading");
  }

  document.addEventListener("submit", function (event) {
    // A handler that cancelled the submit (e.g. the "Cancel this booking?" prompt) means no
    // request is going out, so there is nothing to show.
    if (event.defaultPrevented) return;

    var form = event.target;
    var button = event.submitter || form.querySelector("button[type=submit]");
    startNavigation();
    if (!button) return;
    button.classList.add("loading");
    button.setAttribute("aria-busy", "true");
    // Disable after the browser has collected the form data and sent the submit.
    setTimeout(function () {
      button.disabled = true;
    }, 0);
  });

  document.addEventListener("click", function (event) {
    var link = event.target.closest && event.target.closest("a[href]");
    if (!link || event.defaultPrevented) return;
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (link.target && link.target !== "_self") return;
    if (link.hasAttribute("download")) return;

    var url = new URL(link.href, window.location.href);
    var samePageAnchor =
      url.pathname === window.location.pathname &&
      url.search === window.location.search &&
      url.hash !== "";
    if (url.origin !== window.location.origin || samePageAnchor) return;
    startNavigation();
  });

  // Coming back via the browser's back/forward cache would otherwise show a stuck spinner.
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) reset();
  });
})();
