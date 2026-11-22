// Petites courbes de la rubrique sécurité. Chaque <div class="courbe"> porte ses données
// dans data-courbe : { annees: [...], series: [{ nom, valeurs: [...] }] }. Une valeur null
// coupe la courbe (ressenti : rien entre les deux enquêtes).
"use strict";

(function () {
  if (typeof echarts === "undefined") return;
  const blocs = [...document.querySelectorAll(".courbe[data-courbe]")];
  if (!blocs.length) return;
  const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
  const graphiques = [];

  function couleurs() {
    const s = getComputedStyle(document.documentElement);
    const v = (nom) => s.getPropertyValue(nom).trim();
    return {
      texte: v("--texte"), texte3: v("--texte-3"), grille: v("--grille"),
      surface: v("--surface"), bordure: v("--bordure"),
      series: [v("--serie"), v("--femmes"), v("--texte-2")],
    };
  }

  function dessiner(bloc, graphique) {
    const c = couleurs();
    const d = JSON.parse(bloc.dataset.courbe);
    const pourcentage = bloc.dataset.unite === "pourcentage";
    const format = (x) => (x === null || x === undefined ? "—" : nombre.format(x) + (pourcentage ? " %" : ""));
    const plusieurs = d.series.length > 1;
    graphique.setOption({
      animation: false,
      color: c.series,
      grid: { left: 4, right: 12, top: plusieurs ? 64 : 12, bottom: 4, containLabel: true },
      legend: plusieurs ? { top: 0, left: 0, textStyle: { color: c.texte, fontSize: 12 } } : undefined,
      tooltip: {
        trigger: "axis", backgroundColor: c.surface, borderColor: c.bordure,
        textStyle: { color: c.texte, fontSize: 13 }, valueFormatter: format,
      },
      xAxis: {
        type: "category", data: d.annees, boundaryGap: false,
        axisLine: { lineStyle: { color: c.bordure } }, axisTick: { show: false },
        axisLabel: { color: c.texte3 },
      },
      yAxis: {
        type: "value", scale: !pourcentage, min: pourcentage ? 0 : undefined,
        splitLine: { lineStyle: { color: c.grille } },
        axisLabel: { color: c.texte3, formatter: (x) => nombre.format(x) },
      },
      series: d.series.map((s) => ({
        name: s.nom, type: "line", data: s.valeurs, connectNulls: false,
        symbol: "circle", symbolSize: 6, lineStyle: { width: 2 },
      })),
    }, true);
  }

  for (const bloc of blocs) {
    const graphique = echarts.init(bloc, null, { renderer: "svg" });
    graphiques.push([bloc, graphique]);
    dessiner(bloc, graphique);
  }
  window.addEventListener("resize", () => graphiques.forEach(([, g]) => g.resize()));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () =>
    graphiques.forEach(([b, g]) => dessiner(b, g)));
})();
