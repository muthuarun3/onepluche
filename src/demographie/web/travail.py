"""Pages de la rubrique « Comment travaillent les Français ? » : vue France (chômage depuis
1982, demandeurs d'emploi, entreprises, secteurs, métiers qui peinent à recruter, puis la
carte pour choisir un département), fiche département (les mêmes blocs, comparés à la
France, avec le rang du département) et carte par thème.

Les quatre questions guidées ont chacune leur bloc, sur la vue France comme sur la fiche.
Dossier de conception de l'appli travail, étape 8."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse

from demographie.donnees import series, territoires
from demographie.web.besoins import _carte_coloree
from demographie.web.carte import choix_territoire
from demographie.web.pages import Connexion, _decimal_fr, gabarits
from demographie.web.securite import chiffre, evolution

routeur = APIRouter(prefix="/travail", include_in_schema=False)

RUBRIQUE = "TRAVAIL"
# Le taux de chômage trimestriel appartient à la rubrique de l'appli 1 : on le relit.
CHOMAGE = "TAUX_CHOMAGE"
# Le salaire net moyen est importé par l'appli « Comment vivent les Français ? ».
SALAIRE = "SALAIRE_NET_MOYEN"
# Grands secteurs de l'emploi salarié, dans l'ordre d'affichage ; l'intérim est à part
# (compté dans le commerce et les services).
SECTEURS = (
    "AGRICULTURE",
    "INDUSTRIE",
    "CONSTRUCTION",
    "COMMERCE_SERVICES",
    "ADMIN_ENSEIGNEMENT_SANTE",
)
INTERIM = "INTERIM"
# Métiers BMO : seuil de projets en dessous duquel une part de projets difficiles ne veut
# pas dire grand-chose (quelques employeurs suffisent à la faire varier).
PROJETS_MIN = 50
# Fiche département : années de chômage montrées sur la courbe.
ANNEES_COURBE = 10
# Cartes par thème : adresse -> (thème, indicateurs comparables entre départements).
# On compare des taux et des parts : un nombre brut ne dirait que la taille du département.
THEMES_CARTE = {
    "chercher-creer": (
        "CHERCHER_CREER",
        (CHOMAGE, "PART_LONGUE_DUREE", "PART_RECRUTEMENTS_DIFFICILES"),
    ),
    "emploi": ("EMPLOI", ("PART_INTERIM", "PART_INDEPENDANTS")),
    "comment": ("CONDITIONS", ("PART_CONTRATS_COURTS", "PART_TEMPS_PARTIEL")),
    "salaires": ("SALAIRES", (SALAIRE,)),
}
QUESTIONS = (
    ("Le chômage baisse-t-il dans mon département ?", "chomage"),
    ("Quels métiers peinent à recruter près de chez moi ?", "metiers"),
    ("Crée-t-on plus d'entreprises qu'il n'en ferme ?", "entreprises"),
    ("Quels secteurs créent des emplois ?", "secteurs"),
)
MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)  # fmt: skip


def signe(valeur: float | None, unite: str = "evolution") -> str:
    """Écart signé : +3,2 % (évolution), +0,4 point (taux), +1 250 (nombre) ; « — » sans
    valeur. Le moins est typographique (−)."""
    if valeur is None:
        return "—"
    v = float(valeur)
    if unite == "evolution":
        texte = f"{_decimal_fr(abs(v), 1)}\u00a0%"
    elif unite == "point":
        texte = f"{_decimal_fr(abs(v), 1)}\u00a0point" + ("s" if round(abs(v), 1) >= 2 else "")
    else:
        texte = _decimal_fr(abs(v), 0)
    return ("+" if v > 0 else "−" if v < 0 else "") + texte


def valeur(v: Decimal | float | int | None, unite: str) -> str:
    """Comme le filtre « chiffre », avec l'euro : « 2 505 € »."""
    if unite == "euros":
        return "—" if v is None else f"{chiffre(v, 'nombre')}\u00a0€"
    return chiffre(v, unite)


