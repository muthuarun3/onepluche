// Graphiques de la fiche territoire. Les données arrivent dans <script id="donnees">.
"use strict";

(function () {
  const source = document.getElementById("donnees");
  if (!source || typeof echarts === "undefined" || !document.getElementById("pyramide")) return;
  const donnees = JSON.parse(source.textContent);
  const territoire = donnees.territoire;
  const nombre = new Intl.NumberFormat("fr-FR");
  let structure = donnees.structure;

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
    return {
      backgroundColor: c.surface, borderColor: c.bordure,
      textStyle: { color: c.texte, fontSize: 13 },
    };
  }

  function libelleAge(t) {
    return t.age_max === null ? `${t.age_min} ans et plus` : `${t.age_min} à ${t.age_max} ans`;
  }

  function tranches(lignes) {
    const parAge = new Map();
    for (const l of lignes) {
      const cle = l.age_min;
      if (!parAge.has(cle)) parAge.set(cle, { age_min: l.age_min, age_max: l.age_max, H: null, F: null });
      parAge.get(cle)[l.sexe] = l.valeur;
    }
    return [...parAge.values()].sort((a, b) => a.age_min - b.age_min);
  }

  const pyramide = echarts.init(document.getElementById("pyramide"), null, { renderer: "svg" });
  const evolution = echarts.init(document.getElementById("evolution"), null, { renderer: "svg" });

  function dessinerPyramide() {
    const c = couleurs();
    const t = tranches(structure);
    const max = Math.max(...t.map((x) => Math.max(x.H || 0, x.F || 0)));
    pyramide.setOption({
      animation: false,
      grid: { left: 8, right: 8, top: 8, bottom: 24, containLabel: true },
      tooltip: {
        trigger: "axis", axisPointer: { type: "shadow" }, ...infobulle(c),
        formatter: (p) => {
          const x = t[p[0].dataIndex];
          return `<b>${libelleAge(x)}</b><br>Hommes : ${nombre.format(x.H ?? 0)}<br>Femmes : ${nombre.format(x.F ?? 0)}`;
        },
      },
      xAxis: {
        type: "value", min: -max, max: max,
        axisLabel: {
          color: c.texte3, showMinLabel: false, showMaxLabel: false,
          formatter: (v) => nombre.format(Math.abs(v)),
        },
        splitLine: { lineStyle: { color: c.grille } },
      },
      yAxis: {
        type: "category", data: t.map((x) => (x.age_max === null ? `${x.age_min}+` : `${x.age_min}-${x.age_max}`)),
        axisTick: { show: false }, axisLine: { lineStyle: { color: c.bordure } },
        axisLabel: { color: c.texte2 },
      },
      series: [
        { name: "Hommes", type: "bar", stack: "p", barCategoryGap: "12%",
          data: t.map((x) => -(x.H || 0)), itemStyle: { color: c.hommes, borderRadius: [4, 0, 0, 4] } },
        { name: "Femmes", type: "bar", stack: "p",
          data: t.map((x) => x.F || 0), itemStyle: { color: c.femmes, borderRadius: [0, 4, 4, 0] } },
      ],
    }, true);
    const corps = document.querySelector("#table-pyramide tbody");
    corps.replaceChildren(...t.slice().reverse().map((x) => ligne([libelleAge(x), nombre.format(x.H ?? 0), nombre.format(x.F ?? 0)])));
  }

  function dessinerEvolution() {
    const c = couleurs();
    const e = donnees.evolution;
    const premierProvisoire = e.findIndex((x) => x.provisoire);
    const definitif = e.map((x, i) => (premierProvisoire === -1 || i <= premierProvisoire - 1 ? x.valeur : null));
    // Le tracé provisoire repart du dernier point définitif pour rester continu.
    const provisoire = e.map((x, i) => (premierProvisoire !== -1 && i >= premierProvisoire - 1 ? x.valeur : null));
    evolution.setOption({
      animation: false,
      grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
      tooltip: {
        trigger: "axis", ...infobulle(c),
        formatter: (p) => {
          const x = e[p[0].dataIndex];
          return `<b>1er janvier ${x.annee}</b>${x.provisoire ? " (provisoire)" : ""}<br>${nombre.format(x.valeur)} habitants`;
        },
      },
      xAxis: {
        type: "category", data: e.map((x) => x.annee), boundaryGap: false,
        axisLabel: { color: c.texte3 }, axisLine: { lineStyle: { color: c.bordure } },
      },
      yAxis: {
        type: "value", scale: true,
        axisLabel: { color: c.texte3, formatter: (v) => nombre.format(v) },
        splitLine: { lineStyle: { color: c.grille } },
      },
      series: [
        { name: "Population", type: "line", data: definitif, showSymbol: false, symbolSize: 8,
          lineStyle: { width: 2, color: c.serie }, itemStyle: { color: c.serie } },
        { name: "Provisoire", type: "line", data: provisoire, showSymbol: false, symbolSize: 8,
          lineStyle: { width: 2, type: "dashed", color: c.serie }, itemStyle: { color: c.serie } },
      ],
    }, true);
    const corps = document.querySelector("#table-evolution tbody");
    corps.replaceChildren(...e.slice().reverse().map((x) => ligne([`${x.annee}${x.provisoire ? " (p)" : ""}`, nombre.format(x.valeur)])));
  }

  function ligne(cellules) {
    const tr = document.createElement("tr");
    for (const texte of cellules) {
      const td = document.createElement("td");
      td.textContent = texte;
      tr.append(td);
    }
    return tr;
  }

  const choix = document.getElementById("annee-pyramide");
  choix.addEventListener("change", async () => {
    const params = new URLSearchParams({ niveau: territoire.niveau, code: territoire.code, annee: choix.value });
    const reponse = await fetch(`/api/v1/structure?${params}`);
    if (!reponse.ok) return;
    const json = await reponse.json();
    structure = json.tranches.flatMap((t) => [
      { sexe: "H", age_min: t.age_min, age_max: t.age_max, valeur: t.hommes },
      { sexe: "F", age_min: t.age_min, age_max: t.age_max, valeur: t.femmes },
    ]);
    dessinerPyramide();
  });

  function toutDessiner() { dessinerPyramide(); dessinerEvolution(); }
  toutDessiner();
  window.addEventListener("resize", () => { pyramide.resize(); evolution.resize(); });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", toutDessiner);
})();
