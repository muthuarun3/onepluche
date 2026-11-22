// Graphiques de « Où va l'argent public ? ». Données dans <script id="donnees-argent">.
"use strict";

(function () {
  const source = document.getElementById("donnees-argent");
  if (!source || typeof echarts === "undefined") return;
  const h = JSON.parse(source.textContent).historique;
  if (!h) return;
  const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
  const format = (x, suffixe) => (x === null || x === undefined ? "—" : nombre.format(x) + suffixe);

  function couleurs() {
    const s = getComputedStyle(document.documentElement);
    const v = (nom) => s.getPropertyValue(nom).trim();
    return {
      texte: v("--texte"), texte3: v("--texte-3"), grille: v("--grille"),
      surface: v("--surface"), bordure: v("--bordure"), serie: v("--serie"), femmes: v("--femmes"),
    };
  }

  function base(c, suffixe) {
    return {
      animation: false,
      grid: { left: 4, right: 12, top: 12, bottom: 4, containLabel: true },
      tooltip: {
        trigger: "axis", backgroundColor: c.surface, borderColor: c.bordure,
        textStyle: { color: c.texte, fontSize: 13 }, valueFormatter: (x) => format(x, suffixe),
      },
      xAxis: {
        type: "category", data: h.annees,
        axisLine: { lineStyle: { color: c.bordure } }, axisTick: { show: false },
        axisLabel: { color: c.texte3 },
      },
      yAxis: {
        type: "value", splitLine: { lineStyle: { color: c.grille } },
        axisLabel: { color: c.texte3, formatter: (x) => nombre.format(x) + suffixe },
      },
    };
  }

  // Dette (courbe) et solde (barres) en % du PIB, sur le même axe.
  function deficitDette(g) {
    const c = couleurs();
    g.setOption({
      ...base(c, " %"),
      series: [
        { name: "Dette", type: "line", data: h.dette_pib, symbol: "none",
          lineStyle: { width: 2, color: c.serie }, itemStyle: { color: c.serie } },
        { name: "Solde public", type: "bar", data: h.solde_pib, itemStyle: { color: c.femmes } },
      ],
    }, true);
  }

  function choixEuros() {
    const coche = document.querySelector('input[name="euros"]:checked');
    return coche && h.dette_constants ? coche.value : "courants";
  }

  function detteEuros(g) {
    const c = couleurs();
    const constants = choixEuros() === "constants";
    g.setOption({
      ...base(c, " Md€"),
      series: [{
        name: constants ? `Dette (euros de ${h.base_prix})` : "Dette (euros de l'époque)",
        type: "line", data: constants ? h.dette_constants : h.dette_courants, symbol: "none",
        connectNulls: false, areaStyle: { color: c.serie, opacity: 0.15 },
        lineStyle: { width: 2, color: c.serie }, itemStyle: { color: c.serie },
      }],
    }, true);
  }

  const graphiques = [];
  for (const [id, dessiner] of [["deficit-dette", deficitDette], ["dette-euros", detteEuros]]) {
    const element = document.getElementById(id);
    if (!element) continue;
    const g = echarts.init(element, null, { renderer: "svg" });
    graphiques.push({ g, dessiner: () => dessiner(g) });
  }
  const toutDessiner = () => graphiques.forEach((x) => x.dessiner());
  toutDessiner();
  document.querySelectorAll('input[name="euros"]').forEach((i) => i.addEventListener("change", toutDessiner));
  window.addEventListener("resize", () => graphiques.forEach((x) => x.g.resize()));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", toutDessiner);
})();
