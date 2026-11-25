"""Pages de la rubrique « Comment vivent les Français ? » (appli 3) : vue France (quatre
chiffres en tête, puis un bloc par thème avec les courbes depuis 1996 et la carte pour
choisir un département), fiche département (les mêmes blocs, comparés à la France, avec le
rang du département) et carte colorée par thème.

Les six questions guidées ont chacune leur bloc ; une réponse est une phrase à modèle fixe,
avec un graphique et la source. Dossier de conception de l'appli 3, étapes 7 et 8."""

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

routeur = APIRouter(prefix="/vivre", include_in_schema=False)

RUBRIQUE = "VIVRE"
# Première année proposée pour « le pouvoir d'achat a-t-il augmenté depuis… ? » et année
# choisie par défaut.
DEPUIS_MIN, DEPUIS_DEFAUT = 1996, 2000
# Les parts du revenu disponible (Filosofi), dans l'ordre d'affichage. Les revenus
# d'activité comprennent les salaires ; les prestations sociales, les minima sociaux et
# les aides au logement. Les impôts directs viennent en moins.
PARTS_REVENU = (
    ("PART_REVENUS_ACTIVITE", "Revenus d'activité"),
    ("PART_PENSIONS", "Pensions et retraites"),
    ("PART_CHOMAGE", "Indemnités de chômage"),
    ("PART_REVENUS_PATRIMOINE", "Revenus du patrimoine"),
    ("PART_PRESTATIONS", "Prestations sociales"),
)
# Familles de dettes des ménages surendettés (enquête typologique), dans l'ordre affiché.
TYPES_DETTE = ("CONSOMMATION", "IMMOBILIER", "CHARGES_COURANTES")
# Cartes par thème : adresse -> (titre, indicateurs comparables entre départements). On
# compare des niveaux, des parts et des taux : un nombre brut ne dirait que la taille.
THEMES_CARTE = {
    "revenus": (
        "Revenus",
        ("NIVEAU_VIE_MEDIAN", "SALAIRE_NET_MOYEN", "ECART_SALAIRE_FEMMES_HOMMES"),
    ),
    "inegalites": (
        "Inégalités",
        (
            "RAPPORT_D9_D1",
            "NIVEAU_VIE_D9",
            "NIVEAU_VIE_D1",
            "TAUX_PAUVRETE",
            "INDICE_GINI",
            "RAPPORT_S80_S20",
        ),
    ),
    "aides-logement": (
        "RSA et aides au logement",
        (
            "FOYERS_RSA_POUR_1000",
            "AIDE_LOGEMENT_MOYENNE",
            "PART_AIDES_LOGEMENT",
            "PART_MINIMA_SOCIAUX",
        ),
    ),  # fmt: skip
    "surendettement": ("Surendettement", ("SURENDETTEMENT_POUR_100000", "ENDETTEMENT_MEDIAN")),
    "retraites": ("Retraites", ("PART_PENSIONS", "TAUX_MIN_VIEILLESSE_60P")),
}
QUESTIONS = (
    ("Combien gagne-t-on ici par rapport à la France ?", "revenus"),
    ("Quel est l'écart de salaire entre femmes et hommes dans ma catégorie ?", "salaires"),
    ("Le pouvoir d'achat a-t-il augmenté depuis telle année ?", "pouvoir-achat"),
    ("À partir de quel revenu fait-on partie des 10 % les plus aisés ?", "inegalites"),
    ("D'où vient le revenu des habitants ?", "parts-revenu"),
    ("Combien de foyers touchent le RSA ou une aide au logement ?", "aides"),
)
# Calcul fait par la page (le reste vient de la base) : foyers aidés pour le logement
# rapportés à la population, comme les foyers au RSA de la vue stat.vivre_derives.
FORMULE_AL_POUR_1000 = (
    "calcul On épluche : 1 000 × foyers aidés en décembre / population au 1er janvier suivant"
)


