// Graphiques de « Quel avenir pour les Français ? ». Données dans <script id="donnees-avenir">.
"use strict";

(function () {
  const source = document.getElementById("donnees-avenir");
  if (!source || typeof echarts === "undefined") return;
  const donnees = JSON.parse(source.textContent);
  const nombre = new Intl.NumberFormat("fr-FR");
  const CENTRAL = "INSEE_CENTRAL", BASSE = "INSEE_POP_BASSE", HAUTE = "INSEE_POP_HAUTE";

  function couleurs() {
    const s = getComputedStyle(document.documentElement);
    const v = (nom) => s.getPropertyValue(nom).trim();
    return {
      texte: v("--texte"), texte2: v("--texte-2"), texte3: v("--texte-3"),
      grille: v("--grille"), surface: v("--surface"), bordure: v("--bordure"),
      hommes: v("--hommes"), femmes: v("--femmes"), serie: v("--serie"),
    };
  }

  function infobulle(c) {
    return { backgroundColor: c.surface, borderColor: c.bordure, textStyle: { color: c.texte, fontSize: 13 } };
  }

  // Courbe du scénario central et bande de la population basse à la population haute.
  // `series` : { scénario: [[année, valeur], ...] }.
  function scenarios(graphique, series, unite) {
    const c = couleurs();
    const annees = [...new Set(Object.values(series).flat().map((p) => p[0]))].sort((a, b) => a - b);
    const valeur = (s) => {
      const parAnnee = new Map(series[s] || []);
      return annees.map((a) => (parAnnee.has(a) ? parAnnee.get(a) : null));
    };
    const central = valeur(CENTRAL), basse = valeur(BASSE), haute = valeur(HAUTE);
    const ecart = haute.map((h, i) => (h === null || basse[i] === null ? null : h - basse[i]));
    const format = (v) => (unite === "millions" ? `${(v / 1e6).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} M` : nombre.format(v));
    graphique.setOption({
      animation: false,
      grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
      tooltip: {
        trigger: "axis", ...infobulle(c),
        formatter: (p) => {
          const i = p[0].dataIndex;
          let texte = `<b>1er janvier ${annees[i]}</b>`;
          if (central[i] !== null) texte += `<br>Scénario central : ${nombre.format(central[i])}`;
          if (basse[i] !== null && haute[i] !== null) {
            texte += `<br>Fourchette : ${nombre.format(basse[i])} à ${nombre.format(haute[i])}`;
          }
          return texte;
        },
      },
      xAxis: {
        type: "category", data: annees, boundaryGap: false,
        axisLabel: { color: c.texte3 }, axisLine: { lineStyle: { color: c.bordure } },
      },
      yAxis: {
        type: "value", scale: true,
        axisLabel: { color: c.texte3, formatter: format },
        splitLine: { lineStyle: { color: c.grille } },
      },
      series: [
        { name: "Bas", type: "line", data: basse, stack: "fourchette", symbol: "none",
          lineStyle: { opacity: 0 }, silent: true },
        { name: "Fourchette", type: "line", data: ecart, stack: "fourchette", symbol: "none",
          lineStyle: { opacity: 0 }, areaStyle: { color: c.serie, opacity: 0.25 }, silent: true },
        { name: "Scénario central", type: "line", data: central, showSymbol: false, symbolSize: 8,
          lineStyle: { width: 2, color: c.serie }, itemStyle: { color: c.serie } },
      ],
    }, true);
  }

  function libelleAge(t) {
    return t.age_max === null ? `${t.age_min} ans et plus` : `${t.age_min} à ${t.age_max} ans`;
  }

  function tranches(annee) {
    const parAge = new Map();
    for (const l of donnees.pyramide) {
      if (l.annee !== annee) continue;
      if (!parAge.has(l.age_min)) parAge.set(l.age_min, { age_min: l.age_min, age_max: l.age_max, H: 0, F: 0 });
      parAge.get(l.age_min)[l.sexe] = l.valeur;
    }
    return [...parAge.values()].sort((a, b) => a.age_min - b.age_min);
  }

  // Pyramide de l'année choisie, avec le contour de l'année de départ.
  function pyramide(graphique, annee) {
    const c = couleurs();
    const t = tranches(annee), depart = tranches(donnees.depart);
    const max = Math.max(...t.concat(depart).map((x) => Math.max(x.H, x.F)));
    const contour = { type: "line", step: "middle", symbol: "none", silent: true,
      lineStyle: { color: c.texte3, width: 1.5 } };
    graphique.setOption({
      animation: false,
      grid: { left: 8, right: 8, top: 8, bottom: 24, containLabel: true },
      tooltip: {
        trigger: "axis", axisPointer: { type: "shadow" }, ...infobulle(c),
        formatter: (p) => {
          const x = t[p[0].dataIndex], y = depart[p[0].dataIndex] || { H: 0, F: 0 };
          return `<b>${libelleAge(x)}</b><br>Hommes : ${nombre.format(x.H)} (${nombre.format(y.H)} en ${donnees.depart})`
            + `<br>Femmes : ${nombre.format(x.F)} (${nombre.format(y.F)} en ${donnees.depart})`;
        },
      },
      xAxis: {
        type: "value", min: -max, max: max,
        axisLabel: { color: c.texte3, showMinLabel: false, showMaxLabel: false, formatter: (v) => nombre.format(Math.abs(v)) },
        splitLine: { lineStyle: { color: c.grille } },
      },
      yAxis: {
        type: "category", data: t.map((x) => (x.age_max === null ? `${x.age_min}+` : `${x.age_min}-${x.age_max}`)),
        axisTick: { show: false }, axisLine: { lineStyle: { color: c.bordure } }, axisLabel: { color: c.texte2 },
      },
      series: [
        { name: "Hommes", type: "bar", stack: "p", barCategoryGap: "12%",
          data: t.map((x) => -x.H), itemStyle: { color: c.hommes, borderRadius: [4, 0, 0, 4] } },
        { name: "Femmes", type: "bar", stack: "p",
          data: t.map((x) => x.F), itemStyle: { color: c.femmes, borderRadius: [0, 4, 4, 0] } },
        { name: `Hommes ${donnees.depart}`, data: depart.map((x) => -x.H), ...contour },
        { name: `Femmes ${donnees.depart}`, data: depart.map((x) => x.F), ...contour },
      ],
    }, true);
  }

  const graphiques = [];
  function ajouter(id, dessiner) {
    const element = document.getElementById(id);
    if (!element) return;
    const graphique = echarts.init(element, null, { renderer: "svg" });
    graphiques.push({ graphique, dessiner: () => dessiner(graphique) });
  }

  if (donnees.series) {
    const series = Object.fromEntries(donnees.series.map((s) => [s.scenario, s.points]));
    ajouter("projection-france", (g) => scenarios(g, series, "millions"));
  }
  if (donnees.population) {
    ajouter("projection-departement", (g) => scenarios(g, donnees.population, "personnes"));
    const choix = document.getElementById("annee-pyramide");
    ajouter("pyramide-avenir", (g) => pyramide(g, Number(choix.value)));
    choix.addEventListener("change", toutDessiner);
  }

  function toutDessiner() { for (const g of graphiques) g.dessiner(); }
  toutDessiner();
  window.addEventListener("resize", () => { for (const g of graphiques) g.graphique.resize(); });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", toutDessiner);
})();
