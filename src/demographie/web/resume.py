"""Résumé « Qui sont les Français ? » de la page d'accueil, France entière.

Six blocs, chacun avec une phrase, quelques chiffres et des barres. Un bloc dont les
données ne sont pas encore importées est simplement absent.
"""

from decimal import Decimal

import psycopg

from demographie.donnees import series

FR = ("FRANCE", "FR")

# Statut d'activité des 15 ans ou plus (recensement) : modalités qui forment le total.
ACTIVITE = (
    ("ACTIF_OCCUPE", "En emploi"),
    ("CHOMEUR", "Au chômage"),
    ("RETRAITE", "Retraités"),
    ("ETUDIANT", "Élèves et étudiants"),
)
# Catégories socioprofessionnelles des personnes qui travaillent ou ont travaillé.
PCS_ACTIVES = (
    "AGRICULTEURS",
    "ARTISANS_COMMERCANTS",
    "CADRES",
    "PROF_INTERMEDIAIRES",
    "EMPLOYES",
    "OUVRIERS",
)
PCS_COURTS = {
    "AGRICULTEURS": "Agriculteurs",
    "ARTISANS_COMMERCANTS": "Artisans, commerçants, chefs d'entreprise",
    "CADRES": "Cadres",
    "PROF_INTERMEDIAIRES": "Professions intermédiaires",
    "EMPLOYES": "Employés",
    "OUVRIERS": "Ouvriers",
}
SANTE_AFFICHEES = 10
# Groupes qui ne sont pas des maladies : écartés de la phrase du bloc santé.
SOINS_ET_TRAITEMENTS = {
    "AUCUNE",
    "HOSPITALISATIONS",
    "RISQUE_VASCULAIRE",
    "PSYCHOTROPES",
    "ANTALGIQUES",
}


def _f(valeur: Decimal | int | float | None) -> float | None:
    return None if valeur is None else float(valeur)


def _sans_precision(libelle: str) -> str:
    """« Maladies respiratoires chroniques (dont asthme) » -> sans la parenthèse."""
    return libelle.split(" (")[0]


def _barres(elements: list[tuple[str, float]], total: float) -> list[dict]:
    """Libellé, part en % du total et largeur relative à la plus grande barre."""
    if not elements or not total:
        return []
    plus_grande = max(v for _, v in elements) or 1
    return [
        {"libelle": libelle, "valeur": v, "part": 100 * v / total, "largeur": 100 * v / plus_grande}
        for libelle, v in elements
    ]


def _repartition(conn, indicateur: str, age_min=None, age_max=None) -> tuple[list[dict], dict]:
    lignes = [
        r
        for r in series.repartition(conn, indicateur, *FR)
        if r["age_min"] == age_min and r["age_max"] == age_max
    ]
    entete = {"annee": lignes[0]["annee"], "total": _f(lignes[0]["total"])} if lignes else {}
    return lignes, entete


def _combien(cles: dict) -> dict | None:
    if "POP" not in cles:
        return None
    bloc = {
        "titre": "Combien sommes-nous ?",
        "population": _f(cles["POP"]["valeur"]),
        "annee": cles["POP"]["annee"],
        "provisoire": cles["POP"]["provisoire"],
        "lien": "/territoire/FRANCE/FR",
    }
    if "NAISSANCES" in cles and "DECES" in cles:
        bloc["naissances"] = _f(cles["NAISSANCES"]["valeur"])
        bloc["deces"] = _f(cles["DECES"]["valeur"])
        bloc["annee_flux"] = cles["NAISSANCES"]["annee"]
    return bloc


def _age(cles: dict) -> dict | None:
    codes = ("PART_MOINS_20", "PART_60_PLUS", "PART_75_PLUS")
    if not all(c in cles for c in codes):
        return None
    return {
        "titre": "Quel âge avons-nous ?",
        "annee": cles["PART_60_PLUS"]["annee"],
        "moins_20": _f(cles["PART_MOINS_20"]["valeur"]),
        "plus_60": _f(cles["PART_60_PLUS"]["valeur"]),
        "plus_75": _f(cles["PART_75_PLUS"]["valeur"]),
        "lien": "/territoire/FRANCE/FR",
    }