def montant(v: Decimal | float | int | None, unite: str) -> str:
    """Valeur avec son unité : « 23 210 € », « 17,9 % », « +0,7 % » (évolution), « 3,4 »
    (rapport), « 0,297 » (Gini), « 38,5 ‰ », « 152 pour 100 000 », « 1 877 milliards € » ;
    « — » sans valeur."""
    if v is None:
        return "—"
    x = float(v)
    if unite == "evolution":
        return ("+" if x > 0 else "−" if x < 0 else "") + f"{_decimal_fr(abs(x), 1)}\u00a0%"
    if unite == "euros":
        return f"{_decimal_fr(x, 0)} €"
    if unite == "millions_euros":
        return f"{_decimal_fr(x / 1000, 0)} milliards €"
    if unite == "pourcentage":
        return f"{_decimal_fr(x, 1)} %"
    if unite == "ratio":
        return _decimal_fr(x, 3 if abs(x) < 1 else 1)
    if unite == "pour_mille":
        return f"{_decimal_fr(x, 1)} ‰"
    if unite == "pour_100000":
        return f"{_decimal_fr(x, 0)} pour 100 000"
    return _decimal_fr(x, 0)


def ecart_signe(v: float | None, unite: str) -> str:
    """Écart à la France : « +1 250 € », « −2,3 points », « +0,4 » ; « — » sans valeur."""
    if v is None:
        return "—"
    if unite == "pourcentage":
        texte = f"{_decimal_fr(abs(v), 1)} point" + ("s" if round(abs(v), 1) >= 2 else "")
    else:
        texte = montant(abs(v), unite)
    return ("+" if v > 0 else "−" if v < 0 else "") + texte


# « vivre_valeur » : le filtre « montant » appartient déjà aux programmes.
gabarits.env.filters.update(vivre_valeur=montant, ecart_signe=ecart_signe)


def _nombre(v) -> float | None:
    return None if v is None else float(v)


def _derniere(conn, indicateur: str, niveau: str, code: str, sexe: str = "T") -> dict | None:
    lignes = series.serie(conn, indicateur, niveau, code, sexe=sexe)
    return lignes[-1] if lignes else None


def _france(conn, indicateur: str, periode: date | None = None) -> dict | None:
    """Valeur France (France entière si publiée, sinon métropole), à la période donnée ou
    la dernière ; avec ``code`` FR ou FM."""
    for code in ("FR", "FM"):
        lignes = series.serie(conn, indicateur, "FRANCE", code)
        if periode is not None:
            lignes = [x for x in lignes if x["periode"] == periode]
        if lignes:
            return {**lignes[-1], "code": code}
    return None


def _local(conn, indicateur: str, niveau: str, code: str) -> dict | None:
    """Dernière valeur ici (France : FR ou FM) et la valeur France de la même période."""
    if niveau == "FRANCE":
        france = _france(conn, indicateur)
        return {**france, "france": None} if france else None
    derniere = _derniere(conn, indicateur, niveau, code)
    if derniere is None:
        return None
    return {**derniere, "code": code, "france": _france(conn, indicateur, derniere["periode"])}


def _rangs(conn, code: str | None) -> dict[str, dict]:
    return series.rangs(conn, RUBRIQUE, code) if code else {}


def _courbe(par_nom: dict[str, list[dict]]) -> dict | None:
    """Courbes annuelles alignées : {annees: [...], series: [{nom, valeurs}]}."""
    par_nom = {nom: lignes for nom, lignes in par_nom.items() if lignes}
    if not par_nom:
        return None
    annees = sorted({x["annee"] for lignes in par_nom.values() for x in lignes})
    return {
        "annees": annees,
        "series": [
            {
                "nom": nom,
                "valeurs": [
                    next((_nombre(x["valeur"]) for x in lignes if x["annee"] == a), None)
                    for a in annees
                ],
            }
            for nom, lignes in par_nom.items()
        ],
    }


def _barres(elements: list[dict]) -> list[dict]:
    """Ajoute la largeur (en % de la plus grande valeur) à chaque élément {libelle, valeur}."""
    plus_grande = max((abs(float(e["valeur"])) for e in elements), default=0) or 1
    return [{**e, "largeur": 100 * abs(float(e["valeur"])) / plus_grande} for e in elements]


