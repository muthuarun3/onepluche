"""Pages de la rubrique « Les Français sont-ils en sécurité ? » (appli 4) : vue France
(une carte par famille d'atteintes, le ressenti, les questions guidées), fiche
département (taux et rang de chaque atteinte) et carte comparée par famille.

Dossier de conception de l'appli sécurité, étape 8."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse

from demographie.donnees import series, territoires
from demographie.web.besoins import _carte_coloree
from demographie.web.carte import choix_territoire
from demographie.web.pages import Connexion, _decimal_fr, gabarits

routeur = APIRouter(prefix="/securite", include_in_schema=False)

RUBRIQUE = "SECURITE"
# Familles des faits, dans l'ordre d'affichage ; le ressenti vient après (« Le chiffre
# dit-il tout ? »), jamais en tête.
FAMILLES = ("PERSONNES", "VOLS", "BIENS", "STUPEFIANTS", "ROUTES")
RESSENTI = "RESSENTI"
# Atteinte phare de chaque famille : indicateur affiché en grand, et la fin de sa phrase.
PHARES = {
    "PERSONNES": ("FAITS_HOMICIDES", "victimes d'homicide enregistrées"),
    "VOLS": ("FAITS_CAMBRIOLAGES", "cambriolages de logement enregistrés"),
    "BIENS": ("FAITS_DEGRADATIONS", "destructions et dégradations volontaires enregistrées"),
    "STUPEFIANTS": (
        "FAITS_TRAFIC_STUPEFIANTS",
        "personnes mises en cause pour trafic de stupéfiants",
    ),
    "ROUTES": ("TUES_ROUTE", "personnes tuées sur les routes"),
}
# Taux de référence de chaque famille sur sa carte comparée.
TAUX_PHARES = {
    "PERSONNES": "TAUX_HOMICIDES",
    "VOLS": "TAUX_CAMBRIOLAGES",
    "BIENS": "TAUX_DEGRADATIONS",
    "STUPEFIANTS": "TAUX_TRAFIC_STUPEFIANTS",
    "ROUTES": "TAUX_TUES_ROUTE",
}
# Paires nombre -> taux pour la fiche département (routes : tués -> par million).
TAUX_DE = {"TUES_ROUTE": "TAUX_TUES_ROUTE"}
# Faits comptés là où ils sont commis : Paris et les départements où l'on accueille
# beaucoup de visiteurs par rapport aux habitants (montagne, littoral, Corse) ont des
# taux gonflés. Liste retenue à la main.
TOURISTIQUES = frozenset({"75", "05", "06", "17", "2A", "2B", "40", "66", "73", "74", "83", "85"})
# Première année affichée (délinquance et routes depuis 2016).
DEPUIS = 2016
# Le ressenti : CVS jusqu'en 2019, VRS depuis 2022 ; la courbe est coupée entre les deux.
FIN_CVS, DEBUT_VRS = 2019, 2022
# Les trois parts du ressenti, dans l'ordre d'affichage, avec leur nom court (légende).
PARTS = {
    "PART_INSECURITE_QUARTIER": "Dans leur quartier",
    "PART_INSECURITE_DOMICILE": "Chez elles",
    "PART_RENONCE_SORTIR": "Renoncent à sortir seules",
}
QUESTIONS = (
    ("La délinquance augmente-t-elle ?", "#evolution"),
    ("Où cambriole-t-on le plus ?", "/securite/famille/vols?indicateur=TAUX_CAMBRIOLAGES"),
    ("Les violences sexuelles augmentent-elles vraiment ?", "#violences-sexuelles"),
    ("Mon département est-il plus sûr que la moyenne ?", "#choix-titre"),
    ("Y a-t-il moins de morts sur les routes ?", "#routes"),
    ("Les Français se sentent-ils plus en insécurité ?", "#ressenti"),
)


def chiffre(valeur: Decimal | float | int | None, unite: str) -> str:
    """Valeur avec son unité : « 211 596 », « 6,12 ‰ », « 0,014 ‰ », « 47 par million »,
    « 22 % » ; « — » sans valeur."""
    if valeur is None:
        return "—"
    v = float(valeur)
    if unite == "pour_mille":
        return f"{_decimal_fr(v, 2 if abs(v) >= 0.1 else 3)} ‰"
    if unite == "par_million":
        return f"{_decimal_fr(v, 0)} par million"
    if unite == "pourcentage":
        return f"{_decimal_fr(v, 0 if v == int(v) else 1)} %"
    return _decimal_fr(v, 0)


def evolution(debut: float | None, fin: float | None) -> float | None:
    """Évolution en % de debut à fin (None si debut manque ou vaut zéro)."""
    if debut is None or fin is None or not debut:
        return None
    return 100 * (float(fin) - float(debut)) / float(debut)


def phrase_evolution(pourcent: float | None, annee: int) -> str:
    """-15.2, 2016 -> « 15 % de moins qu'en 2016 »."""
    if pourcent is None:
        return ""
    arrondi = round(abs(pourcent))
    if arrondi == 0:
        return f"autant qu'en {annee}"
    sens = "de plus" if pourcent > 0 else "de moins"
    return f"{arrondi} % {sens} qu'en {annee}"