def tranche(age_min: int | None, age_max: int | None) -> str:
    """(0, 24) -> « moins de 25 ans » ; (25, 39) -> « 25-39 ans » ; (55, None) -> « 55 ans
    ou plus »."""
    if age_min in (None, 0) and age_max is not None:
        return f"moins de {age_max + 1} ans"
    if age_max is None:
        return f"{age_min} ans ou plus"
    return f"{age_min}-{age_max} ans"


gabarits.env.filters.update(signe=signe, valeur=valeur, tranche_tuple=lambda ages: tranche(*ages))


def libelle_periode(periode: date, periode_type: str) -> str:
    """« 2e trimestre 2026 », « 1er trimestre 2026 », « octobre 2026 », « 2025 »."""
    if periode_type == "TRIMESTRE":
        rang = (periode.month - 1) // 3 + 1
        return f"{rang}{'er' if rang == 1 else 'e'} trimestre {periode.year}"
    if periode_type == "MOIS":
        return f"{MOIS[periode.month - 1]} {periode.year}"
    return str(periode.year)


def _court(periode: date, periode_type: str) -> str:
    """Étiquette d'axe : « T2 2026 », « 2025 »."""
    if periode_type == "TRIMESTRE":
        return f"T{(periode.month - 1) // 3 + 1} {periode.year}"
    return str(periode.year)


def _un_an_avant(periode: date) -> date:
    return periode.replace(year=periode.year - 1)


def _nombre(valeur: Decimal | int | float | None) -> float | None:
    return None if valeur is None else float(valeur)


def _courbe(par_nom: dict[str, list[dict]], depuis: date | None = None) -> dict | None:
    """Courbes alignées sur les mêmes périodes : {annees: [étiquettes], series: [...]}."""
    par_nom = {
        nom: [x for x in lignes if depuis is None or x["periode"] >= depuis]
        for nom, lignes in par_nom.items()
        if lignes
    }
    par_nom = {nom: lignes for nom, lignes in par_nom.items() if lignes}
    if not par_nom:
        return None
    periodes = sorted({(x["periode"], x["periode_type"]) for v in par_nom.values() for x in v})
    return {
        "annees": [_court(p, t) for p, t in periodes],
        "series": [
            {
                "nom": nom,
                "valeurs": [
                    next((_nombre(x["valeur"]) for x in lignes if x["periode"] == p), None)
                    for p, _ in periodes
                ],
            }
            for nom, lignes in par_nom.items()
        ],
    }


def _derniere_et_un_an(lignes: list[dict]) -> dict | None:
    """Dernière valeur d'une série, celle de la même période un an plus tôt et l'écart."""
    if not lignes:
        return None
    derniere = lignes[-1]
    avant = next((x for x in lignes if x["periode"] == _un_an_avant(derniere["periode"])), None)
    return {
        "valeur": derniere["valeur"],
        "periode": derniere["periode"],
        "libelle": libelle_periode(derniere["periode"], derniere["periode_type"]),
        "provisoire": derniere["provisoire"],
        "avant": avant["valeur"] if avant else None,
        "ecart": float(derniere["valeur"]) - float(avant["valeur"]) if avant else None,
        "evolution": evolution(avant["valeur"], derniere["valeur"]) if avant else None,
    }


def _a_la_periode(lignes: list[dict], periode: date) -> Decimal | None:
    return next((x["valeur"] for x in lignes if x["periode"] == periode), None)


def _rang(conn, indicateur: str, code: str) -> dict | None:
    """Valeur d'un département, son rang (1 = la plus forte) et la valeur France."""
    lignes = [x for x in series.classement(conn, indicateur) if x["valeur"] is not None]
    for rang, ligne in enumerate(lignes, start=1):
        if ligne["code"] == code:
            return {**ligne, "rang": rang, "classes": len(lignes)}
    return None


def _cumul(lignes: list[dict], n: int) -> dict | None:
    """Somme des n dernières périodes et des n précédentes (12 mois ou 4 trimestres)."""
    if len(lignes) < n:
        return None
    recentes, precedentes = lignes[-n:], lignes[-2 * n : -n]
    total = sum(float(x["valeur"]) for x in recentes)
    avant = sum(float(x["valeur"]) for x in precedentes) if len(precedentes) == n else None
    return {
        "total": total,
        "avant": avant,
        "evolution": evolution(avant, total) if avant else None,
        "debut": libelle_periode(recentes[0]["periode"], recentes[0]["periode_type"]),
        "fin": libelle_periode(recentes[-1]["periode"], recentes[-1]["periode_type"]),
        "provisoire": any(x["provisoire"] for x in recentes),
    }


