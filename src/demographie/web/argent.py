"""Pages de la rubrique « Où va l'argent public ? » : vue France (chiffres clés, « pour
1 000 € de dépense publique », qui dépense, d'où vient l'argent, déficit et dette dans le
temps) et budget de l'État (solde mois par mois, crédits par mission). Départements, ménage
type et catastrophes naturelles viennent avec les PR suivantes.

Dossier de conception de l'appli, étape 8. Les montants par habitant et en euros constants
sont calculés ici, à l'affichage, à partir de la population et de l'indice des prix déjà
en base."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, Request
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
    ("Mon département", "les dépenses du département et des communes par habitant, poste "
     "par poste, comparées à la moyenne."),
    ("Impôts d'un ménage type", "ce que paie un ménage comme le vôtre, et ce que ses "
     "impôts financent."),
    ("Catastrophes naturelles", "les reconnaissances par année et par péril dans votre "
     "département."),
)  # fmt: skip
# Pages de la rubrique déjà construites : liens en tête de la vue France.
PAGES = (("Le budget de l'État", "/argent-public/etat"),)
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre")  # fmt: skip
MOIS_COURTS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.",
               "oct.", "nov.", "déc.")  # fmt: skip
# Mission qui rend des impôts trop perçus : montrée à part, hors du classement.
DEGREVEMENTS = "REMBOURSEMENTS_ET_DEGREVEMENTS"

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
        "pages": PAGES,
        "donnees": {"historique": historique},
    }
    return gabarits.TemplateResponse(request, "argent.html", contexte)


# --- Budget de l'État -------------------------------------------------------------------


def _mensuel(conn, indicateur: str) -> dict[int, dict[int, float]]:
    """Valeurs mensuelles cumulées : année -> mois -> milliards d'euros."""
    resultat: dict[int, dict[int, float]] = {}
    for x in series.serie(conn, indicateur, "FRANCE", "FR"):
        if x["periode_type"] == "MOIS" and x["valeur"] is not None:
            resultat.setdefault(x["annee"], {})[x["periode"].month] = float(x["valeur"])
    return resultat


def _solde_mensuel(conn) -> dict | None:
    """Solde cumulé de l'année en cours et des deux précédentes, mois par mois, et la
    comparaison à la même date l'an passé."""
    soldes = _mensuel(conn, "SOLDE_ETAT")
    if not soldes:
        return None
    annees = sorted(soldes)[-3:]
    courante = annees[-1]
    mois = max(soldes[courante])
    comparaison = None
    if courante - 1 in soldes and mois in soldes[courante - 1]:
        comparaison = {"annee": courante - 1, "valeur": soldes[courante - 1][mois]}
    return {
        "annee": courante,
        "mois": mois,
        "mois_libelle": MOIS[mois - 1],
        "valeur": soldes[courante][mois],
        "comparaison": comparaison,
        "fins": [
            {"annee": a, "valeur": soldes[a][12]}
            for a in annees
            if a != courante and 12 in soldes[a]
        ],
        "courbe": {
            "mois": list(MOIS_COURTS),
            "series": [
                {"nom": str(a), "valeurs": [soldes[a].get(m) for m in range(1, 13)]} for a in annees
            ],
        },
    }


def _missions(conn, annee: int | None) -> dict | None:
    """Crédits votés et consommés par mission pour une année, du plus gros au plus petit
    consommé, la mission « Remboursements et dégrèvements » à part."""
    votes = series.repartition(conn, "CREDITS_VOTES", "FRANCE", "FR", annee)
    if not votes:
        return None
    consommes = {
        x["modalite"]: x
        for x in series.repartition(conn, "CREDITS_CONSOMMES", "FRANCE", "FR", votes[0]["annee"])
    }
    lignes = []
    for x in votes:
        c = consommes.get(x["modalite"])
        lignes.append({
            "code": x["modalite"],
            "libelle": x["libelle"],
            "vote": float(x["valeur"]),
            "consomme": float(c["valeur"]) if c else None,
        })  # fmt: skip
    degrevements = next((x for x in lignes if x["code"] == DEGREVEMENTS), None)
    lignes = sorted(
        (x for x in lignes if x["code"] != DEGREVEMENTS),
        key=lambda x: -(x["consomme"] if x["consomme"] is not None else x["vote"]),
    )
    vote = sum(x["vote"] for x in lignes)
    consomme = sum(x["consomme"] or 0 for x in lignes)
    for x in lignes:
        x["ecart"] = None if x["consomme"] is None else x["consomme"] - x["vote"]
    return {
        "annee": votes[0]["annee"],
        "lignes": lignes,
        "vote": vote,
        "consomme": consomme,
        "degrevements": degrevements,
        "plus_depasse": max(lignes, key=lambda x: x["ecart"] or 0),
        "plus_sous": min(lignes, key=lambda x: x["ecart"] or 0),
    }


@routeur.get("/etat", response_class=HTMLResponse)
def etat(
    request: Request,
    conn: Connexion,
    annee: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> HTMLResponse:
    definitions = {i["code"]: i for i in series.indicateurs(conn, rubrique=RUBRIQUE)}
    solde = _solde_mensuel(conn)
    annees_missions = sorted(
        {x["annee"] for x in series.serie(conn, "CREDITS_VOTES", "FRANCE", "FR")}
    )
    if annee is not None and annee not in annees_missions:
        annee = None
    missions = _missions(conn, annee)

    impots = None
    recettes = _mensuel(conn, "RECETTES_FISCALES_ETAT")
    completes = sorted(a for a, m in recettes.items() if 12 in m)
    if completes:
        derniere = completes[-1]
        lignes = series.repartition_mensuelle(
            conn, "RECETTES_FISCALES_ETAT", "FRANCE", "FR", date(derniere, 12, 1)
        )
        total = recettes[derniere][12]
        if lignes and total:
            barres = [
                {"libelle": x["libelle"], "valeur": float(x["valeur"]),
                 "part": 100 * float(x["valeur"]) / total}
                for x in sorted(lignes, key=lambda x: -float(x["valeur"]))
            ]  # fmt: skip
            plus_grande = max(b["part"] for b in barres) or 1
            for b in barres:
                b["largeur"] = 100 * b["part"] / plus_grande
            impots = {"annee": derniere, "total": total, "barres": barres}

    contexte = {
        "definitions": definitions,
        "solde": solde,
        "missions": missions,
        "annees_missions": annees_missions,
        "impots": impots,
        "donnees": {
            "solde": solde["courbe"] if solde else None,
            "missions": [
                {"libelle": x["libelle"], "vote": x["vote"], "consomme": x["consomme"]}
                for x in missions["lignes"]
            ]
            if missions
            else None,
        },
    }
    return gabarits.TemplateResponse(request, "argent_etat.html", contexte)