gabarits.env.filters.update(chiffre=chiffre)


def _themes(conn) -> dict[str, str]:
    return {
        t["theme"]: t["theme_libelle"]
        for t in series.themes(conn)
        if t["rubrique"] == RUBRIQUE and t["theme"]
    }


def _resume(lignes: list[dict]) -> dict | None:
    """Dernière valeur, première valeur depuis 2016 et évolution d'une série."""
    lignes = [x for x in lignes if x["annee"] >= DEPUIS and x["valeur"] is not None]
    if not lignes:
        return None
    premiere, derniere = lignes[0], lignes[-1]
    pourcent = evolution(premiere["valeur"], derniere["valeur"])
    return {
        "annee": derniere["annee"],
        "valeur": derniere["valeur"],
        "provisoire": derniere["provisoire"],
        "debut": premiere["annee"],
        "evolution": pourcent if premiere["annee"] < derniere["annee"] else None,
        "phrase": phrase_evolution(pourcent, premiere["annee"])
        if premiere["annee"] < derniere["annee"]
        else "",
        "courbe": {
            "annees": [x["annee"] for x in lignes],
            "series": [{"nom": "", "valeurs": [float(x["valeur"]) for x in lignes]}],
        },
    }


def _ressenti(definitions: dict, valeurs: dict) -> dict | None:
    """Les parts du ressenti, sur une courbe coupée entre CVS (jusqu'en 2019) et VRS."""
    codes = [c for c in PARTS if c in definitions and c in valeurs]
    if not codes:
        return None
    # Années d'enquête, plus les années sans enquête entre les deux (2020, 2021) : des
    # trous qui coupent la courbe. Une année manquante dans une même enquête est sautée.
    annees = {x["annee"] for c in codes for x in valeurs[c]}
    if min(annees) <= FIN_CVS and max(annees) >= DEBUT_VRS:
        annees |= set(range(FIN_CVS + 1, DEBUT_VRS))
    axe = sorted(annees)
    courbe = {
        "annees": axe,
        "series": [
            {
                "nom": PARTS[c],
                "valeurs": [
                    next((float(x["valeur"]) for x in valeurs[c] if x["annee"] == a), None)
                    for a in axe
                ],
            }
            for c in codes
        ],
        "unite": "pourcentage",
    }
    mesures = []
    for c in codes:
        lignes = valeurs[c]
        cvs = [x for x in lignes if x["annee"] <= FIN_CVS]
        mesures.append(
            {
                "definition": definitions[c],
                "court": PARTS[c],
                "derniere": lignes[-1],
                "cvs": cvs[-1] if cvs else None,
            }
        )
    return {"mesures": mesures, "courbe": courbe, "fin_cvs": FIN_CVS, "debut_vrs": DEBUT_VRS}


@routeur.get("", response_class=HTMLResponse)
def securite(request: Request, conn: Connexion) -> HTMLResponse:
    tous = territoires.lister(conn)
    departements: dict[str, list[dict]] = {}
    for t in tous:
        if t["niveau"] == "DEP":
            departements.setdefault(t["parent_code"], []).append(t)
    definitions = {i["code"]: i for i in series.indicateurs(conn, rubrique=RUBRIQUE)}
    themes = _themes(conn)
    france = series.series_rubrique(conn, RUBRIQUE, "FRANCE", "FR")
    metropole = series.series_rubrique(conn, RUBRIQUE, "FRANCE", "FM")

    familles = []
    toutes_atteintes = []
    for famille in FAMILLES:
        phare, fin_phrase = PHARES[famille]
        nombres = sorted(
            c for c, d in definitions.items() if d["theme"] == famille and d["unite"] == "nombre"
        )
        autres = []
        for c in nombres:
            resume = _resume(france.get(c, []))
            if resume is None:
                continue
            taux = TAUX_DE.get(c, "TAUX_" + c.removeprefix("FAITS_"))
            atteinte = {
                "definition": definitions[c],
                "resume": resume,
                "taux": _resume(france.get(taux, [])) if taux in definitions else None,
                "taux_definition": definitions.get(taux),
            }
            if c.startswith("FAITS_"):
                toutes_atteintes.append(atteinte)
            if c != phare:
                autres.append(atteinte)
        resume = _resume(france.get(phare, [])) if phare in definitions else None
        if resume is None and not autres:
            continue
        familles.append(
            {
                "code": famille,
                "ancre": famille.lower(),
                "titre": themes.get(famille, famille.title()),
                "phare": {"definition": definitions.get(phare), "resume": resume}
                if resume
                else None,
                "fin_phrase": fin_phrase,
                "autres": autres,
                "lien": f"/securite/famille/{famille.lower()}",
            }
        )
    # « La délinquance augmente-t-elle ? » : les atteintes en hausse et en baisse.
    avec_evolution = [a for a in toutes_atteintes if a["resume"]["evolution"] is not None]
    hausses = sorted(
        (a for a in avec_evolution if a["resume"]["evolution"] >= 0.5),
        key=lambda a: -a["resume"]["evolution"],
    )
    baisses = sorted(
        (a for a in avec_evolution if a["resume"]["evolution"] < 0.5),
        key=lambda a: a["resume"]["evolution"],
    )
    violences = next(
        (a for a in toutes_atteintes if a["definition"]["code"] == "FAITS_VIOLENCES_SEXUELLES"),
        None,
    )
    contexte = {
        "familles": familles,
        "evolution": {"hausses": hausses, "baisses": baisses} if avec_evolution else None,
        "violences": violences,
        "ressenti": _ressenti(definitions, metropole),
        "questions": QUESTIONS,
        "regions": sorted((t for t in tous if t["niveau"] == "REG"), key=lambda t: t["libelle"]),
        "departements": departements,
        "choix": choix_territoire(tous, ("DEP",), "/securite/DEP/{code}"),
    }
    return gabarits.TemplateResponse(request, "securite.html", contexte)