def _par_age(conn, indicateur: str, niveau: str, code: str, annee: int) -> list[dict]:
    return [
        {"age_min": x["age_min"], "age_max": x["age_max"], "valeur": x["valeur"]}
        for x in series.ventilation(conn, indicateur, niveau, code, debut=annee)
        if x["annee"] == annee and x["sexe"] == "T" and x["modalite"] is None
        and (x["age_min"] is not None or x["age_max"] is not None)
    ]  # fmt: skip


def _modalites(conn, indicateur: str, niveau: str, code: str, dimension: str, periode: date):
    return [
        x
        for x in series.ventilation(conn, indicateur, niveau, code, dimension, periode.year)
        if x["periode"] == periode and x["sexe"] == "T" and x["age_min"] is None
    ]


# --- Blocs ------------------------------------------------------------------------------


def _revenus(conn, niveau: str, code: str) -> dict | None:
    """Question 1 : niveau de vie médian et salaire moyen, comparés à la France ; niveau de
    vie par tranche d'âge ; salaire moyen du privé depuis 1996 (France)."""
    niveau_vie = _local(conn, "NIVEAU_VIE_MEDIAN", niveau, code)
    salaire = _local(conn, "SALAIRE_NET_MOYEN", niveau, code)
    if niveau_vie is None and salaire is None:
        return None
    ici = "FM" if niveau == "FRANCE" and niveau_vie else code
    ages = (
        _par_age(conn, "NIVEAU_VIE_MEDIAN", niveau, ici, niveau_vie["annee"]) if niveau_vie else []
    )
    serie = series.serie(conn, "SALAIRE_PRIVE_SERIE", "FRANCE", "FR")
    return {
        "niveau_vie": niveau_vie,
        "salaire": salaire,
        "ages": ages,
        "courbe_salaire": _courbe({"": serie}) if niveau == "FRANCE" else None,
        "salaire_1996": serie[0] if serie else None,
        "salaire_serie": serie[-1] if serie else None,
    }


def _salaires(conn, niveau: str, code: str, categorie: str | None) -> dict | None:
    """Question 2 : salaire des femmes et des hommes par catégorie socioprofessionnelle."""
    ici = "FR" if niveau == "FRANCE" else code
    derniere = _derniere(conn, "SALAIRE_NET_MOYEN", niveau, ici)
    if derniere is None:
        return None
    lignes = [
        x
        for x in series.ventilation(
            conn, "SALAIRE_NET_MOYEN", niveau, ici, "pcs", derniere["annee"]
        )
        if x["periode"] == derniere["periode"] and x["age_min"] is None
    ]
    categories: dict[str, dict] = {}
    for x in lignes:
        c = categories.setdefault(x["modalite"], {"code": x["modalite"], "libelle": x["libelle"]})
        c[x["sexe"]] = x["valeur"]
    for c in categories.values():
        h, f = c.get("H"), c.get("F")
        c["ecart"] = 100 * (float(h) - float(f)) / float(h) if h and f is not None else None
    liste = [c for c in categories.values() if c["ecart"] is not None]
    choisie = next((c for c in liste if c["code"] == categorie), liste[0] if liste else None)
    ensemble = {
        sexe: (_derniere(conn, "SALAIRE_NET_MOYEN", niveau, ici, sexe) or {}).get("valeur")
        for sexe in ("F", "H")
    }
    ecart = _derniere(conn, "ECART_SALAIRE_FEMMES_HOMMES", niveau, ici)
    return {
        "annee": derniere["annee"],
        "categories": liste,
        "choisie": choisie,
        "ensemble": ensemble,
        "ecart": ecart["valeur"] if ecart else None,
        "france": _france(conn, "ECART_SALAIRE_FEMMES_HOMMES", derniere["periode"])
        if niveau != "FRANCE"
        else None,
    }