def _par_annee(lignes: list[dict], n: int) -> list[dict]:
    """Totaux des années complètes (12 mois ou 4 trimestres publiés)."""
    annees: dict[int, list[float]] = {}
    for x in lignes:
        annees.setdefault(x["annee"], []).append(float(x["valeur"]))
    return [
        {"periode": date(a, 1, 1), "periode_type": "ANNEE", "valeur": sum(v)}
        for a, v in sorted(annees.items())
        if len(v) == n
    ]


def _chomage(conn, niveau: str, code: str) -> dict | None:
    lignes = series.serie(conn, CHOMAGE, niveau, code)
    resume = _derniere_et_un_an(lignes)
    if resume is None:
        return None
    if niveau == "FRANCE":
        metropole = series.serie(conn, CHOMAGE, "FRANCE", "FM") if code == "FR" else []
        courbe = _courbe({"France": lignes, "France métropolitaine": metropole})
        france = None
    else:
        depuis = date(resume["periode"].year - ANNEES_COURBE, 1, 1)
        france_lignes = series.serie(conn, CHOMAGE, "FRANCE", "FR", debut=depuis.year)
        courbe = _courbe({"Ce département": lignes, "France": france_lignes}, depuis)
        france = _a_la_periode(france_lignes, resume["periode"])
    # Les 15-24 ans : moyenne annuelle (série annuelle par âge).
    jeunes = None
    par_age = [
        x
        for x in series.ventilation(conn, "TAUX_CHOMAGE_ANNUEL", niveau, code)
        if x["sexe"] == "T" and x["age_min"] == 15
    ]
    if par_age:
        derniere = par_age[-1]
        jeunes = {"valeur": derniere["valeur"], "annee": derniere["annee"], "france": None}
        if niveau != "FRANCE":
            france_jeunes = series.ventilation(conn, "TAUX_CHOMAGE_ANNUEL", "FRANCE", "FR")
            jeunes["france"] = next(
                (
                    x["valeur"]
                    for x in france_jeunes
                    if x["sexe"] == "T" and x["age_min"] == 15 and x["annee"] == derniere["annee"]
                ),
                None,
            )
    return {"resume": resume, "courbe": courbe, "france": france, "jeunes": jeunes}


def _demandeurs(conn, niveau: str, code: str) -> dict | None:
    abc = series.serie(conn, "DEMANDEURS_EMPLOI", niveau, code)
    resume = _derniere_et_un_an(abc)
    if resume is None:
        return None
    a = series.serie(conn, "DEMANDEURS_EMPLOI_A", niveau, code)
    longue = series.serie(conn, "PART_LONGUE_DUREE", niveau, code)
    return {
        "resume": resume,
        "a": _a_la_periode(a, resume["periode"]),
        "longue_duree": _a_la_periode(longue, resume["periode"]),
        "courbe": _courbe(
            {"Catégories A, B, C": abc, "Catégorie A (sans aucune activité)": a},
            date(2011, 1, 1) if niveau == "DEP" else None,
        ),
    }


def _entreprises(conn, niveau: str, code: str) -> dict | None:
    creations = series.serie(conn, "CREATIONS_ENTREPRISES", niveau, code)
    defaillances = series.serie(conn, "DEFAILLANCES_ENTREPRISES", niveau, code)
    if not creations and not defaillances:
        return None
    cumul_creations = _cumul(creations, 12)
    micro = None
    if cumul_creations:
        micros = [
            x
            for x in series.ventilation(
                conn,
                "CREATIONS_ENTREPRISES",
                niveau,
                code,
                "type_entreprise",
                debut=creations[-1]["annee"] - 1,
            )  # fmt: skip
            if x["modalite"] == "MICRO"
        ]
        recentes = {x["periode"] for x in creations[-12:]}
        somme = sum(float(x["valeur"]) for x in micros if x["periode"] in recentes)
        micro = 100 * somme / cumul_creations["total"] if cumul_creations["total"] else None
    return {
        "creations": cumul_creations,
        "micro": micro,
        "defaillances": _cumul(defaillances, 4),
        "courbe": _courbe(
            {
                "Créations": _par_annee(creations, 12),
                "Défaillances": _par_annee(defaillances, 4),
            }
        ),
    }