@routeur.get("/DEP/{code}", response_class=HTMLResponse)
def departement(
    request: Request,
    conn: Connexion,
    code: Annotated[str, Chemin(pattern=r"^[0-9][0-9AB][0-9]?$")],
) -> HTMLResponse:
    fiche = territoires.trouver(conn, "DEP", code)
    if fiche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Département inconnu")
    definitions = {i["code"]: i for i in series.indicateurs(conn, rubrique=RUBRIQUE)}
    themes = _themes(conn)
    rangs = series.rangs(conn, RUBRIQUE, code)
    familles = []
    for famille in FAMILLES:
        lignes = []
        for c in sorted(
            c for c, d in definitions.items() if d["theme"] == famille and d["unite"] == "nombre"
        ):
            taux = TAUX_DE.get(c, "TAUX_" + c.removeprefix("FAITS_"))
            lignes.append(
                {
                    "definition": definitions[c],
                    "nombre": rangs.get(c),
                    "taux_definition": definitions.get(taux),
                    "taux": rangs.get(taux),
                }
            )
        if lignes:
            familles.append(
                {
                    "code": famille,
                    "titre": themes.get(famille, famille.title()),
                    "lignes": lignes,
                    "lien": f"/securite/famille/{famille.lower()}",
                }
            )
    contexte = {
        "fiche": fiche,
        "familles": familles,
        "avec_donnees": any(ligne["nombre"] for f in familles for ligne in f["lignes"]),
        "paris": code == "75",
        "touristique": code in TOURISTIQUES,
    }
    return gabarits.TemplateResponse(request, "securite_departement.html", contexte)


@routeur.get("/famille/{famille}", response_class=HTMLResponse)
def famille(
    request: Request,
    conn: Connexion,
    famille: Annotated[str, Chemin(pattern=r"^[a-z]+$")],
    indicateur: Annotated[str | None, Query(pattern=r"^[A-Z0-9_]+$")] = None,
) -> HTMLResponse:
    code_famille = famille.upper()
    if code_famille not in FAMILLES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Famille inconnue")
    definitions = {i["code"]: i for i in series.indicateurs(conn, rubrique=RUBRIQUE)}
    # On compare des taux : un nombre brut ne dirait que la taille du département.
    choix = sorted(
        (
            d
            for d in definitions.values()
            if d["theme"] == code_famille and d["unite"] in ("pour_mille", "par_million")
        ),
        key=lambda d: (d["code"] != TAUX_PHARES[code_famille], d["libelle"]),
    )
    if not choix:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Famille sans indicateur")
    if indicateur is None:
        indicateur = choix[0]["code"]
    elif definitions.get(indicateur) not in choix:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicateur inconnu pour cette famille")
    definition = definitions[indicateur]
    lignes = series.classement(conn, indicateur)
    avec = [ligne for ligne in lignes if ligne["valeur"] is not None]
    sans = [ligne for ligne in lignes if ligne["valeur"] is None]
    france = None
    if avec and avec[0]["france_code"]:
        france = {"code": avec[0]["france_code"], "valeur": avec[0]["france_valeur"]}
    themes = _themes(conn)
    contexte = {
        "famille": {"code": code_famille, "lien": famille, "titre": themes.get(code_famille)},
        "familles": [{"lien": f.lower(), "titre": themes.get(f, f.title())} for f in FAMILLES],
        "choix": choix,
        "definition": definition,
        "annee": avec[0]["annee"] if avec else None,
        "france": france,
        "classement": avec,
        "sans_donnee": sans,
        "carte": _carte_coloree(
            lignes, definition["unite"], "/securite/DEP/{code}", format_valeur=chiffre
        ),
    }
    return gabarits.TemplateResponse(request, "securite_famille.html", contexte)
