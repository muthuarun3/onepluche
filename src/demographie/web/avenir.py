"""Pages de la rubrique « Quel avenir pour les Français ? » (appli 5) : vue France
(projections nationales de 2026, choix du département, thèmes à venir) et fiche
département (projections Omphale 2022 : population, âges, fourchette des scénarios)."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse

from demographie.donnees import projections, series, territoires
from demographie.web.carte import choix_territoire
from demographie.web.pages import Connexion, gabarits

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
    ("Climat", "Chaleur, nuits tropicales, gel, pluies et sécheresse selon les scénarios "
     "du GIEC (Météo-France, DRIAS-2020)."),
    ("Risques naturels", "Inondations, sécheresse des sols, mouvements de terrain : les "
     "catastrophes naturelles reconnues et les plans de prévention (Géorisques)."),
)  # fmt: skip


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
def avenir(request: Request, conn: Connexion) -> HTMLResponse:
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
    donnees = {
        "series": [
            {"scenario": s, "points": [[a, _nombre(n["valeur"])] for a, n in sorted(v.items())]}
            for s, v in totaux.items()
        ]
    }
    contexte = {
        "france": france,
        "omphale": definitions.get("PROJ_POP"),
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
) -> HTMLResponse:
    fiche = territoires.trouver(conn, "DEP", code)
    if fiche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Département inconnu")
    lignes = _par_scenario(projections.population(conn, "DEP", code))
    definition = _definitions(conn).get("PROJ_POP")
    contexte = {"fiche": fiche, "projection": None, "definition": definition}
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
    return gabarits.TemplateResponse(request, "avenir_departement.html", contexte)
