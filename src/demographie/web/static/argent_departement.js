// Dépense locale par habitant d'un département et de la France, par année.
// Données dans <script id="donnees-local">.
"use strict";

(function () {
  const source = document.getElementById("donnees-local");
  const element = document.getElementById("historique-local");
  if (!source || !element || typeof echarts === "undefined") return;
  const h = JSON.parse(source.textContent).historique;
  if (!h) return;
  const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
  const format = (x) => (x === null || x === undefined ? "—" : nombre.format(x) + " €");
  const g = echarts.init(element, null, { renderer: "svg" });

  function dessiner() {
    const s = getComputedStyle(document.documentElement);
    const v = (nom) => s.getPropertyValue(nom).trim();
    const ligne = (nom, donnees, couleur) => ({
      name: nom, type: "line", data: donnees, symbol: "circle", symbolSize: 5,
      connectNulls: true, lineStyle: { width: 2, color: couleur }, itemStyle: { color: couleur },
    });
    g.setOption({
      animation: false,
      grid: { left: 4, right: 12, top: 12, bottom: 4, containLabel: true },
      tooltip: {
        trigger: "axis", backgroundColor: v("--surface"), borderColor: v("--bordure"),
        textStyle: { color: v("--texte"), fontSize: 13 }, valueFormatter: format,
      },
      xAxis: {
        type: "category", data: h.annees,
        axisLine: { lineStyle: { color: v("--bordure") } }, axisTick: { show: false },
        axisLabel: { color: v("--texte-3") },
      },
      yAxis: {
        type: "value", scale: true, splitLine: { lineStyle: { color: v("--grille") } },
        axisLabel: { color: v("--texte-3"), formatter: format },
      },
      series: [ligne("Ici", h.ici, v("--serie")), ligne("France", h.france, v("--femmes"))],
    }, true);
  }

  dessiner();
  window.addEventListener("resize", () => g.resize());
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", dessiner);
})();