def _pouvoir_achat(conn, depuis: int) -> dict | None:
    """Question 3 (France) : évolution cumulée du pouvoir d'achat par unité de consommation
    depuis l'année choisie, à partir des évolutions annuelles des comptes nationaux."""
    lignes = series.serie(conn, "POUVOIR_ACHAT_UC", "FRANCE", "FR")
    # Seules les années suivies sans trou jusqu'à la dernière se cumulent.
    while len(lignes) > 1 and any(
        b["annee"] != a["annee"] + 1 for a, b in zip(lignes, lignes[1:], strict=False)
    ):
        lignes = lignes[1:]
    if not lignes:
        return None
    annees = [x["annee"] for x in lignes]
    choix = list(range(annees[0] - 1, annees[-1]))
    if depuis not in choix:
        depuis = DEPUIS_DEFAUT if DEPUIS_DEFAUT in choix else choix[0]
    indice = 1.0
    for x in lignes:
        if x["annee"] > depuis:
            indice *= 1 + float(x["valeur"]) / 100
    n = annees[-1] - depuis
    return {
        "depuis": depuis,
        "jusqu_a": annees[-1],
        "cumul": 100 * (indice - 1),
        "par_an": 100 * (indice ** (1 / n) - 1),
        "derniere": lignes[-1],
        "provisoires": [x["annee"] for x in lignes if x["provisoire"] and x["annee"] > depuis],
        "choix": choix,
        "courbe": _courbe({"": series.serie(conn, "POUVOIR_ACHAT_UC", "FRANCE", "FR")}),
        "revenu": _france(conn, "REVENU_DISPONIBLE"),
    }


def _inegalites(conn, niveau: str, code: str) -> dict | None:
    """Question 4 : seuils des 10 % les plus modestes et les plus aisés ; rapport D9/D1,
    Gini et pauvreté ; pour la France, les courbes depuis 1996 (métropole)."""
    valeurs = {
        c: _local(conn, c, niveau, code)
        for c in ("NIVEAU_VIE_D1", "NIVEAU_VIE_D9", "RAPPORT_D9_D1", "INDICE_GINI",
                  "TAUX_PAUVRETE", "RAPPORT_S80_S20")
    }  # fmt: skip
    if not any(valeurs.values()):
        return None
    courbes = None
    if niveau == "FRANCE":
        lire = lambda c: series.serie(conn, c, "FRANCE", "FM")  # noqa: E731
        courbes = {
            "rapport": _courbe({"Rapport D9/D1": lire("RAPPORT_D9_D1_SERIE")}),
            "pauvrete": _courbe({"Taux de pauvreté": lire("TAUX_PAUVRETE_SERIE")}),
            "gini": _courbe({"Indice de Gini": lire("GINI_SERIE")}),
            "mediane": _courbe({"Niveau de vie médian": lire("NIVEAU_VIE_MEDIAN_SERIE")}),
        }
    return {**valeurs, "courbes": courbes}


def _parts_revenu(conn, niveau: str, code: str) -> dict | None:
    """Question 5 : d'où vient le revenu disponible (Filosofi), comparé à la France."""
    elements = []
    for indicateur, libelle in PARTS_REVENU:
        ligne = _local(conn, indicateur, niveau, code)
        if ligne is not None:
            france = ligne["france"]
            elements.append(
                {
                    "code": indicateur,
                    "libelle": libelle,
                    "valeur": ligne["valeur"],
                    "france": france["valeur"] if france else None,
                    "annee": ligne["annee"],
                }
            )
    if not elements:
        return None
    impots = _local(conn, "PART_IMPOTS", niveau, code)
    salaires = _local(conn, "PART_SALAIRES", niveau, code)
    premiere = max(elements, key=lambda e: e["valeur"])
    return {
        "elements": _barres(elements),
        "annee": elements[0]["annee"],
        "premiere": premiere,
        "pensions": next((e for e in elements if e["code"] == "PART_PENSIONS"), None),
        "prestations": next((e for e in elements if e["code"] == "PART_PRESTATIONS"), None),
        "impots": impots,
        "salaires": salaires,
    }