def _activite(conn, cles: dict) -> dict | None:
    lignes, entete = _repartition(conn, "POP_RP", age_min=15)
    valeurs = {r["modalite"]: _f(r["valeur"]) for r in lignes}
    if not entete.get("total") or not all(m in valeurs for m, _ in ACTIVITE):
        return None
    elements = [(libelle, valeurs[m]) for m, libelle in ACTIVITE]
    autres = entete["total"] - sum(v for _, v in elements)
    elements.append(("Autres sans activité (au foyer, invalidité…)", max(autres, 0)))
    bloc = {"titre": "Que faisons-nous ?", **entete, "barres": _barres(elements, entete["total"])}
    if "TAUX_CHOMAGE" in cles:
        bloc["chomage"] = _f(cles["TAUX_CHOMAGE"]["valeur"])
        bloc["annee_chomage"] = cles["TAUX_CHOMAGE"]["annee"]
    return bloc


def _metiers(conn) -> dict | None:
    lignes, entete = _repartition(conn, "POP_PCS", age_min=15)
    valeurs = {r["modalite"]: _f(r["valeur"]) for r in lignes if r["modalite"] in PCS_ACTIVES}
    if len(valeurs) != len(PCS_ACTIVES):
        return None
    actifs = sum(valeurs.values())
    bloc = {
        "titre": "Quels métiers ?",
        "annee": entete["annee"],
        "actifs": actifs,
        "barres": _barres([(PCS_COURTS[m], valeurs[m]) for m in PCS_ACTIVES], actifs),
    }
    secteurs, entete_secteurs = _repartition(conn, "EMPLOIS_RP", age_min=15)
    if secteurs and entete_secteurs.get("total"):
        bloc["secteurs"] = _barres(
            sorted(((r["libelle"], _f(r["valeur"])) for r in secteurs), key=lambda e: -e[1]),
            entete_secteurs["total"],
        )
    return bloc


def _etudes(conn) -> dict | None:
    lignes, entete = _repartition(conn, "ETUDIANTS")
    if not lignes or not entete.get("total"):
        return None
    formations = sorted(((r["libelle"], _f(r["valeur"])) for r in lignes), key=lambda e: -e[1])
    bloc = {
        "titre": "Qu'étudions-nous ?",
        **entete,
        "barres": _barres(formations, entete["total"]),
    }
    disciplines, entete_univ = _repartition(conn, "ETUDIANTS_UNIVERSITE")
    if disciplines and entete_univ.get("total"):
        bloc["disciplines"] = _barres(
            sorted(((r["libelle"], _f(r["valeur"])) for r in disciplines), key=lambda e: -e[1]),
            entete_univ["total"],
        )
        bloc["annee_univ"] = entete_univ["annee"]
        bloc["total_univ"] = entete_univ["total"]
    return bloc


def _sante(conn) -> dict | None:
    lignes, entete = _repartition(conn, "PATIENTS_PATHOLOGIE")
    if not lignes or not entete.get("total"):
        return None
    aucune = next((_f(r["valeur"]) for r in lignes if r["modalite"] == "AUCUNE"), None)
    groupes = sorted(
        ((r["libelle"], _f(r["valeur"])) for r in lignes if r["modalite"] != "AUCUNE"),
        key=lambda e: -e[1],
    )
    maladies = sorted(
        (r for r in lignes if r["modalite"] not in SOINS_ET_TRAITEMENTS),
        key=lambda r: -r["valeur"],
    )
    # Largeurs relatives au groupe le plus fréquent, y compris pour les groupes repliés.
    barres = _barres(groupes, entete["total"])
    return {
        "titre": "De quoi souffrons-nous ?",
        **entete,
        "aucune": None if aucune is None else 100 * aucune / entete["total"],
        "barres": barres[:SANTE_AFFICHEES],
        "reste": barres[SANTE_AFFICHEES:],
        "maladies": [
            {
                "libelle": _sans_precision(r["libelle"]),
                "part": 100 * _f(r["valeur"]) / entete["total"],
            }
            for r in maladies[:2]
        ],
    }


def resume(conn: psycopg.Connection) -> dict:
    cles = series.chiffres_cles(conn, *FR)
    return {
        "combien": _combien(cles),
        "age": _age(cles),
        "activite": _activite(conn, cles),
        "metiers": _metiers(conn),
        "etudes": _etudes(conn),
        "sante": _sante(conn),
    }
