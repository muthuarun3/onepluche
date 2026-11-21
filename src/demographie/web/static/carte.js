// Carte des départements des pages par thème. Les valeurs arrivent dans <script id="donnees">,
// les contours dans window.CARTE_DEPARTEMENTS (static/carte-departements.js).
"use strict";

(function () {
  // Le choix de l'indicateur recharge la page sans attendre le bouton.
  const choix = document.getElementById("indicateur");
  if (choix && choix.form) choix.addEventListener("change", () => choix.form.submit());

  const source = document.getElementById("donnees");
  const conteneur = document.getElementById("carte");
  if (!source || !conteneur || typeof echarts === "undefined" || !window.CARTE_DEPARTEMENTS) return;
  const donnees = JSON.parse(source.textContent);
  const fmt = donnees.format;
  const nombre = new Intl.NumberFormat("fr-FR", {
    minimumFractionDigits: fmt.chiffres, maximumFractionDigits: fmt.chiffres,
  });
  const texteValeur = (v) => fmt.modele.replace("{}", nombre.format(v)).replace(" %", " %");

  echarts.registerMap("departements", window.CARTE_DEPARTEMENTS);
  const carte = echarts.init(conteneur, null, { renderer: "svg" });
  const valeurs = donnees.valeurs.map((d) => d.valeur);
  const min = Math.min(...valeurs);
  const max = Math.max(...valeurs);

  function couleurs() {
    const s = getComputedStyle(document.documentElement);
    const v = (nom) => s.getPropertyValue(nom).trim();
    return {
      texte: v("--texte"), texte3: v("--texte-3"), grille: v("--grille"),
      surface: v("--surface"), bordure: v("--bordure"), serie: v("--serie"), fond: v("--fond"),
    };
  }

  function dessiner() {
    const c = couleurs();
    carte.setOption({
      animation: false,
      tooltip: {
        trigger: "item", backgroundColor: c.surface, borderColor: c.bordure,
        textStyle: { color: c.texte, fontSize: 13 },
        formatter: (p) => {
          const nom = p.data ? p.data.nom : p.name;
          const valeur = p.data && p.data.value !== undefined ? texteValeur(p.data.value) : "pas de donnée";
          return `<b>${nom}</b><br>${valeur}`;
        },
      },
      // Une seule teinte, de clair à foncé : la carte ne juge pas, elle situe.
      visualMap: {
        type: "continuous", min, max: max > min ? max : min + 1, calculable: false,
        orient: "horizontal", left: "center", bottom: 0, itemWidth: 12, itemHeight: 160,
        text: [texteValeur(max), texteValeur(min)], textStyle: { color: c.texte3 },
        inRange: { color: [c.grille, c.serie] },
      },
      series: [{
        type: "map", map: "departements", roam: false, top: 8, bottom: 48,
        aspectScale: 0.72, selectedMode: false,
        itemStyle: { areaColor: c.fond || c.surface, borderColor: c.bordure, borderWidth: 0.6 },
        emphasis: { label: { show: false }, itemStyle: { borderColor: c.texte, borderWidth: 1.2 } },
        label: { show: false },
        data: donnees.valeurs.map((d) => ({ name: d.code, nom: d.nom, value: d.valeur })),
      }],
    }, true);
  }

  carte.on("click", (p) => {
    if (p.name) window.location.href = `/besoins/DEP/${encodeURIComponent(p.name)}`;
  });
  dessiner();
  window.addEventListener("resize", () => carte.resize());
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", dessiner);
})();
