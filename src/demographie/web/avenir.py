"""Pages de la rubrique « Quel avenir pour les Français ? » (appli 5) : vue France
(projections nationales de 2026, climat de la métropole, choix du département, thèmes à
venir) et fiche département (projections Omphale 2022 : population, âges, fourchette des
scénarios ; climat selon les scénarios du GIEC ; catastrophes naturelles reconnues et plans
de prévention, base GASPAR)."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse

from demographie.donnees import projections, series, territoires
from demographie.web.besoins import _carte_coloree
from demographie.web.carte import choix_territoire
from demographie.web.pages import Connexion, _decimal_fr, gabarits

routeur = APIRouter(prefix="/avenir", include_in_schema=False)

CENTRAL = "INSEE_CENTRAL"
BASSE = "INSEE_POP_BASSE"
HAUTE = "INSEE_POP_HAUTE"
# Année mise en avant sur la fiche, et années du tableau récapitulatif.
HORIZON = 2050
ANNEES_TABLEAU = (2018, 2030, 2050, 2070)
# Grands groupes d'âge des projections nationales (scénario central).
GROUPES_FRANCE = {
    (0, 19): "Moins de 20 ans",
    (20, 44): "20 à 44 ans",
    (45, 64): "45 à 64 ans",
    (65, None): "65 ans ou plus",
    (80, None): "dont 80 ans ou plus",
}
# Thèmes de la rubrique qui n'ont pas encore de données : annoncés sur la vue France.
A_VENIR = (
    ("L'eau", "Débits des rivières et sécheresses d'été selon le réchauffement (Explore2)."),
    ("Santé et dépendance", "Personnes âgées en perte d'autonomie d'ici 2070 (DREES)."),
)  # fmt: skip
# Questions guidées (dossier de conception, étape 8) : chacune ouvre la carte qui y répond.
QUESTIONS = (
    ("Combien d'habitants aura mon département en 2050 ?",
     "/avenir/theme/population?indicateur=EVOLUTION&annee=2050"),
    ("Mon département sera-t-il plus âgé que la France en 2050 ?",
     "/avenir/theme/population?indicateur=PART_75&annee=2050"),
    ("Combien de seniors pour 100 actifs en 2070 ?",
     "/avenir/theme/population?indicateur=SENIORS&annee=2070"),
    ("Combien de jours à 35 °C ou plus en fin de siècle, selon le scénario du GIEC ?",
     "/avenir/theme/climat?indicateur=CLIM_HD35&periode=2080"),
    ("Combien de nuits tropicales en plus d'ici 2050 ?",
     "/avenir/theme/climat?indicateur=CLIM_TR&periode=2040"),
    ("Combien de communes reconnues en sécheresse en 10 ans ?",
     "/avenir/theme/risques?indicateur=CATNAT_SECHERESSE_10ANS"),
)  # fmt: skip
# Risques : périls du graphique (les autres sont regroupés), en plus du tableau complet.
PERILS_GRAPHIQUE = ("INONDATION", "SECHERESSE")
# Climat : scénario du GIEC par défaut (intermédiaire, la trajectoire des politiques
# annoncées), ordre des indicateurs et période mise en avant.
SCENARIO_CLIMAT = "GIEC_SSP245"
INDICATEURS_CLIMAT = (
    "CLIM_TAS", "CLIM_HD35", "CLIM_TR", "CLIM_FD", "CLIM_PR", "CLIM_R20MM", "CLIM_CDD",
)  # fmt: skip
_UNITES_CLIMAT = {"degres_c": ("°C", 1), "jours": ("jours", 0), "millimetres": ("mm", 0)}
ScenarioClimat = Annotated[str | None, Query(alias="climat", pattern=r"^GIEC_SSP\d{3}$")]


def ecart(valeur, unite: str) -> str:
    """2.345, « degres_c » -> « +2,3 °C » ; -12.4, « jours » -> « −12 jours »."""
    if valeur is None:
        return "—"
    symbole, chiffres = _UNITES_CLIMAT.get(unite, ("", 1))
    x = round(float(valeur), chiffres)
    signe = "+" if x > 0 else "\u2212" if x < 0 else ""
    texte = f"{abs(x):,.{chiffres}f}".replace(",", "\u202f").replace(".", ",")
    if symbole == "jours" and abs(x) < 2:
        symbole = "jour"
    return f"{signe}{texte}\u00a0{symbole}".strip()


gabarits.env.filters["ecart"] = ecart


def _climat(conn, niveau: str, code: str, scenario: str | None, definitions: dict,
            comparaison: tuple[str, str] | None = None) -> dict | None:  # fmt: skip
    """Tableau du climat projeté d'un territoire pour un scénario du GIEC : une ligne par
    indicateur, une colonne par période (médiane et fourchette), et la France à côté."""
    lignes = projections.climat(conn, niveau, code)
    if not lignes:
        return None
    scenarios = [s for s in projections.scenarios(conn) if s["famille"] == "GIEC"]
    connus = {ligne["scenario"] for ligne in lignes}
    scenarios = [s for s in scenarios if s["code"] in connus]
    if scenario not in connus:
        scenario = SCENARIO_CLIMAT if SCENARIO_CLIMAT in connus else scenarios[0]["code"]
    autres = {}
    if comparaison:
        for ligne in projections.climat(conn, *comparaison):
            if ligne["scenario"] == scenario:
                autres[(ligne["indicateur"], ligne["debut"])] = ligne
    periodes = sorted({(ligne["debut"], ligne["fin"]) for ligne in lignes})
    par_cle = {
        (ligne["indicateur"], ligne["debut"]): ligne
        for ligne in lignes
        if ligne["scenario"] == scenario
    }
    indicateurs = []
    for indicateur in INDICATEURS_CLIMAT:
        presente = any((indicateur, d) in par_cle for d, _ in periodes)
        if indicateur not in definitions or not presente:
            continue
        indicateurs.append(
            {
                "definition": definitions[indicateur],
                "valeurs": [par_cle.get((indicateur, d)) for d, _ in periodes],
                "comparaison": [autres.get((indicateur, d)) for d, _ in periodes],
            }
        )
    choisi = next(s for s in scenarios if s["code"] == scenario)
    fin = periodes[-1]
    milieu = next((p for p in periodes if p[0] == 2040), periodes[0])
    cles = {i["definition"]["code"]: i for i in indicateurs}

    def valeur(indicateur: str, periode) -> dict | None:
        if indicateur not in cles:
            return None
        return cles[indicateur]["valeurs"][periodes.index(periode)]

    return {
        "scenario": choisi,
        "scenarios": scenarios,
        "periodes": periodes,
        "indicateurs": indicateurs,
        "milieu": milieu,
        "fin": fin,
        "rechauffement": valeur("CLIM_TAS", fin),
        "chaleur": valeur("CLIM_HD35", fin),
        "nuits": valeur("CLIM_TR", fin),
        "source": definitions.get("CLIM_TAS"),
    }


def _risques(conn, niveau: str, code: str, definitions: dict,
              comparaison: tuple[str, str] | None = None) -> dict | None:  # fmt: skip
    """Catastrophes naturelles reconnues par année et par péril, part des communes
    reconnues en sécheresse en 10 ans et couvertes par un plan de prévention."""
    totaux = series.serie(conn, "CATNAT_ARRETES", niveau, code)
    if not totaux:
        return None
    perils = series.ventilation(conn, "CATNAT_ARRETES", niveau, code, "peril_catnat")
    annees = [t["annee"] for t in totaux]
    definitives = [t for t in totaux if not t["provisoire"]]
    derniere = definitives[-1]["annee"] if definitives else annees[-1]
    dix_ans = [t for t in totaux if derniere - 10 < t["annee"] <= derniere]
    par_peril: dict[str, dict] = {}
    for p in perils:
        ligne = par_peril.setdefault(
            p["modalite"],
            {
                "code": p["modalite"],
                "libelle": p["libelle"],
                "total": 0,
                "dix_ans": 0,
                "annees": {},
            },  # fmt: skip
        )
        ligne["total"] += p["valeur"]
        ligne["annees"][p["annee"]] = p["valeur"]
        if derniere - 10 < p["annee"] <= derniere:
            ligne["dix_ans"] += p["valeur"]
    record = max(totaux, key=lambda t: t["valeur"])

    def dernier(indicateur: str, territoire: tuple[str, str]) -> dict | None:
        valeurs = [v for v in series.serie(conn, indicateur, *territoire) if not v["provisoire"]]
        return valeurs[-1] if valeurs else None

    france = comparaison or (niveau, code)
    groupes = []
    for c in PERILS_GRAPHIQUE:
        if c in par_peril:
            groupes.append({"libelle": par_peril[c]["libelle"], "annees": par_peril[c]["annees"]})
    autres = {
        a: sum(p["annees"].get(a, 0) for c, p in par_peril.items() if c not in PERILS_GRAPHIQUE)
        for a in annees
    }
    groupes.append({"libelle": "Autres périls", "annees": autres})
    return {
        "debut": annees[0],
        "derniere": derniere,
        "total": sum(t["valeur"] for t in totaux),
        "dix_ans": sum(t["valeur"] for t in dix_ans),
        "record": record,
        "perils": sorted(par_peril.values(), key=lambda p: -p["total"]),
        "secheresse": dernier("CATNAT_SECHERESSE_10ANS", (niveau, code)),
        "secheresse_france": dernier("CATNAT_SECHERESSE_10ANS", france) if comparaison else None,
        "pprn": dernier("COMMUNES_PPRN", (niveau, code)),
        "pprn_france": dernier("COMMUNES_PPRN", france) if comparaison else None,
        "definition": definitions.get("CATNAT_ARRETES"),
        "definition_secheresse": definitions.get("CATNAT_SECHERESSE_10ANS"),
        "graphique": {
            "annees": annees,
            "provisoires": [t["annee"] for t in totaux if t["provisoire"]],
            "series": [
                {
                    "libelle": g["libelle"],
                    "valeurs": [_nombre(g["annees"].get(a, 0)) for a in annees],
                }
                for g in groupes
            ],
        },
    }


def _nombre(valeur) -> int | float | None:
    """Valeur pour le JSON des graphiques (les Decimal n'y passent pas)."""
    if valeur is None:
        return None
    return int(valeur) if float(valeur).is_integer() else float(valeur)


def _evolution(depart: float | None, arrivee: float | None) -> float | None:
    if not depart or arrivee is None:
        return None
    return 100 * (float(arrivee) - float(depart)) / float(depart)


def _par_scenario(lignes: list[dict]) -> dict[str, dict[int, dict]]:
    resultat: dict[str, dict[int, dict]] = {}
    for ligne in lignes:
        resultat.setdefault(ligne["scenario"], {})[ligne["annee"]] = ligne
    return resultat


def _definitions(conn) -> dict[str, dict]:
    return {i["code"]: i for i in series.indicateurs(conn, rubrique="AVENIR")}


@routeur.get("", response_class=HTMLResponse)
def avenir(request: Request, conn: Connexion, climat: ScenarioClimat = None) -> HTMLResponse:
    definitions = _definitions(conn)
    tous = territoires.lister(conn)
    departements: dict[str, list[dict]] = {}
    for t in tous:
        if t["niveau"] == "DEP":
            departements.setdefault(t["parent_code"], []).append(t)
    nationales = projections.valeurs(conn, "PROJ_POP_FRANCE", "FRANCE", "FR", par_age=True)
    totaux = _par_scenario([n for n in nationales if n["age_min"] is None])
    france = None
    if CENTRAL in totaux:
        central = totaux[CENTRAL]
        annees = sorted(central)
        fin = annees[-1]
        groupes: dict[tuple, dict] = {}
        for n in nationales:
            cle = (n["age_min"], n["age_max"])
            if n["scenario"] == CENTRAL and cle in GROUPES_FRANCE:
                groupes.setdefault(cle, {})[n["annee"]] = n["valeur"]
        annees_groupes = sorted({a for g in groupes.values() for a in g})
        reperes = [a for a in (annees_groupes[:1] + [2050, 2070]) if a in annees_groupes]
        france = {
            "debut": annees[0],
            "fin": fin,
            "depart": central[annees[0]]["valeur"],
            "central": central[fin]["valeur"],
            "basse": totaux.get(BASSE, {}).get(fin, {}).get("valeur"),
            "haute": totaux.get(HAUTE, {}).get(fin, {}).get("valeur"),
            "pic": max(central.values(), key=lambda n: n["valeur"]),
            "reperes": reperes,
            "groupes": [
                {
                    "libelle": GROUPES_FRANCE[cle],
                    "valeurs": [groupes[cle].get(a) for a in reperes],
                    "dont": cle == (80, None),
                }
                for cle in GROUPES_FRANCE
                if cle in groupes
            ],  # fmt: skip
            "definition": definitions.get("PROJ_POP_FRANCE"),
        }
    risques = _risques(conn, "FRANCE", "FR", definitions)
    donnees = {
        "series": [
            {"scenario": s, "points": [[a, _nombre(n["valeur"])] for a, n in sorted(v.items())]}
            for s, v in totaux.items()
        ],
        "catnat": risques["graphique"] if risques else None,
    }
    contexte = {
        "france": france,
        "omphale": definitions.get("PROJ_POP"),
        "climat": _climat(conn, "FRANCE", "FM", climat, definitions),
        "risques": risques,
        "questions": QUESTIONS,
        "a_venir": A_VENIR,
        "choix": choix_territoire(tous, ("DEP",), "/avenir/DEP/{code}"),
        "regions": sorted((t for t in tous if t["niveau"] == "REG"), key=lambda t: t["libelle"]),
        "departements": departements,
        "donnees": donnees,
    }
    return gabarits.TemplateResponse(request, "avenir.html", contexte)


@routeur.get("/DEP/{code}", response_class=HTMLResponse)
def departement(
    request: Request,
    conn: Connexion,
    code: Annotated[str, Chemin(pattern=r"^[0-9][0-9AB][0-9]?$")],
    climat: ScenarioClimat = None,
) -> HTMLResponse:
    fiche = territoires.trouver(conn, "DEP", code)
    if fiche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Département inconnu")
    lignes = _par_scenario(projections.population(conn, "DEP", code))
    definitions = _definitions(conn)
    contexte = {
        "fiche": fiche,
        "projection": None,
        "definition": definitions.get("PROJ_POP"),
        "climat": _climat(conn, "DEP", code, climat, definitions, ("FRANCE", "FM")),
        "risques": _risques(conn, "DEP", code, definitions, ("FRANCE", "FR")),
    }
    central = lignes.get(CENTRAL)
    if central:
        depart = central[min(central)]
        horizon = central.get(HORIZON) or central[max(central)]
        france = _par_scenario(projections.population(conn, "FRANCE", "FR")).get(CENTRAL, {})
        france_depart = france.get(depart["annee"], {})
        france_horizon = france.get(horizon["annee"], {})
        scenarios = {s["code"]: s["libelle"] for s in projections.scenarios(conn)}
        annees = sorted(central)
        pyramide = projections.pyramide(conn, "DEP", code, annees, CENTRAL)
        contexte["projection"] = {
            "depart": depart,
            "horizon": horizon,
            "evolution": _evolution(depart["population"], horizon["population"]),
            "evolution_france": _evolution(
                france_depart.get("population"), france_horizon.get("population")
            ),
            "france": france_horizon,
            "basse": lignes.get(BASSE, {}).get(horizon["annee"]),
            "haute": lignes.get(HAUTE, {}).get(horizon["annee"]),
            "tableau": [
                {"annee": a, **{s: lignes.get(s, {}).get(a) for s in (CENTRAL, BASSE, HAUTE)}}
                for a in ANNEES_TABLEAU
                if a in central
            ],
            "scenarios": scenarios,
            "annees": annees,
        }
        contexte["donnees"] = {
            "territoire": {"niveau": "DEP", "code": code, "libelle": fiche["libelle"]},
            "scenarios": {s: scenarios.get(s, s) for s in lignes},
            "population": {
                s: [[a, _nombre(v["population"])] for a, v in sorted(par_annee.items())]
                for s, par_annee in lignes.items()
            },
            "pyramide": [
                {
                    "annee": p["annee"],
                    "sexe": p["sexe"],
                    "age_min": p["age_min"],
                    "age_max": p["age_max"],
                    "valeur": _nombre(p["valeur"]),
                }
                for p in pyramide
            ],
            "depart": depart["annee"],
            "horizon": horizon["annee"],
        }
    if contexte["risques"]:
        contexte.setdefault("donnees", {})["catnat"] = contexte["risques"]["graphique"]
    return gabarits.TemplateResponse(request, "avenir_departement.html", contexte)


# Pages thème : une carte et un classement des départements pour un indicateur choisi par
# liens (sans JavaScript). Population : scénario central de l'INSEE.
THEMES = {"population": "Population", "climat": "Climat", "risques": "Risques naturels"}
ANNEES_THEME = (2030, 2050, 2070)
INDICATEURS_POPULATION = {
    "EVOLUTION": ("Évolution de la population depuis 2018", "evolution", "pourcentage_signe"),
    "PART_75": ("Part des 75 ans ou plus", "part_75_plus", "pourcentage"),
    "SENIORS": ("Seniors (65 ans ou plus) pour 100 actifs (20-64 ans)",
                "seniors_pour_100_actifs", "nombre"),
}  # fmt: skip
INDICATEURS_RISQUES = {
    "CATNAT_SECHERESSE_10ANS": "pourcentage",
    "COMMUNES_PPRN": "pourcentage",
    "CATNAT_10ANS": "nombre",
}
_DEP = r"^[A-Z0-9_]+$"


def _format(valeur, unite: str) -> str:
    """Valeur d'une page thème : « +12,3 % », « 14,2 % », « 52 », « +2,3 °C »."""
    if valeur is None:
        return "—"
    if unite == "pourcentage_signe":
        v = float(valeur)
        return f"{'+' if v > 0 else '−' if v < 0 else ''}{_decimal_fr(abs(v), 1)} %"
    if unite == "pourcentage":
        return f"{_decimal_fr(float(valeur), 1)} %"
    if unite == "nombre":
        return _decimal_fr(float(valeur), 0)
    return ecart(valeur, unite)


gabarits.env.filters["valeur_theme"] = _format


def _lien(theme: str, **parametres) -> str:
    requete = "&".join(f"{k}={v}" for k, v in parametres.items() if v is not None)
    return f"/avenir/theme/{theme}" + (f"?{requete}" if requete else "")


@routeur.get("/theme/{theme}", response_class=HTMLResponse)
def theme(
    request: Request,
    conn: Connexion,
    theme: Annotated[str, Chemin(pattern=r"^[a-z]+$")],
    indicateur: Annotated[str | None, Query(pattern=_DEP)] = None,
    annee: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    climat: ScenarioClimat = None,
    periode: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> HTMLResponse:
    if theme not in THEMES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thème inconnu")
    definitions = _definitions(conn)
    choix: list[dict] = []  # groupes de liens : {"titre", "liens": [{libelle, url, actif}]}
    if theme == "population":
        indicateur = indicateur or "EVOLUTION"
        annee = annee or HORIZON
        if indicateur not in INDICATEURS_POPULATION or annee not in ANNEES_THEME:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicateur ou année inconnus")
        libelle, colonne, unite = INDICATEURS_POPULATION[indicateur]
        lignes = [
            {**ligne, "valeur": ligne[colonne]}
            for ligne in projections.classement_population(conn, CENTRAL, annee, 2018)
        ]
        titre = f"{libelle}, {annee}"
        definition = definitions.get("PROJ_POP")
        note = "Scénario central des projections de l'INSEE (Omphale 2022)."
        choix = [
            {"titre": "Indicateur", "liens": [
                {"libelle": v[0], "url": _lien(theme, indicateur=k, annee=annee),
                 "actif": k == indicateur} for k, v in INDICATEURS_POPULATION.items()]},
            {"titre": "Année", "liens": [
                {"libelle": str(a), "url": _lien(theme, indicateur=indicateur, annee=a),
                 "actif": a == annee} for a in ANNEES_THEME]},
        ]  # fmt: skip
    elif theme == "climat":
        indicateur = indicateur or "CLIM_HD35"
        scenarios = [s for s in projections.scenarios(conn) if s["famille"] == "GIEC"]
        codes = [s["code"] for s in scenarios]
        scenario = climat or (SCENARIO_CLIMAT if SCENARIO_CLIMAT in codes else None)
        periode = periode or 2080
        disponibles = [i for i in INDICATEURS_CLIMAT if i in definitions]
        if indicateur not in disponibles or scenario not in codes:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicateur ou scénario inconnus")
        definition = definitions[indicateur]
        unite = definition["unite"]
        lignes = projections.classement_climat(conn, indicateur, scenario, periode)
        if not any(ligne["valeur"] is not None for ligne in lignes):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Période inconnue")
        choisi = next(s for s in scenarios if s["code"] == scenario)
        titre = f"{definition['libelle']}, {periode}-{periode + 19}"
        note = (f"Écart à 1995-2014, médiane des modèles. {choisi['libelle']} : "
                f"{choisi['equivalent_giec']} de réchauffement mondial vers 2100.")  # fmt: skip
        choix = [
            {"titre": "Indicateur", "liens": [
                {"libelle": definitions[i]["libelle"],
                 "url": _lien(theme, indicateur=i, climat=scenario, periode=periode),
                 "actif": i == indicateur} for i in disponibles]},
            {"titre": "Scénario", "liens": [
                {"libelle": s["libelle"],
                 "url": _lien(theme, indicateur=indicateur, climat=s["code"], periode=periode),
                 "actif": s["code"] == scenario} for s in scenarios]},
            {"titre": "Période", "liens": [
                {"libelle": f"{d}-{d + 19}",
                 "url": _lien(theme, indicateur=indicateur, climat=scenario, periode=d),
                 "actif": d == periode} for d in (2020, 2040, 2060, 2080)]},
        ]  # fmt: skip
    else:
        indicateur = indicateur or "CATNAT_SECHERESSE_10ANS"
        if indicateur not in INDICATEURS_RISQUES:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicateur inconnu")
        unite = INDICATEURS_RISQUES[indicateur]
        totaux = [t for t in series.serie(conn, "CATNAT_ARRETES", "FRANCE", "FR")
                  if not t["provisoire"]]  # fmt: skip
        derniere = totaux[-1]["annee"] if totaux else None
        if indicateur == "CATNAT_10ANS":
            definition = definitions.get("CATNAT_ARRETES")
            lignes = (series.cumul_departements(conn, "CATNAT_ARRETES", derniere - 9, derniere)
                      if derniere else [])  # fmt: skip
            titre = (
                f"Catastrophes naturelles reconnues, {derniere - 9}-{derniere}" if derniere else ""
            )
            note = (
                "Reconnaissances par commune et par péril, sur les dix dernières années complètes."
            )
        else:
            definition = definitions.get(indicateur)
            brutes = series.classement(conn, indicateur)
            lignes = [{**b, "niveau": "DEP"} for b in brutes]
            if brutes and brutes[0]["france_code"]:
                lignes.append(
                    {
                        "niveau": "FRANCE",
                        "code": brutes[0]["france_code"],
                        "libelle": "France",
                        "valeur": brutes[0]["france_valeur"],
                    }
                )
            annee_valeurs = next((b["annee"] for b in brutes if b["valeur"] is not None), None)
            titre = f"{definition['libelle']}, {annee_valeurs}" if definition else ""
            note = definition["definition"] if definition else ""
        choix = [{"titre": "Indicateur", "liens": [
            {"libelle": (definitions["CATNAT_ARRETES"]["libelle"] + " en 10 ans"
                         if k == "CATNAT_10ANS" and "CATNAT_ARRETES" in definitions
                         else definitions.get(k, {}).get("libelle", k)),
             "url": _lien(theme, indicateur=k), "actif": k == indicateur}
            for k in INDICATEURS_RISQUES]}]  # fmt: skip
    departements = [ligne for ligne in lignes if ligne["niveau"] == "DEP"]
    france = next((ligne for ligne in lignes if ligne["niveau"] == "FRANCE"), None)
    avec = sorted((d for d in departements if d["valeur"] is not None),
                  key=lambda d: -float(d["valeur"]))  # fmt: skip
    sans = [d for d in departements if d["valeur"] is None]
    carte = _carte_coloree(departements, unite, lien="/avenir/DEP/{code}", format_valeur=_format)
    contexte = {
        "theme": theme,
        "themes": THEMES,
        "titre": titre,
        "note": note,
        "choix": choix,
        "unite": unite,
        "definition": definition,
        "france": france if france and france["valeur"] is not None else None,
        "classement": avec,
        "sans_donnee": sans,
        "carte": carte,
    }
    return gabarits.TemplateResponse(request, "avenir_theme.html", contexte)
