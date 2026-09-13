// Applied before the app renders to avoid a light/dark flash.
// Kept in an external file so the production CSP can stay strict.
try {
  var t = localStorage.getItem("opendocket_theme");
  if (t === "dark") {
    document.documentElement.dataset.theme = "dark";
  }
} catch (e) {}