def _secteurs(conn, niveau: str, code: str) -> dict | None:
    total = _derniere_et_un_an(series.serie(conn, "EMPLOI_SALARIE", niveau, code))
    if total is None:
        return None
    periode = total["periode"]
    debut = periode.year - 1
    lignes = series.ventilation(conn, "EMPLOI_SALARIE", niveau, code, "secteur", debut=debut)
    par_secteur: dict[str, dict] = {}
    for x in lignes:
        s = par_secteur.setdefault(x["modalite"], {"code": x["modalite"], "libelle": x["libelle"]})
        if x["periode"] == periode:
            s["valeur"] = x["valeur"]
        elif x["periode"] == _un_an_avant(periode):
            s["avant"] = x["valeur"]
    for s in par_secteur.values():
        if s.get("valeur") is not None and s.get("avant") is not None:
            s["ecart"] = float(s["valeur"]) - float(s["avant"])
            s["evolution"] = evolution(s["avant"], s["valeur"])
    return {
        "total": total,
        "secteurs": [par_secteur[c] for c in SECTEURS if c in par_secteur],
        "interim": par_secteur.get(INTERIM),
    }


def _metiers(conn, niveau: str, code: str) -> dict | None:
    total = series.serie(conn, "PROJETS_RECRUTEMENT", niveau, code)
    if not total:
        return None
    annee = total[-1]["annee"]
    part = _a_la_periode(series.serie(conn, "PART_RECRUTEMENTS_DIFFICILES", niveau, code),
                         total[-1]["periode"])  # fmt: skip
    projets = series.ventilation(conn, "PROJETS_RECRUTEMENT", niveau, code, "metier_bmo", annee)
    difficiles = {
        x["modalite"]: x["valeur"]
        for x in series.ventilation(
            conn, "RECRUTEMENTS_DIFFICILES", niveau, code, "metier_bmo", annee
        )
        if x["annee"] == annee
    }
    metiers = []
    for x in projets:
        if x["annee"] != annee or not x["valeur"]:
            continue
        d = difficiles.get(x["modalite"])
        metiers.append(
            {
                "libelle": x["libelle"],
                "projets": x["valeur"],
                "difficiles": d,
                "part": 100 * float(d) / float(x["valeur"]) if d is not None else None,
            }
        )
    metiers.sort(key=lambda m: -m["projets"])
    tension = sorted(
        (m for m in metiers if m["projets"] >= PROJETS_MIN and m["part"] is not None),
        key=lambda m: (-m["part"], -m["projets"]),
    )
    familles = [
        {"code": x["modalite"], "libelle": x["libelle"], "part": x["valeur"]}
        for x in series.ventilation(
            conn, "PART_RECRUTEMENTS_DIFFICILES", niveau, code, "famille_metier", annee
        )
        if x["annee"] == annee
    ]
    familles.sort(key=lambda f: -f["part"])
    return {
        "annee": annee,
        "projets": total[-1]["valeur"],
        "part": part,
        "top": metiers[:10],
        "tension": tension[:5],
        "familles": familles,
    }


def _par_age(conn, indicateur: str, niveau: str, code: str, annee: int) -> list[dict]:
    """Valeurs par tranche d'âge (tous sexes, sans modalité) d'une année."""
    return [
        {"age_min": x["age_min"], "age_max": x["age_max"], "valeur": x["valeur"]}
        for x in series.ventilation(conn, indicateur, niveau, code, debut=annee)
        if x["annee"] == annee and x["sexe"] == "T" and x["modalite"] is None
        and (x["age_min"] is not None or x["age_max"] is not None)
    ]  # fmt: skip


def _par_sexe(conn, indicateur: str, niveau: str, code: str, periode: date) -> dict:
    return {
        sexe: _a_la_periode(series.serie(conn, indicateur, niveau, code, sexe=sexe), periode)
        for sexe in ("F", "H")
    }


