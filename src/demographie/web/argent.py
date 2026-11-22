"""Pages de la rubrique « Où va l'argent public ? » : vue France (chiffres clés, « pour
1 000 € de dépense publique », qui dépense, d'où vient l'argent, déficit et dette dans le
temps). Budget de l'État, départements, ménage type et catastrophes naturelles viennent
avec les PR suivantes.

Dossier de conception de l'appli, étape 8. Les montants par habitant et en euros constants
sont calculés ici, à l'affichage, à partir de la population et de l'indice des prix déjà
en base."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from demographie.donnees import series
from demographie.web.pages import Connexion, _decimal_fr, gabarits

routeur = APIRouter(prefix="/argent-public", include_in_schema=False)

RUBRIQUE = "ARGENT"
# Questions guidées de la vue France ; les autres arrivent avec leurs pages.
QUESTIONS = (
    ("Sur 1 000 € de dépense publique, combien vont aux retraites, à la santé et à "
     "l'école ?", "#mille-euros"),
    ("La dette a-t-elle augmenté plus vite que la richesse produite ?", "#dette"),
    ("Que coûtent les intérêts de la dette par rapport à la défense ou à l'enseignement ?",
     "#interets"),
)  # fmt: skip
A_VENIR = (
    ("Budget de l'État", "le solde mois par mois et les crédits de chaque mission."),
    ("Mon département", "les dépenses du département et des communes par habitant, poste "
     "par poste, comparées à la moyenne."),
    ("Impôts d'un ménage type", "ce que paie un ménage comme le vôtre, et ce que ses "
     "impôts financent."),
    ("Catastrophes naturelles", "les reconnaissances par année et par péril dans votre "
     "département."),
)  # fmt: skip
# Libellés courts des recettes, dans l'ordre d'affichage.
RECETTES = {
    "COTISATIONS": ("Cotisations sociales", "de cotisations sociales"),
    "PRODUCTION": ("TVA et impôts sur la production", "de TVA et d'impôts sur la production"),
    "REVENU_PATRIMOINE": (
        "Impôts sur le revenu et le patrimoine (dont CSG)",
        "d'impôts sur le revenu et le patrimoine",
    ),
    "AUTRES": ("Autres recettes", "d'autres recettes"),
}
ETAGES = {
    "SECU": "Sécurité sociale",
    "CENTRALE": "État et organismes nationaux",
    "LOCALE": "Collectivités locales",
}


def milliards(valeur) -> str:
    """1714.1117 -> « 1 714 Md€ » ; 65.72 -> « 65,7 Md€ »."""
    v = float(valeur)
    return f"{_decimal_fr(v, 0 if abs(v) >= 100 else 1)} Md€"


def euros(valeur) -> str:
    """24 987.4 -> « 24 987 € »."""
    return f"{_decimal_fr(float(valeur), 0)} €"


gabarits.env.filters.update(milliards=milliards, euros=euros)


def _par_annee(lignes: list[dict]) -> dict[int, dict]:
    return {x["annee"]: x for x in lignes if x["valeur"] is not None}


def _population(conn) -> dict[int, float]:
    """Population moyenne de chaque année : moyenne du 1er janvier et du 1er janvier
    suivant, ou le seul 1er janvier connu pour la dernière année."""
    debut = {x["annee"]: float(x["valeur"]) for x in series.serie(conn, "POP", "FRANCE", "FR")}
    return {a: (p + debut[a + 1]) / 2 if a + 1 in debut else p for a, p in debut.items()}


def _prix(conn) -> dict[int, float]:
    """Indice des prix moyen de chaque année complète (douze mois publiés)."""
    mois: dict[int, list[float]] = {}
    for x in series.serie(conn, "IPC", "FRANCE", "FR"):
        if x["periode_type"] == "MOIS" and x["valeur"] is not None:
            mois.setdefault(x["annee"], []).append(float(x["valeur"]))
    return {a: sum(v) / len(v) for a, v in mois.items() if len(v) == 12}


def _barres(lignes: list[dict], libelles: dict[str, str] | None = None) -> dict | None:
    """Parts de chaque modalité dans le total, triées de la plus grosse à la plus petite,
    et leur montant pour 1 000 €."""
    lignes = [x for x in lignes if x["valeur"] is not None and x["total"]]
    if not lignes:
        return None
    total = float(lignes[0]["total"])
    barres = sorted(
        (
            {
                "code": x["modalite"],
                "libelle": (libelles or {}).get(x["modalite"], x["libelle"]),
                "valeur": float(x["valeur"]),
                "part": 100 * float(x["valeur"]) / total,
                "pour_mille": 1000 * float(x["valeur"]) / total,
            }
            for x in lignes
        ),
        key=lambda b: -b["valeur"],
    )
    plus_grande = max(b["part"] for b in barres) or 1
    for b in barres:
        b["largeur"] = 100 * b["part"] / plus_grande
    return {
        "annee": lignes[0]["annee"],
        "provisoire": lignes[0]["provisoire"],
        "total": total,
        "barres": barres,
        "par_code": {b["code"]: b for b in barres},
    }


def _recettes(conn, depenses: dict[int, dict]) -> dict | None:
    """D'où vient l'argent : chaque nature de recette et l'emprunt (le déficit), en part
    de la dépense de la même année."""
    lignes = series.repartition(conn, "RECETTE_NATURE", "FRANCE", "FR")
    lignes = [x for x in lignes if x["valeur"] is not None]
    if not lignes or lignes[0]["annee"] not in depenses:
        return None
    annee = lignes[0]["annee"]
    depense = float(depenses[annee]["valeur"])
    connues = sorted(
        (x for x in lignes if x["modalite"] in RECETTES),
        key=lambda x: list(RECETTES).index(x["modalite"]),
    )
    parts = [
        {"libelle": RECETTES[x["modalite"]][0], "phrase": RECETTES[x["modalite"]][1],
         "valeur": float(x["valeur"])}
        for x in connues
    ]  # fmt: skip
    recettes = sum(p["valeur"] for p in parts)
    if depense > recettes:
        parts.append({"libelle": "Emprunt (le déficit)", "valeur": depense - recettes,
                      "emprunt": True})  # fmt: skip
    for p in parts:
        p["part"] = 100 * p["valeur"] / depense
        p["pour_mille"] = 1000 * p["valeur"] / depense
    plus_grande = max(p["part"] for p in parts) or 1
    for p in parts:
        p["largeur"] = 100 * p["part"] / plus_grande
    return {"annee": annee, "provisoire": lignes[0]["provisoire"], "barres": parts}


def _dette_trimestrielle(conn) -> dict | None:
    lignes = {
        code: [
            x
            for x in series.serie(conn, code, "FRANCE", "FR")
            if x["periode_type"] == "TRIMESTRE" and x["valeur"] is not None
        ]
        for code in ("DETTE_TRIMESTRIELLE", "DETTE_TRIMESTRIELLE_PIB")
    }
    if not lignes["DETTE_TRIMESTRIELLE"]:
        return None
    derniere = lignes["DETTE_TRIMESTRIELLE"][-1]
    pib = {x["periode"]: x for x in lignes["DETTE_TRIMESTRIELLE_PIB"]}.get(derniere["periode"])
    trimestre = (derniere["periode"].month + 2) // 3
    return {
        "valeur": float(derniere["valeur"]),
        "pib": float(pib["valeur"]) if pib else None,
        "periode": f"{'1er' if trimestre == 1 else f'{trimestre}e'} trimestre "
        f"{derniere['periode'].year}",
        "annee": derniere["periode"].year,
    }


def _historique(valeurs: dict[str, dict[int, dict]], prix: dict[int, float]) -> dict | None:
    """Déficit et dette en % du PIB depuis la première année commune, et la dette en
    milliards d'euros de l'époque et en euros constants de la dernière année des prix."""
    dette, solde = valeurs.get("DETTE_APU_PIB", {}), valeurs.get("SOLDE_APU_PIB", {})
    annees = sorted(set(dette) & set(solde))
    if not annees:
        return None
    milliards_epoque = valeurs.get("DETTE_APU", {})
    base = max((a for a in prix if a <= annees[-1]), default=None)
    constants = None
    if base is not None:
        constants = [
            round(float(milliards_epoque[a]["valeur"]) * prix[base] / prix[a], 1)
            if a in milliards_epoque and a in prix
            else None
            for a in annees
        ]
    return {
        "annees": annees,
        "dette_pib": [float(dette[a]["valeur"]) for a in annees],
        "solde_pib": [float(solde[a]["valeur"]) for a in annees],
        "dette_courants": [
            float(milliards_epoque[a]["valeur"]) if a in milliards_epoque else None for a in annees
        ],
        "dette_constants": constants,
        "base_prix": base,
    }


def _comparaison_dette(dette: dict[int, dict], pib_dette: dict[int, dict]) -> dict | None:
    """La dette a-t-elle crû plus vite que le PIB ? Multiplication de la dette et du PIB
    (déduit du ratio) depuis la première année connue."""
    annees = sorted(set(dette) & set(pib_dette))
    if len(annees) < 2:
        return None
    debut, fin = annees[0], annees[-1]

    def pib(a: int) -> float:
        return 100 * float(dette[a]["valeur"]) / float(pib_dette[a]["valeur"])

    return {
        "debut": debut,
        "fin": fin,
        "dette": float(dette[fin]["valeur"]) / float(dette[debut]["valeur"]),
        "pib": pib(fin) / pib(debut),
        "ratio_debut": float(pib_dette[debut]["valeur"]),
        "ratio_fin": float(pib_dette[fin]["valeur"]),
    }


@routeur.get("", response_class=HTMLResponse)
def argent(request: Request, conn: Connexion) -> HTMLResponse:
    definitions = {i["code"]: i for i in series.indicateurs(conn, rubrique=RUBRIQUE)}
    valeurs = {
        code: _par_annee(lignes)
        for code, lignes in series.series_rubrique(conn, RUBRIQUE, "FRANCE", "FR").items()
    }
    population = _population(conn)
    prix = _prix(conn)

    def derniere(code: str) -> dict | None:
        serie = valeurs.get(code)
        return serie[max(serie)] if serie else None

    depense = derniere("DEPENSES_APU")
    cles = None
    if depense:
        annee = depense["annee"]
        pib = valeurs.get("DEPENSES_APU_PIB", {}).get(annee)
        solde = valeurs.get("SOLDE_APU", {}).get(annee)
        solde_pib = valeurs.get("SOLDE_APU_PIB", {}).get(annee)
        habitants = population.get(annee)
        cles = {
            "annee": annee,
            "provisoire": depense["provisoire"],
            "depense": float(depense["valeur"]),
            "depense_pib": float(pib["valeur"]) if pib else None,
            "par_habitant": 1e9 * float(depense["valeur"]) / habitants if habitants else None,
            "solde": float(solde["valeur"]) if solde else None,
            "solde_pib": float(solde_pib["valeur"]) if solde_pib else None,
        }
    dette = _dette_trimestrielle(conn)
    if dette:
        habitants = population.get(dette["annee"]) or (
            population[max(population)] if population else None
        )
        dette["par_habitant"] = 1e9 * dette["valeur"] / habitants if habitants else None

    fonctions = _barres(series.repartition(conn, "DEPENSE_FONCTION", "FRANCE", "FR"))
    etages = _barres(series.repartition(conn, "DEPENSE_ETAGE", "FRANCE", "FR"), ETAGES)
    recettes = _recettes(conn, valeurs.get("DEPENSES_APU", {}))
    historique = _historique(valeurs, prix)
    croissance = _comparaison_dette(valeurs.get("DETTE_APU", {}), valeurs.get("DETTE_APU_PIB", {}))

    interets = derniere("CHARGE_INTERETS")
    comparaison_interets = None
    if interets and fonctions:
        annee = fonctions["annee"]
        meme_annee = valeurs.get("CHARGE_INTERETS", {}).get(annee)
        if meme_annee:
            comparaison_interets = {
                "annee": annee,
                "interets": float(meme_annee["valeur"]),
                "fonctions": [
                    fonctions["par_code"][c] for c in ("DEFENSE", "ENSEIGNEMENT")
                    if c in fonctions["par_code"]
                ],
            }  # fmt: skip
    interets_resume = None
    if interets:
        habitants = population.get(interets["annee"])
        interets_resume = {
            "annee": interets["annee"],
            "valeur": float(interets["valeur"]),
            "par_habitant": 1e9 * float(interets["valeur"]) / habitants if habitants else None,
            "provisoire": interets["provisoire"],
        }
    prelevements = derniere("PRELEVEMENTS_PIB")

    contexte = {
        "definitions": definitions,
        "cles": cles,
        "dette": dette,
        "fonctions": fonctions,
        "etages": etages,
        "recettes": recettes,
        "historique": historique,
        "croissance": croissance,
        "interets": interets_resume,
        "comparaison_interets": comparaison_interets,
        "prelevements": prelevements,
        "questions": QUESTIONS,
        "a_venir": A_VENIR,
        "donnees": {"historique": historique},
    }
    return gabarits.TemplateResponse(request, "argent.html", contexte)