def _epargne(conn, niveau: str, code: str) -> dict | None:
    """Épargne (France) et surendettement (départements, métropole)."""
    taux = series.serie(conn, "TAUX_EPARGNE", "FRANCE", "FR")
    financiere = _france(conn, "TAUX_EPARGNE_FINANCIERE")
    dossiers = _local(conn, "DOSSIERS_SURENDETTEMENT", niveau, code)
    pour_100000 = _local(conn, "SURENDETTEMENT_POUR_100000", niveau, code)
    endettement = _local(conn, "ENDETTEMENT_MEDIAN", niveau, code)
    familles = []
    if endettement and niveau == "DEP":
        par_code = {
            x["modalite"]: x
            for x in _modalites(
                conn, "ENDETTEMENT_MEDIAN", niveau, code, "type_dette", endettement["periode"]
            )
        }
        familles = [par_code[c] for c in TYPES_DETTE if c in par_code]
    if not taux and dossiers is None:
        return None
    return {
        "taux": taux[-1] if taux else None,
        "taux_2000": next((x for x in taux if x["annee"] == DEPUIS_DEFAUT), None),
        "courbe": _courbe({"Taux d'épargne": taux, "Taux d'épargne financière":
                           series.serie(conn, "TAUX_EPARGNE_FINANCIERE", "FRANCE", "FR")}),
        "financiere": financiere,
        "dossiers": dossiers,
        "pour_100000": pour_100000,
        "endettement": endettement,
        "familles": familles,
    }  # fmt: skip


def _patrimoine(conn) -> dict | None:
    """Patrimoine des ménages (France) : enquête Histoire de vie et Patrimoine et
    placements financiers des comptes nationaux."""
    brut = _france(conn, "PATRIMOINE_BRUT_MOYEN")
    net = _france(conn, "PATRIMOINE_NET_MEDIAN")
    financier = _france(conn, "PATRIMOINE_FINANCIER")
    if brut is None and financier is None:
        return None
    ages, deciles, placements = [], [], []
    if brut:
        ages = _barres(
            [
                {**x, "libelle": None}
                for x in _par_age(conn, "PATRIMOINE_BRUT_MOYEN", "FRANCE", "FR", brut["annee"])
            ]
        )
        deciles = _barres([
            {"libelle": x["libelle"], "valeur": x["valeur"]}
            for x in _modalites(conn, "PATRIMOINE_BRUT_MOYEN", "FRANCE", "FR",
                                "decile_niveau_vie", brut["periode"])
        ])  # fmt: skip
    if financier:
        placements = _barres([
            {"libelle": x["libelle"], "valeur": x["valeur"]}
            for x in _modalites(conn, "PATRIMOINE_FINANCIER", "FRANCE", "FR", "placement",
                                financier["periode"])
        ])  # fmt: skip
        placements.sort(key=lambda x: -x["valeur"])
    return {
        "brut": brut,
        "net": net,
        "financier": financier,
        "ages": ages,
        "deciles": deciles,
        "placements": placements,
    }


def _pour_1000(conn, foyers: dict | None, niveau: str, code: str) -> float | None:
    """Foyers de décembre pour 1 000 habitants au 1er janvier suivant."""
    if foyers is None:
        return None
    janvier = date(foyers["periode"].year + 1, 1, 1)
    ici = "FR" if niveau == "FRANCE" else code
    population = next(
        (x["valeur"] for x in series.serie(conn, "POP", niveau, ici) if x["periode"] == janvier),
        None,
    )
    return 1000 * float(foyers["valeur"]) / float(population) if population else None


