"""Pages de la rubrique « Où va l'argent public ? » : vue France (chiffres clés, « pour
1 000 € de dépense publique », qui dépense, d'où vient l'argent, déficit et dette dans le
temps), budget de l'État (solde mois par mois, crédits par mission) et collectivités
locales d'un département (département, communes, intercommunalités, par habitant). Ménage
type et catastrophes naturelles viennent avec les PR suivantes.

Dossier de conception de l'appli, étape 8. Les montants par habitant et en euros constants
sont calculés ici, à l'affichage, à partir de la population et de l'indice des prix déjà
en base."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse

from demographie.donnees import series, territoires
from demographie.web.carte import choix_territoire
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


def _population(conn, niveau: str = "FRANCE", code: str = "FR") -> dict[int, float]:
    """Population moyenne de chaque année : moyenne du 1er janvier et du 1er janvier
    suivant, ou le seul 1er janvier connu pour la dernière année."""
    debut = {
        x["annee"]: float(x["valeur"])
        for x in series.serie(conn, "POP", niveau, code)
        if x["valeur"] is not None
    }
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
    tous = territoires.lister(conn)
    departements: dict[str, list[dict]] = {}
    for t in tous:
        if t["niveau"] == "DEP":
            departements.setdefault(t["parent_code"], []).append(t)

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
        "choix": choix_territoire(tous, ("DEP",), "/argent-public/DEP/{code}"),
        "regions": sorted((t for t in tous if t["niveau"] == "REG"), key=lambda t: t["libelle"]),
        "departements": departements,
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


# --- Collectivités locales d'un département ---------------------------------------------

ECHELONS = (
    ("DEPARTEMENT", "Le département"),
    ("COMMUNES", "Les communes"),
    ("INTERCO", "Les intercommunalités"),
)
# Départements publiés ensemble dans une collectivité unique : le premier code porte les
# comptes des deux, l'autre n'en a plus.
UNIQUES = {
    "67": ("67", "68", "la Collectivité européenne d'Alsace"),
    "68": ("67", "68", "la Collectivité européenne d'Alsace"),
    "2A": ("2A", "2B", "la Collectivité de Corse"),
    "2B": ("2A", "2B", "la Collectivité de Corse"),
}
NOTES = {
    "67": "Depuis 2021, le Bas-Rhin et le Haut-Rhin forment la Collectivité européenne "
    "d'Alsace : ses comptes sont publiés ensemble et rapportés aux habitants des deux "
    "départements.",
    "2A": "Depuis 2018, la Collectivité de Corse remplace les deux départements et la "
    "région : ses dépenses comprennent celles d'une région et sont rapportées aux "
    "habitants de toute l'île.",
    "972": "La collectivité territoriale unique exerce aussi les compétences de la région : "
    "ses dépenses sont plus élevées que celles d'un département.",
    "75": "Paris est à la fois une commune et un département : depuis 2019, ses dépenses "
    "départementales sont comptées avec celles des communes.",
    "69": "La Métropole de Lyon exerce les compétences du département sur son territoire : "
    "elle est comptée avec les intercommunalités, et le département du Rhône ne couvre que "
    "le reste.",
}
NOTES |= {"68": NOTES["67"], "2B": NOTES["2A"], "973": NOTES["972"], "976": NOTES["972"]}


def _annuelles(conn, indicateur: str, niveau: str, code: str) -> dict[int, float]:
    return {
        x["annee"]: float(x["valeur"])
        for x in series.serie(conn, indicateur, niveau, code)
        if x["periode_type"] == "ANNEE" and x["valeur"] is not None
    }


def _par_habitant(millions: float | None, habitants: float | None) -> float | None:
    if millions is None or not habitants:
        return None
    return 1e6 * millions / habitants


class _Comptes:
    """Comptes d'un échelon pour un département, par année, rapportés au bon nombre
    d'habitants : pour une collectivité unique, les comptes publiés sous un seul code et
    la population des deux départements."""

    def __init__(self, conn, code: str, populations: dict[str, dict[int, float]]):
        self.conn = conn
        self.code = code
        self.populations = populations

    def habitants(self, codes: tuple[str, ...], annee: int) -> float | None:
        valeurs = [self.populations[c].get(annee) for c in codes]
        return sum(valeurs) if all(valeurs) else None

    def annees(self, indicateur: str) -> dict[int, dict]:
        """Année -> {valeur (M€), code des comptes, codes des habitants, collectivité unique}."""
        resultat = {}
        propres = _annuelles(self.conn, indicateur, "DEP", self.code)
        unique = UNIQUES.get(self.code) if indicateur.endswith("_DEPARTEMENT") else None
        if unique:
            premier, second, nom = unique
            communs = _annuelles(self.conn, indicateur, "DEP", premier)
            seconds = _annuelles(self.conn, indicateur, "DEP", second)
            for a, v in communs.items():
                if a not in seconds:
                    resultat[a] = {"valeur": v, "code": premier, "codes": (premier, second),
                                   "unique": nom}  # fmt: skip
        for a, v in propres.items():
            resultat.setdefault(a, {"valeur": v, "code": self.code, "codes": (self.code,),
                                    "unique": None})  # fmt: skip
        for a, x in resultat.items():
            x["habitants"] = self.habitants(x["codes"], a)
            x["par_habitant"] = _par_habitant(x["valeur"], x["habitants"])
        return resultat


def _postes(conn, indicateur: str, compte: dict, annee: int, habitants_fr: float | None):
    """Postes de dépense par habitant, ici et en France, du plus gros au plus petit."""
    ici = series.repartition(conn, indicateur, "DEP", compte["code"], annee)
    lignes_fr = series.repartition(conn, indicateur, "FRANCE", "FR", annee)
    france = {x["modalite"]: x for x in lignes_fr}
    lignes = []
    for x in ici:
        if x["valeur"] is None:
            continue
        fr = france.get(x["modalite"])
        lignes.append({
            "libelle": x["libelle"],
            "ici": _par_habitant(float(x["valeur"]), compte["habitants"]),
            "france": _par_habitant(float(fr["valeur"]), habitants_fr) if fr else None,
        })  # fmt: skip
    lignes = [x for x in lignes if x["ici"] is not None]
    if not lignes:
        return None
    lignes.sort(key=lambda x: -x["ici"])
    plus_grand = max(max(x["ici"], x["france"] or 0) for x in lignes) or 1
    for x in lignes:
        x["largeur"] = 100 * max(x["ici"], 0) / plus_grand
        x["repere"] = None if x["france"] is None else 100 * max(x["france"], 0) / plus_grand
    return {"annee": annee, "lignes": lignes}


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
    codes = set(UNIQUES.get(code, (code, code))[:2]) | {code}
    comptes = _Comptes(conn, code, {c: _population(conn, "DEP", c) for c in codes})
    population_fr = _population(conn)

    depenses = {e: comptes.annees(f"DEPENSES_{e}") for e, _ in ECHELONS}
    dettes = {e: comptes.annees(f"DETTE_{e}") for e, _ in ECHELONS}
    france = {
        e: (_annuelles(conn, f"DEPENSES_{e}", "FRANCE", "FR"),
            _annuelles(conn, f"DETTE_{e}", "FRANCE", "FR"))
        for e, _ in ECHELONS
    }  # fmt: skip
    annees = sorted({a for d in depenses.values() for a, x in d.items() if x["par_habitant"]})
    contexte = {"fiche": fiche, "definitions": definitions, "note": NOTES.get(code),
                "resume": None, "postes": [], "donnees": {"historique": None}}  # fmt: skip
    if annees:
        annee = annees[-1]
        echelons = []
        for e, libelle in ECHELONS:
            d, t = depenses[e].get(annee), dettes[e].get(annee)
            dep_fr, dette_fr = france[e]
            echelons.append({
                "code": e,
                "libelle": libelle,
                "unique": d["unique"] if d else None,
                "depense": d["par_habitant"] if d else None,
                "dette": t["par_habitant"] if t else None,
                "depense_fr": _par_habitant(dep_fr.get(annee), population_fr.get(annee)),
                "dette_fr": _par_habitant(dette_fr.get(annee), population_fr.get(annee)),
            })  # fmt: skip

        def somme(cle: str) -> float | None:
            valeurs = [x[cle] for x in echelons if x[cle] is not None]
            return sum(valeurs) if valeurs else None

        total, total_fr = somme("depense"), somme("depense_fr")
        contexte["resume"] = {
            "annee": annee,
            "echelons": echelons,
            "total": total,
            "total_fr": total_fr,
            "dette": somme("dette"),
            "dette_fr": somme("dette_fr"),
            "ecart": 100 * (total / total_fr - 1) if total and total_fr else None,
        }
        habitants_fr = population_fr.get(annee)
        for e, titre in (("DEPARTEMENT", "Le département"), ("COMMUNES", "Les communes")):
            compte = depenses[e].get(annee)
            postes = compte and _postes(conn, f"DEPENSES_{e}", compte, annee, habitants_fr)
            if postes:
                postes["titre"] = titre
                postes["unique"] = compte["unique"]
                postes["definition"] = definitions.get(f"DEPENSES_{e}")
                contexte["postes"].append(postes)
        historique = _historique_local(depenses, france, population_fr, _prix(conn))
        contexte["donnees"]["historique"] = historique
    return gabarits.TemplateResponse(request, "argent_departement.html", contexte)


def _historique_local(depenses, france, population_fr, prix) -> dict | None:
    """Dépense des trois échelons par habitant, ici et en France, depuis la première année :
    en euros constants si l'indice des prix couvre toutes les années."""
    annees = sorted(
        a for a in depenses["COMMUNES"]
        if all(depenses[e].get(a, {}).get("par_habitant") for e in ("COMMUNES", "INTERCO"))
    )  # fmt: skip
    if len(annees) < 2:
        return None
    constants = all(a in prix for a in annees)
    base = max(prix) if constants else None

    def euros_de(a: int, v: float | None) -> float | None:
        if v is None:
            return None
        return round(v * prix[base] / prix[a] if constants else v)

    ici, fr = [], []
    for a in annees:
        total = sum(depenses[e].get(a, {}).get("par_habitant") or 0 for e, _ in ECHELONS)
        ici.append(euros_de(a, total))
        total_fr = sum(france[e][0].get(a) or 0 for e, _ in ECHELONS)
        fr.append(euros_de(a, _par_habitant(total_fr, population_fr.get(a))))
    return {"annees": annees, "ici": ici, "france": fr, "base_prix": base}
