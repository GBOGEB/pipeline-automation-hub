/* Render committed gg_MATH bridge figure JSON with the locally vendored Plotly bundle.
   No CDN: if assets/js/plotly.min.js is absent the page keeps its evidence tables. */
(function () {
  "use strict";
  var source = document.getElementById("ggmath-figures");
  if (!source) { return; }
  var doc = JSON.parse(source.textContent);
  var status = document.getElementById("ggmath-plotly-status");

  function render() {
    doc.figures.forEach(function (entry) {
      var node = document.querySelector('.ggmath-figure[data-figure-id="' + entry.id + '"]');
      if (node) {
        node.style.minHeight = "360px";
        window.Plotly.newPlot(node, entry.figure.data, entry.figure.layout,
          { displaylogo: false, responsive: true });
      }
    });
    if (status) { status.textContent = "Charts rendered from the committed figure JSON with the offline Plotly bundle."; }
  }

  if (window.Plotly) { render(); return; }
  var script = document.createElement("script");
  script.src = source.getAttribute("data-plotlyjs");
  script.onload = render;
  script.onerror = function () {
    if (status) { status.textContent = "Plotly bundle not vendored in this build; the tables are the evidence."; }
  };
  document.head.appendChild(script);
}());