def _conditions(conn, niveau: str, code: str) -> dict | None:
    """Contrats courts et temps partiel (recensement), par sexe et âge."""
    resultat = {}
    for indicateur in ("PART_CONTRATS_COURTS", "PART_TEMPS_PARTIEL"):
        lignes = series.serie(conn, indicateur, niveau, code)
        if not lignes:
            continue
        derniere = lignes[-1]
        resultat[indicateur] = {
            "valeur": derniere["valeur"],
            "annee": derniere["annee"],
            "sexes": _par_sexe(conn, indicateur, niveau, code, derniere["periode"]),
            "ages": _par_age(conn, indicateur, niveau, code, derniere["annee"]),
        }
    return resultat or None


def _salaires(conn, niveau: str, code: str) -> dict | None:
    """Salaire net moyen (secteur privé, équivalent temps plein), par sexe, âge et
    catégorie socioprofessionnelle, et l'écart entre femmes et hommes."""
    lignes = series.serie(conn, SALAIRE, niveau, code)
    if not lignes:
        return None
    derniere = lignes[-1]
    avant = lignes[-2] if len(lignes) > 1 else None
    sexes = _par_sexe(conn, SALAIRE, niveau, code, derniere["periode"])
    ecart = None
    if sexes["H"] and sexes["F"] is not None:
        ecart = 100 * (float(sexes["H"]) - float(sexes["F"])) / float(sexes["H"])
    categories = [
        {"libelle": x["libelle"], "valeur": x["valeur"]}
        for x in series.ventilation(conn, SALAIRE, niveau, code, "pcs", derniere["annee"])
        if x["annee"] == derniere["annee"] and x["sexe"] == "T" and x["age_min"] is None
    ]
    return {
        "valeur": derniere["valeur"],
        "annee": derniere["annee"],
        "avant": avant,
        "evolution": evolution(avant["valeur"], derniere["valeur"]) if avant else None,
        "sexes": sexes,
        "ecart": ecart,
        "ages": _par_age(conn, SALAIRE, niveau, code, derniere["annee"]),
        "categories": categories,
    }


def _parts(conn, code: str | None) -> dict[str, dict]:
    """Taux et parts comparables, avec le rang du département (fiche) ou la valeur France."""
    resultat = {}
    for indicateur in (CHOMAGE, "PART_LONGUE_DUREE", "PART_RECRUTEMENTS_DIFFICILES",
                       "PART_INTERIM", "PART_INDEPENDANTS", "PART_CONTRATS_COURTS",
                       "PART_TEMPS_PARTIEL", SALAIRE):  # fmt: skip
        if code is not None:
            rang = _rang(conn, indicateur, code)
            if rang:
                resultat[indicateur] = rang
        else:
            lignes = series.serie(conn, indicateur, "FRANCE", "FR")
            if lignes:
                resultat[indicateur] = {
                    "valeur": lignes[-1]["valeur"],
                    "annee": lignes[-1]["annee"],
                }
    return resultat


def _definitions(conn) -> dict[str, dict]:
    definitions = {i["code"]: i for i in series.indicateurs(conn, rubrique=RUBRIQUE)}
    for code in (CHOMAGE, SALAIRE):  # affichés dans la rubrique, mais d'une autre appli
        definitions.update({i["code"]: i for i in series.indicateurs(conn, code=code)})
    return definitions


def _blocs(conn, niveau: str, code: str) -> dict:
    blocs = {
        "chomage": _chomage(conn, niveau, code),
        "demandeurs": _demandeurs(conn, niveau, code),
        "metiers": _metiers(conn, niveau, code),
        "entreprises": _entreprises(conn, niveau, code),
        "secteurs": _secteurs(conn, niveau, code),
        "conditions": _conditions(conn, niveau, code),
        "salaires": _salaires(conn, niveau, code),
        "parts": _parts(conn, code if niveau == "DEP" else None),
    }
    blocs["avec_donnees"] = any(v for k, v in blocs.items() if k != "parts")
    return blocs