def _aides(conn, niveau: str, code: str) -> dict | None:
    """Question 6 : foyers au RSA et aidés pour leur logement en décembre (CAF), rapportés
    à la population ; aide moyenne et type de logement."""
    ici = "FR" if niveau == "FRANCE" else code
    rsa = _derniere(conn, "FOYERS_RSA", niveau, ici)
    logement = _derniere(conn, "FOYERS_AIDES_LOGEMENT", niveau, ici)
    if rsa is None and logement is None:
        return None
    rsa_1000 = _derniere(conn, "FOYERS_RSA_POUR_1000", niveau, ici)
    al_1000 = _pour_1000(conn, logement, niveau, code)
    al_1000_france = None
    if niveau != "FRANCE" and logement:
        al_1000_france = _pour_1000(
            conn, _france(conn, "FOYERS_AIDES_LOGEMENT", logement["periode"]), "FRANCE", "FR"
        )
    types = []
    if logement:
        types = _barres([
            {"libelle": x["libelle"], "valeur": x["valeur"]}
            for x in _modalites(conn, "FOYERS_AIDES_LOGEMENT", niveau, ici, "logement_aide",
                                logement["periode"])
        ])  # fmt: skip
        types.sort(key=lambda x: -x["valeur"])
    moyenne = _derniere(conn, "AIDE_LOGEMENT_MOYENNE", niveau, ici)
    return {
        "rsa": rsa,
        "rsa_1000": rsa_1000,
        "rsa_1000_france": _france(conn, "FOYERS_RSA_POUR_1000", rsa_1000["periode"])
        if rsa_1000 and niveau != "FRANCE"
        else None,
        "logement": logement,
        "al_1000": al_1000,
        "al_1000_france": al_1000_france,
        "moyenne": moyenne,
        "moyenne_france": _france(conn, "AIDE_LOGEMENT_MOYENNE", moyenne["periode"])
        if moyenne and niveau != "FRANCE"
        else None,
        "types": types,
        "courbe": _courbe({"RSA": series.serie(conn, "FOYERS_RSA", niveau, ici),
                           "Aide au logement": series.serie(conn, "FOYERS_AIDES_LOGEMENT",
                                                            niveau, ici)}),
        "parts": {c: _local(conn, c, niveau, code)
                  for c in ("PART_MINIMA_SOCIAUX", "PART_AIDES_LOGEMENT")},
        "formule_al": FORMULE_AL_POUR_1000,
    }  # fmt: skip


def _retraites(conn, niveau: str, code: str) -> dict | None:
    """Pension moyenne (France, DREES), part des pensions dans le revenu (Filosofi) et
    allocataires du minimum vieillesse parmi les 60 ans ou plus."""
    pension = _france(conn, "PENSION_MOYENNE")
    part = _local(conn, "PART_PENSIONS", niveau, code)
    minimum = _local(conn, "TAUX_MIN_VIEILLESSE_60P", niveau, code)
    if pension is None and part is None:
        return None
    sexes = {}
    if pension:
        sexes = {
            s: next((x["valeur"] for x in series.serie(conn, "PENSION_MOYENNE", "FRANCE", "FR",
                                                         sexe=s)
                     if x["periode"] == pension["periode"]), None)
            for s in ("F", "H")
        }  # fmt: skip
    return {
        "pension": pension,
        "sexes": sexes,
        "pensionnes": _france(conn, "PENSIONNES"),
        "part": part,
        "minimum": minimum,
    }


def _definitions(conn) -> dict[str, dict]:
    definitions = {i["code"]: i for i in series.indicateurs(conn, rubrique=RUBRIQUE)}
    # Indicateurs dérivés et séries nationales lus sans être affichés dans un thème.
    for code in ("POP",):
        definitions.update({i["code"]: i for i in series.indicateurs(conn, code=code)})
    return definitions


def _tete(libelle: str, ligne: dict | None, unite: str, note: str, code: str) -> dict | None:
    """Un chiffre en tête de page ; « (provisoire) » ajouté à la note s'il y a lieu."""
    if not ligne or ligne.get("valeur") is None:
        return None
    provisoire = " (provisoire)" if ligne.get("provisoire") else ""
    return {
        "libelle": libelle,
        "valeur": ligne["valeur"],
        "unite": unite,
        "note": f"{ligne['annee']}{provisoire}, {note}",
        "code": code,
    }


