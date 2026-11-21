"""Pages de la rubrique « De quoi les Français ont besoin ? » (appli 2) : choix du
département et fiche département (thèmes × accès, coût, manque, valeur France à côté)."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse

from demographie.donnees import series, territoires
from demographie.web.pages import Connexion, _decimal_fr, gabarits

routeur = APIRouter(prefix="/besoins", include_in_schema=False)

THEMES = {
    "LOGEMENT": "Logement",
    "ENERGIE": "Énergie",
    "EAU": "Eau",
    "ALIMENTATION": "Alimentation",
    "TRANSPORTS": "Transports",
    "SOINS": "Accès aux soins",
    "NUMERIQUE": "Numérique",
    "GARDE": "Garde d'enfants",
}
ANGLES = {
    "ACCES": ("Accès", "Ce qui est à portée"),
    "COUT": ("Coût", "Ce que ça coûte"),
    "MANQUE": ("Manque", "Qui en manque"),
}
# Chiffres en tête de fiche, dans cet ordre.
CHIFFRES_CLES = ("LOYER_APPARTEMENT_M2", "PART_DPE_FG", "APL_MG")
# Publiés pour la France seulement : affichés sur la vue d'ensemble, pas sur la fiche.
NATIONAUX = frozenset({"IPC"})
# Encadré 18-39 ans : indicateurs Filosofi publiés par âge de la personne de référence.
JEUNES = ("NIVEAU_VIE_MEDIAN", "TAUX_PAUVRETE")

_UNITES = {
    "euros_m2": ("{} €/m²", 1),
    "euros": ("{} €", 0),
    "pourcentage": ("{} %", 1),
    "consultations_hab": ("{} consultations", 2),
    "pour_10000": ("{} pour 10 000 hab.", 1),
    "mwh": ("{} MWh", 2),
    "annees": ("{} ans", 1),
    "indice": ("{}", 1),
    "ratio": ("{}", 1),
}


def valeur_unite(valeur: Decimal | float | int | None, unite: str) -> str:
    """12.4, « euros_m2 » -> « 12,4 €/m² » ; les effectifs en entier (« 5 416 826 »)."""
    if valeur is None:
        return "—"
    modele, chiffres = _UNITES.get(unite, ("{}", 0))
    return modele.format(_decimal_fr(float(valeur), chiffres)).replace(" %", " %")


gabarits.env.filters["valeur_unite"] = valeur_unite


@routeur.get("", response_class=HTMLResponse)
def besoins(request: Request, conn: Connexion) -> HTMLResponse:
    tous = territoires.lister(conn)
    departements: dict[str, list[dict]] = {}
    for t in tous:
        if t["niveau"] == "DEP":
            departements.setdefault(t["parent_code"], []).append(t)
    contexte = {
        "regions": sorted((t for t in tous if t["niveau"] == "REG"), key=lambda t: t["libelle"]),
        "departements": departements,
    }
    return gabarits.TemplateResponse(request, "besoins.html", contexte)


@routeur.get("/DEP/{code}", response_class=HTMLResponse)
def departement(
    request: Request,
    conn: Connexion,
    code: Annotated[str, Chemin(pattern=r"^[0-9][0-9AB][0-9]?$")],
) -> HTMLResponse:
    fiche = territoires.trouver(conn, "DEP", code)
    if fiche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Département inconnu")
    toutes = {i["code"]: i for i in series.indicateurs(conn, rubrique="BESOINS")}
    definitions = {c: i for c, i in toutes.items() if i["angle"] and c not in NATIONAUX}
    valeurs = {ligne["indicateur"]: ligne for ligne in series.fiche(conn, "DEP", code, "BESOINS")}

    def mesure(indicateur: str) -> dict:
        ligne = valeurs.get(indicateur)
        return {"definition": definitions[indicateur], "ligne": ligne}

    # Un bloc par thème ayant au moins un indicateur ; dans chaque colonne, les
    # indicateurs sans valeur pour ce département restent affichés comme absents.
    themes = []
    for theme, titre in THEMES.items():
        codes = sorted(c for c, d in definitions.items() if d["theme"] == theme)
        if not codes:
            continue
        colonnes = [
            {
                "titre": ANGLES[angle][0],
                "sous_titre": ANGLES[angle][1],
                "mesures": [mesure(c) for c in codes if definitions[c]["angle"] == angle],
            }
            for angle in ANGLES
        ]
        themes.append({"code": theme, "titre": titre, "colonnes": colonnes})
    jeunes = series.par_age(conn, "DEP", code, list(JEUNES))
    contexte = {
        "fiche": fiche,
        "chiffres": [mesure(c) for c in CHIFFRES_CLES if c in definitions],
        "themes": themes,
        "jeunes": _encadre_jeunes(jeunes, toutes),
    }
    return gabarits.TemplateResponse(request, "besoins_departement.html", contexte)


def _encadre_jeunes(lignes: list[dict], definitions: dict) -> dict | None:
    """Tableau tranche d'âge × indicateur de l'encadré 18-39 ans (None si rien)."""
    tranches: dict[tuple, dict] = {}
    for ligne in lignes:
        if ligne["age_min"] is None or ligne["age_min"] < 18 or (ligne["age_max"] or 99) > 39:
            continue
        cle = (ligne["age_min"], ligne["age_max"])
        tranches.setdefault(cle, {"libelle": f"{cle[0]}-{cle[1]} ans", "valeurs": {}})
        tranches[cle]["valeurs"][ligne["indicateur"]] = ligne
    if not tranches:
        return None
    colonnes = [definitions[c] for c in JEUNES if c in definitions]
    annee = max(ligne["annee"] for t in tranches.values() for ligne in t["valeurs"].values())
    return {
        "colonnes": colonnes,
        "tranches": [tranches[k] for k in sorted(tranches)],
        "annee": annee,
    }