@routeur.get("", response_class=HTMLResponse)
def travail(request: Request, conn: Connexion) -> HTMLResponse:
    tous = territoires.lister(conn)
    departements: dict[str, list[dict]] = {}
    for t in tous:
        if t["niveau"] == "DEP":
            departements.setdefault(t["parent_code"], []).append(t)
    contexte = {
        **_blocs(conn, "FRANCE", "FR"),
        "fiche": None,
        "definitions": _definitions(conn),
        "questions": QUESTIONS,
        "regions": sorted((t for t in tous if t["niveau"] == "REG"), key=lambda t: t["libelle"]),
        "departements": departements,
        "choix": choix_territoire(tous, ("DEP",), "/travail/DEP/{code}"),
        "projets_min": PROJETS_MIN,
    }
    return gabarits.TemplateResponse(request, "travail.html", contexte)


@routeur.get("/DEP/{code}", response_class=HTMLResponse)
def departement(
    request: Request,
    conn: Connexion,
    code: Annotated[str, Chemin(pattern=r"^[0-9][0-9AB][0-9]?$")],
) -> HTMLResponse:
    fiche = territoires.trouver(conn, "DEP", code)
    if fiche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Département inconnu")
    contexte = {
        **_blocs(conn, "DEP", code),
        "fiche": fiche,
        "definitions": _definitions(conn),
        "questions": QUESTIONS,
        "projets_min": PROJETS_MIN,
    }
    return gabarits.TemplateResponse(request, "travail.html", contexte)


@routeur.get("/theme/{theme}", response_class=HTMLResponse)
def theme(
    request: Request,
    conn: Connexion,
    theme: Annotated[str, Chemin(pattern=r"^[a-z-]+$")],
    indicateur: Annotated[str | None, Query(pattern=r"^[A-Z0-9_]+$")] = None,
    famille: Annotated[str | None, Query(pattern=r"^[A-Z]$")] = None,
) -> HTMLResponse:
    if theme not in THEMES_CARTE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thème inconnu")
    code_theme, codes = THEMES_CARTE[theme]
    definitions = _definitions(conn)
    choix = [definitions[c] for c in codes if c in definitions]
    if indicateur is None:
        indicateur = codes[0]
    elif indicateur not in codes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicateur inconnu pour ce thème")
    definition = definitions.get(indicateur)
    if definition is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicateur non importé")
    familles = []
    if indicateur == "PART_RECRUTEMENTS_DIFFICILES":
        familles = [
            {"code": x["modalite"], "libelle": x["libelle"]}
            for x in series.ventilation(conn, indicateur, "FRANCE", "FR", "famille_metier")
        ]
        familles = list({f["code"]: f for f in familles}.values())
        if famille is not None and famille not in {f["code"] for f in familles}:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Famille de métiers inconnue")
    elif famille is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Famille sans objet pour cet indicateur")
    if famille is not None:
        lignes = series.classement_modalite(conn, indicateur, "famille_metier", famille)
    else:
        lignes = series.classement(conn, indicateur)
    avec = [ligne for ligne in lignes if ligne["valeur"] is not None]
    sans = [ligne for ligne in lignes if ligne["valeur"] is None]
    france = None
    if avec and avec[0]["france_code"]:
        france = {"code": avec[0]["france_code"], "valeur": avec[0]["france_valeur"]}
    themes = {
        t["theme"]: t["theme_libelle"]
        for t in series.themes(conn)
        if t["rubrique"] == RUBRIQUE and t["theme"]
    }
    contexte = {
        "theme": {"lien": theme, "titre": themes.get(code_theme, code_theme.title())},
        "themes": [
            {"lien": t, "titre": themes.get(c, c.title())} for t, (c, _) in THEMES_CARTE.items()
        ],
        "choix": choix,
        "definition": definition,
        "familles": familles,
        "famille": next((f for f in familles if f["code"] == famille), None),
        "annee": avec[0]["annee"] if avec else None,
        "france": france,
        "classement": avec,
        "sans_donnee": sans,
        "carte": _carte_coloree(
            lignes, definition["unite"], "/travail/DEP/{code}", format_valeur=valeur
        ),
    }
    return gabarits.TemplateResponse(request, "travail_theme.html", contexte)