def _chiffres_tete(blocs: dict, niveau: str) -> list[dict]:
    """Les quatre chiffres en tête : pour la France, niveau de vie médian, pouvoir d'achat
    sur un an, taux d'épargne et rapport D9/D1 (étape 8 du dossier) ; pour un département,
    niveau de vie, salaire, pauvreté et RSA, avec la France et le rang."""
    if niveau == "FRANCE":
        revenus = blocs["revenus"] or {}
        pouvoir = blocs["pouvoir_achat"] or {}
        epargne = blocs["epargne"] or {}
        inegalites = blocs["inegalites"] or {}
        chiffres = (
            _tete("Niveau de vie médian", revenus.get("niveau_vie"), "euros",
                  "par an, métropole", "NIVEAU_VIE_MEDIAN"),
            _tete("Pouvoir d'achat sur un an", pouvoir.get("derniere"), "evolution",
                  "par unité de consommation", "POUVOIR_ACHAT_UC"),
            _tete("Taux d'épargne", epargne.get("taux"), "pourcentage",
                  "part du revenu disponible", "TAUX_EPARGNE"),
            _tete("Rapport D9/D1", inegalites.get("RAPPORT_D9_D1"), "ratio",
                  "plus aisés / plus modestes, métropole", "RAPPORT_D9_D1"),
        )  # fmt: skip
        return [c for c in chiffres if c]
    resultat = []
    aides = blocs["aides"] or {}
    for code, libelle, unite, ligne, france in (
        ("NIVEAU_VIE_MEDIAN", "Niveau de vie médian", "euros",
         (blocs["revenus"] or {}).get("niveau_vie"), None),
        ("SALAIRE_NET_MOYEN", "Salaire net moyen du privé", "euros",
         (blocs["revenus"] or {}).get("salaire"), None),
        ("TAUX_PAUVRETE", "Taux de pauvreté", "pourcentage",
         (blocs["inegalites"] or {}).get("TAUX_PAUVRETE"), None),
        ("FOYERS_RSA_POUR_1000", "Foyers au RSA", "pour_mille",
         aides.get("rsa_1000"), aides.get("rsa_1000_france")),
    ):  # fmt: skip
        if not ligne:
            continue
        france = france or ligne.get("france")
        note = f"France : {montant(france['valeur'], unite)}" if france else "département"
        chiffre = _tete(libelle, ligne, unite, note, code)
        if chiffre:
            resultat.append({**chiffre, "rang": blocs["rangs"].get(code)})
    return resultat


def _blocs(conn, niveau: str, code: str, depuis: int, categorie: str | None) -> dict:
    blocs = {
        "revenus": _revenus(conn, niveau, code),
        "salaires": _salaires(conn, niveau, code, categorie),
        "pouvoir_achat": _pouvoir_achat(conn, depuis),
        "inegalites": _inegalites(conn, niveau, code),
        "parts_revenu": _parts_revenu(conn, niveau, code),
        "epargne": _epargne(conn, niveau, code),
        "patrimoine": _patrimoine(conn),
        "aides": _aides(conn, niveau, code),
        "retraites": _retraites(conn, niveau, code),
        "rangs": _rangs(conn, code if niveau == "DEP" else None),
    }
    # Le pouvoir d'achat, l'épargne, le patrimoine et la pension moyenne sont nationaux :
    # ils ne suffisent pas à remplir une fiche.
    locaux = ("revenus", "salaires", "inegalites", "parts_revenu", "aides")
    blocs["avec_donnees"] = (
        any(blocs[k] for k in locaux)
        or bool((blocs["epargne"] or {}).get("dossiers"))
        or bool((blocs["retraites"] or {}).get("part") or (blocs["retraites"] or {}).get("minimum"))
    )
    blocs["chiffres_tete"] = _chiffres_tete(blocs, niveau)
    return blocs


Depuis = Annotated[int, Query(ge=DEPUIS_MIN - 1, le=2100)]
Categorie = Annotated[str | None, Query(pattern=r"^[A-Z0-9_]+$")]


