"""Pages HTML : accueil (choix du territoire) et fiche d'un territoire."""

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from demographie import donnees
from demographie.donnees import series, territoires

DOSSIER = Path(__file__).parent
STATIQUE = DOSSIER / "static"
gabarits = Jinja2Templates(directory=DOSSIER / "templates")
routeur = APIRouter(include_in_schema=False)
Connexion = Annotated[psycopg.Connection, Depends(donnees.connexion_lecture)]

# Ordre et libellés courts des chiffres clés.
CHIFFRES_CLES = (
    ("POP", "Population"),
    ("PART_MOINS_20", "Moins de 20 ans"),
    ("PART_60_PLUS", "60 ans et plus"),
    ("PART_75_PLUS", "75 ans et plus"),
    ("INDICE_VIEILLISSEMENT", "Indice de vieillissement"),
)


def _nombre(valeur: Decimal | int | None) -> int | float | None:
    """Les Decimal de PostgreSQL ne passent pas en JSON : entier si possible, sinon réel."""
    if valeur is None:
        return None
    return int(valeur) if valeur == valeur.to_integral_value() else float(valeur)


def _niveau_libelle(niveau: str) -> str:
    return {"FRANCE": "Pays", "REG": "Région", "DEP": "Département"}[niveau]


@routeur.get("/", response_class=HTMLResponse)
def accueil(request: Request, conn: Connexion) -> HTMLResponse:
    tous = territoires.lister(conn)
    departements: dict[str, list[dict]] = {}
    for t in tous:
        if t["niveau"] == "DEP":
            departements.setdefault(t["parent_code"], []).append(t)
    contexte = {
        "france": [t for t in tous if t["niveau"] == "FRANCE"],
        "regions": sorted((t for t in tous if t["niveau"] == "REG"), key=lambda t: t["libelle"]),
        "departements": departements,
    }
    return gabarits.TemplateResponse(request, "accueil.html", contexte)


@routeur.get("/territoire/{niveau}/{code}", response_class=HTMLResponse)
def territoire(
    request: Request,
    conn: Connexion,
    niveau: Literal["FRANCE", "REG", "DEP"],
    code: Annotated[str, Chemin(pattern=r"^[0-9A-Z]{2,3}$")],
) -> HTMLResponse:
    fiche = territoires.trouver(conn, niveau, code)
    if fiche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Territoire inconnu")
    cles = series.chiffres_cles(conn, niveau, code)
    definitions = {i["code"]: i for i in series.indicateurs(conn)}
    structure = series.structure(conn, niveau, code)
    evolution = series.serie(conn, "POP", niveau, code)
    chiffres = [
        {
            "code": c,
            "libelle": libelle,
            "unite": definitions[c]["unite"],
            "definition": definitions[c]["definition"],
            "valeur": _nombre(cles[c]["valeur"]),
            "annee": cles[c]["annee"],
            "provisoire": cles[c]["provisoire"],
        }
        for c, libelle in CHIFFRES_CLES
        if c in cles
    ]
    donnees_graphiques = {
        "territoire": {"niveau": niveau, "code": code, "libelle": fiche["libelle"]},
        "structure": [{**ligne, "valeur": _nombre(ligne["valeur"])} for ligne in structure],
        "evolution": [{**ligne, "valeur": _nombre(ligne["valeur"])} for ligne in evolution],
    }
    contexte = {
        "fiche": fiche,
        "niveau_libelle": _niveau_libelle(niveau),
        "chiffres": chiffres,
        "annee": chiffres[0]["annee"] if chiffres else None,
        "annees": [ligne["annee"] for ligne in reversed(evolution)],
        "enfants": territoires.enfants(conn, niveau, code),
        "source": definitions.get("POP"),
        "donnees": donnees_graphiques,
    }
    return gabarits.TemplateResponse(request, "territoire.html", contexte)
