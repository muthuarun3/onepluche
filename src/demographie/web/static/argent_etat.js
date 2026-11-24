// Graphiques du budget de l'État. Données dans <script id="donnees-etat">.
"use strict";

(function () {
  const source = document.getElementById("donnees-etat");
  if (!source || typeof echarts === "undefined") return;
  const donnees = JSON.parse(source.textContent);
  const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
  const md = (x) => (x === null || x === undefined ? "—" : `${nombre.format(x)} Md€`);

  function couleurs() {
    const s = getComputedStyle(document.documentElement);
    const v = (nom) => s.getPropertyValue(nom).trim();
    return {
      texte: v("--texte"), texte2: v("--texte-2"), texte3: v("--texte-3"), grille: v("--grille"),
      surface: v("--surface"), bordure: v("--bordure"), serie: v("--serie"), femmes: v("--femmes"),
    };
  }
  const infobulle = (c) => ({
    backgroundColor: c.surface, borderColor: c.bordure, textStyle: { color: c.texte, fontSize: 13 },
    valueFormatter: md,
  });

  // Solde cumulé : une courbe par année, la plus récente en couleur, les autres en gris.
  function solde(g) {
    const c = couleurs();
    const d = donnees.solde;
    const n = d.series.length;
    g.setOption({
      animation: false,
      grid: { left: 4, right: 12, top: 36, bottom: 4, containLabel: true },
      legend: { top: 0, left: 0, textStyle: { color: c.texte, fontSize: 12 } },
      tooltip: { trigger: "axis", ...infobulle(c) },
      xAxis: {
        type: "category", data: d.mois, boundaryGap: false,
        axisLine: { lineStyle: { color: c.bordure } }, axisTick: { show: false },
        axisLabel: { color: c.texte3 },
      },
      yAxis: {
        type: "value", splitLine: { lineStyle: { color: c.grille } },
        axisLabel: { color: c.texte3, formatter: (x) => nombre.format(x) },
      },
      series: d.series.map((s, i) => {
        const couleur = i === n - 1 ? c.serie : (i === n - 2 ? c.texte2 : c.texte3);
        return {
          name: s.nom, type: "line", data: s.valeurs, symbol: "circle", symbolSize: 5,
          lineStyle: { width: i === n - 1 ? 3 : 1.5, color: couleur, type: i === n - 1 ? "solid" : "dashed" },
          itemStyle: { color: couleur },
        };
      }),
    }, true);
  }

  // Missions : barres horizontales, voté (clair) et dépensé (plein), la plus grosse en haut.
  function missions(g) {
    const c = couleurs();
    const d = [...donnees.missions].reverse();
    g.setOption({
      animation: false,
      grid: { left: 4, right: 16, top: 8, bottom: 4, containLabel: true },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, ...infobulle(c) },
      xAxis: {
        type: "value", position: "top", splitLine: { lineStyle: { color: c.grille } },
        axisLabel: { color: c.texte3, formatter: (x) => nombre.format(x) },
      },
      yAxis: {
        type: "category", data: d.map((x) => x.libelle),
        axisTick: { show: false }, axisLine: { lineStyle: { color: c.bordure } },
        axisLabel: { color: c.texte2, width: window.innerWidth < 600 ? 110 : 210, overflow: "truncate", fontSize: 11 },
      },
      series: [
        { name: "Voté", type: "bar", data: d.map((x) => x.vote), barGap: "-100%", barWidth: "70%",
          itemStyle: { color: c.serie, opacity: 0.25 } },
        { name: "Dépensé", type: "bar", data: d.map((x) => x.consomme), barWidth: "40%",
          itemStyle: { color: c.serie } },
      ],
    }, true);
  }

  const graphiques = [];
  for (const [id, cle, dessiner] of [["solde-etat", "solde", solde], ["missions-etat", "missions", missions]]) {
    const element = document.getElementById(id);
    if (!element || !donnees[cle]) continue;
    const g = echarts.init(element, null, { renderer: "svg" });
    graphiques.push({ g, dessiner: () => dessiner(g) });
  }
  const tout = () => graphiques.forEach((x) => x.dessiner());
  tout();
  window.addEventListener("resize", () => graphiques.forEach((x) => x.g.resize()));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", tout);
})();