@routeur.get("", response_class=HTMLResponse)
def vivre(
    request: Request, conn: Connexion, depuis: Depuis = DEPUIS_DEFAUT, categorie: Categorie = None
) -> HTMLResponse:
    tous = territoires.lister(conn)
    departements: dict[str, list[dict]] = {}
    for t in tous:
        if t["niveau"] == "DEP":
            departements.setdefault(t["parent_code"], []).append(t)
    contexte = {
        **_blocs(conn, "FRANCE", "FR", depuis, categorie),
        "fiche": None,
        "adresse": "/vivre",
        "definitions": _definitions(conn),
        "questions": QUESTIONS,
        "regions": sorted((t for t in tous if t["niveau"] == "REG"), key=lambda t: t["libelle"]),
        "departements": departements,
        "choix": choix_territoire(tous, ("DEP",), "/vivre/DEP/{code}"),
    }
    return gabarits.TemplateResponse(request, "vivre.html", contexte)


@routeur.get("/DEP/{code}", response_class=HTMLResponse)
def departement(
    request: Request,
    conn: Connexion,
    code: Annotated[str, Chemin(pattern=r"^[0-9][0-9AB][0-9]?$")],
    depuis: Depuis = DEPUIS_DEFAUT,
    categorie: Categorie = None,
) -> HTMLResponse:
    fiche = territoires.trouver(conn, "DEP", code)
    if fiche is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Département inconnu")
    contexte = {
        **_blocs(conn, "DEP", code, depuis, categorie),
        "fiche": fiche,
        "adresse": f"/vivre/DEP/{code}",
        "definitions": _definitions(conn),
        "questions": QUESTIONS,
    }
    return gabarits.TemplateResponse(request, "vivre.html", contexte)


@routeur.get("/theme/{theme}", response_class=HTMLResponse)
def theme(
    request: Request,
    conn: Connexion,
    theme: Annotated[str, Chemin(pattern=r"^[a-z-]+$")],
    indicateur: Annotated[str | None, Query(pattern=r"^[A-Z0-9_]+$")] = None,
    dep: Annotated[str | None, Query(pattern=r"^[0-9][0-9AB][0-9]?$")] = None,
) -> HTMLResponse:
    if theme not in THEMES_CARTE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thème inconnu")
    titre, codes = THEMES_CARTE[theme]
    definitions = {i["code"]: i for i in series.indicateurs(conn)}
    choix = [definitions[c] for c in codes if c in definitions]
    if indicateur is None:
        indicateur = codes[0]
    elif indicateur not in codes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicateur inconnu pour ce thème")
    definition = definitions.get(indicateur)
    if definition is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicateur non importé")
    lignes = series.classement(conn, indicateur)
    avec = [ligne for ligne in lignes if ligne["valeur"] is not None]
    sans = [ligne for ligne in lignes if ligne["valeur"] is None]
    france = None
    if avec and avec[0]["france_code"]:
        france = {"code": avec[0]["france_code"], "valeur": avec[0]["france_valeur"]}
    choisi = None
    if dep is not None:
        rang = next((i for i, x in enumerate(avec, 1) if x["code"] == dep), None)
        ligne = next((x for x in lignes if x["code"] == dep), None)
        if ligne is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Département inconnu")
        choisi = {**ligne, "rang": rang}
    contexte = {
        "theme": {"lien": theme, "titre": titre},
        "themes": [{"lien": t, "titre": v[0]} for t, v in THEMES_CARTE.items()],
        "choix": choix,
        "definition": definition,
        "annee": avec[0]["annee"] if avec else None,
        "france": france,
        "classement": avec,
        "sans_donnee": sans,
        "choisi": choisi,
        "departements": sorted(lignes, key=lambda x: x["libelle"]),
        "carte": _carte_coloree(
            lignes, definition["unite"], "/vivre/DEP/{code}", format_valeur=montant
        ),
    }
    return gabarits.TemplateResponse(request, "vivre_theme.html", contexte)
