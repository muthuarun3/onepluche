"""Pages de la rubrique « De quoi les Français ont besoin ? » (appli 2) : vue d'ensemble
(budget des ménages, prix, un chiffre France par thème, choix du département) et fiche
département (thèmes × accès, coût, manque, valeur France à côté)."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse

from demographie.donnees import series, territoires
from demographie.web.pages import Connexion, _decimal_fr, gabarits

routeur = APIRouter(prefix="/besoins", include_in_schema=False)

THEMES = {
    "BUDGET": "Budget des ménages",
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
NATIONAUX = frozenset({"IPC", "DEPENSE_CONSO_MENAGES", "PART_DEPENSE_PRE_ENGAGEE"})
# Point de départ de la hausse des prix sur la vue d'ensemble.
PRIX_DEPUIS = 2015
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
    toutes = {i["code"]: i for i in series.indicateurs(conn, rubrique="BESOINS")}
    france = {ligne["indicateur"]: ligne for ligne in series.fiche(conn, "FRANCE", "FR", "BESOINS")}

    def mesure(indicateur: str) -> dict | None:
        if indicateur not in toutes:
            return None
        return {"definition": toutes[indicateur], "ligne": france.get(indicateur)}

    postes = series.repartition(conn, "DEPENSE_CONSO_MENAGES", "FRANCE", "FR")
    budget = None
    if postes and postes[0]["total"]:
        total = postes[0]["total"]
        lignes = sorted(
            ({"libelle": p["libelle"], "part": float(100 * p["valeur"] / total)} for p in postes),
            key=lambda p: -p["part"],
        )
        budget = {
            "annee": postes[0]["annee"],
            "provisoire": postes[0]["provisoire"],
            "total_milliards": float(total) / 1000,
            "postes": lignes,
            "max": lignes[0]["part"],
            "definition": toutes["DEPENSE_CONSO_MENAGES"],
            "pre_engagee": mesure("PART_DEPENSE_PRE_ENGAGEE"),
        }
    hausses = series.hausse_prix(conn, PRIX_DEPUIS)
    prix = None
    if hausses:
        prix = {
            "debut": hausses[0]["debut"],
            "fin": hausses[0]["fin"],
            "postes": hausses,
            "max": max(abs(float(h["hausse"])) for h in hausses) or 1,
            "definition": toutes.get("IPC"),
        }
    contexte = {
        "budget": budget,
        "pages_themes": _pages_themes(toutes),
        "prix": prix,
        "themes": [
            {"titre": THEMES[toutes[c]["theme"]], "mesure": mesure(c)}
            for c in CHIFFRES_CLES
            if c in toutes
        ],
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
        themes.append({"code": theme, "titre": titre, "colonnes": colonnes, "lien": theme.lower()})
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


def _cartographiables(toutes: dict, theme: str | None = None) -> list[dict]:
    """Indicateurs publiés par département (rangés par angle), d'un thème ou de tous."""
    ordre = list(ANGLES)
    return sorted(
        (
            i
            for c, i in toutes.items()
            if i["angle"] and c not in NATIONAUX and (theme is None or i["theme"] == theme)
        ),
        key=lambda i: (ordre.index(i["angle"]), i["code"]),
    )


def _pages_themes(toutes: dict) -> list[dict]:
    """Thèmes ayant au moins un indicateur départemental, pour les liens vers leur carte."""
    presents = {i["theme"] for i in _cartographiables(toutes)}
    return [{"lien": t.lower(), "titre": titre} for t, titre in THEMES.items() if t in presents]


@routeur.get("/theme/{theme}", response_class=HTMLResponse)
def theme(
    request: Request,
    conn: Connexion,
    theme: Annotated[str, Chemin(pattern=r"^[a-z]+$")],
    indicateur: Annotated[str | None, Query(pattern=r"^[A-Z0-9_]+$")] = None,
) -> HTMLResponse:
    code_theme = theme.upper()
    toutes = {i["code"]: i for i in series.indicateurs(conn, rubrique="BESOINS")}
    choix = _cartographiables(toutes, code_theme)
    if code_theme not in THEMES or not choix:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thème inconnu")
    if indicateur is None:
        # Le chiffre clé du thème s'il y en a un, sinon le premier indicateur.
        cles = [c for c in CHIFFRES_CLES if toutes.get(c) in choix]
        indicateur = cles[0] if cles else choix[0]["code"]
    elif toutes.get(indicateur) not in choix:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicateur inconnu pour ce thème")
    definition = toutes[indicateur]
    lignes = series.classement(conn, indicateur)
    avec = [ligne for ligne in lignes if ligne["valeur"] is not None]
    sans = [ligne for ligne in lignes if ligne["valeur"] is None]
    france = None
    if avec and avec[0]["france_code"] and definition["nature"] not in ("effectif", "flux"):
        france = {
            "code": avec[0]["france_code"],
            "valeur": avec[0]["france_valeur"],
            "provisoire": avec[0]["france_provisoire"],
        }
    modele_unite = _UNITES.get(definition["unite"], ("{}", 0))
    donnees = {
        "indicateur": {"code": indicateur, "libelle": definition["libelle"]},
        # Format des nombres repris par le script de la carte (« {} €/m² », 1 décimale).
        "format": dict(zip(("modele", "chiffres"), modele_unite, strict=True)),
        "valeurs": [
            {"code": ligne["code"], "nom": ligne["libelle"], "valeur": float(ligne["valeur"])}
            for ligne in avec
        ],
    }
    contexte = {
        "theme": {"code": code_theme, "lien": theme, "titre": THEMES[code_theme]},
        "choix": choix,
        "definition": definition,
        "annee": avec[0]["annee"] if avec else None,
        "provisoire": any(ligne["provisoire"] for ligne in avec),
        "france": france,
        "classement": avec,
        "sans_donnee": sans,
        "pages_themes": _pages_themes(toutes),
        "donnees": donnees,
    }
    return gabarits.TemplateResponse(request, "besoins_theme.html", contexte)
