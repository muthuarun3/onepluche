"""Pages HTML : accueil (« Qui sont les Français ? », choix du territoire), fiches."""

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from demographie import donnees
from demographie.donnees import series, sources, territoires
from demographie.web.carte import choix_territoire
from demographie.web.resume import resume

DOSSIER = Path(__file__).parent
STATIQUE = DOSSIER / "static"
gabarits = Jinja2Templates(directory=DOSSIER / "templates")
routeur = APIRouter(include_in_schema=False)


def _decimal_fr(valeur: float, chiffres: int = 1) -> str:
    return f"{valeur:,.{chiffres}f}".replace(",", "\u202f").replace(".", ",")


def _millions(valeur: float) -> str:
    """69 081 996 -> « 69,1 millions »."""
    return f"{_decimal_fr(float(valeur) / 1e6)} millions"


def _entier(valeur: float) -> str:
    """642 905 -> « 642 905 » (espace fine insécable)."""
    return _decimal_fr(valeur, 0)


def _pct(valeur: float, chiffres: int = 1) -> str:
    return f"{_decimal_fr(valeur, chiffres)}\u00a0%"


gabarits.env.filters.update(millions=_millions, entier=_entier, pct=_pct)
Connexion = Annotated[psycopg.Connection, Depends(donnees.connexion_lecture)]

# Les questions de la macro-catégorie « Données », chacune avec l'application qui y répond ;
# l'accueil et la barre latérale les reprennent sous ce titre.
QUESTIONS = (
    {
        "titre": "Qui sont les Français ?",
        "lien": "/francais",
        "resume": "Combien, quel âge, quel travail, quelles études, quelle santé.",
    },
    {
        "titre": "De quoi les Français ont besoin ?",
        "lien": "/besoins",
        "resume": "Logement, énergie, eau, alimentation, transports, soins, numérique, "
        "garde d'enfants.",
    },
    {
        "titre": "Où va l'argent public ?",
        "lien": "/argent-public",
        "resume": "Dépenses, recettes, déficit et dette ; le budget de l'État mois par mois et "
        "par mission ; bientôt mon département et les impôts d'un ménage type.",
    },
    {
        "titre": "Quel avenir pour les Français ?",
        "lien": "/avenir",
        "resume": "Combien serons-nous et à quel âge d'ici 2070 ; bientôt le climat et les "
        "risques naturels.",
    },
    {
        "titre": "Les Français sont-ils en sécurité ?",
        "lien": "/securite",
        "resume": "Violences, vols, dégradations, stupéfiants, routes, et ce que les Français "
        "ressentent.",
    },
    {
        "titre": "Comment travaillent les Français ?",
        "lien": "/travail",
        "resume": "Chômage, demandeurs d'emploi, métiers qui peinent à recruter, créations "
        "d'entreprises, secteurs qui embauchent.",
    },
)
gabarits.env.globals["questions_menu"] = QUESTIONS

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
def accueil(request: Request) -> HTMLResponse:
    return gabarits.TemplateResponse(request, "accueil.html", {"questions": QUESTIONS})


@routeur.get("/francais", response_class=HTMLResponse)
def francais(request: Request, conn: Connexion) -> HTMLResponse:
    tous = territoires.lister(conn)
    departements: dict[str, list[dict]] = {}
    for t in tous:
        if t["niveau"] == "DEP":
            departements.setdefault(t["parent_code"], []).append(t)
    contexte = {
        "france": [t for t in tous if t["niveau"] == "FRANCE"],
        "regions": sorted((t for t in tous if t["niveau"] == "REG"), key=lambda t: t["libelle"]),
        "departements": departements,
        "choix": choix_territoire(tous, ("REG", "DEP"), "/territoire/{niveau}/{code}"),
        "resume": resume(conn),
    }
    return gabarits.TemplateResponse(request, "francais.html", contexte)


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
        "evolution": [
            {"annee": e["annee"], "valeur": _nombre(e["valeur"]), "provisoire": e["provisoire"]}
            for e in evolution
        ],
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


STATUTS = {
    "PUBLIE": "À jour",
    "EN_ATTENTE": "En attente de validation",
    "REJETE": "Dernier fichier rejeté",
    "EN_COURS": "Import en cours",
    None: "Pas encore importé",
}


@routeur.get("/sources", response_class=HTMLResponse)
def page_sources(request: Request, conn: Connexion) -> HTMLResponse:
    lignes = sources.etat_imports(conn)
    contexte = {"lignes": lignes, "statuts": STATUTS}
    return gabarits.TemplateResponse(request, "sources.html", contexte)
