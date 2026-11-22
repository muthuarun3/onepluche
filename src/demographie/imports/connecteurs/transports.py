"""Sources de l'appli 2 sur les transports et les courses.

- Ministère de l'Économie : prix des carburants déclarés par les stations (flux
  instantané, Opendatasoft), moyenne des stations par département, région et France
  métropolitaine au jour de l'import.
- INSEE, recensement (Melodi) : mode de transport des actifs pour aller travailler,
  nombre de voitures des ménages.
- INSEE, comptes nationaux (Melodi) : dépense des ménages en carburants (France).
"""

import json
import tempfile
import time
import urllib.error
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.connecteurs.besoins import _COMPTES, _LOGEMENT_TOTAUX, _SANS_MAYOTTE
from demographie.imports.connecteurs.communes import DROM
from demographie.imports.connecteurs.recensement import JeuRecensement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

# --- Prix des carburants ----------------------------------------------------------------

CARBURANTS_API = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "prix-des-carburants-en-france-flux-instantane-v2/records"
)
# Prix plus anciens que cela écartés : station fermée ou qui ne vend plus ce carburant.
FRAICHEUR_JOURS = 7
# En dessous, la moyenne d'un territoire n'est pas publiée.
STATIONS_MIN = 5
# Bornes de plausibilité d'un prix moyen au litre.
PRIX_MIN, PRIX_MAX = Decimal("0.5"), Decimal("5")


@dataclass(frozen=True)
class PrixCarburants:
    """Un carburant : `carburant` est le préfixe des champs de la source (« gazole »)."""

    carburant: str
    indicateur: str
    # Les stations d'outre-mer ne déclarent pas leurs prix (prix administrés).
    departements_absents: frozenset[str] = DROM
    source: str = "MINEFI_CARBURANTS"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True

    @property
    def nom_fichier(self) -> str:
        return f"prix-carburants-{self.carburant}.json"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=CARBURANTS_API, nom=self.nom_fichier)]

    def telecharger(self, fichier: Fichier, dossier: Path) -> Path:
        """Prix moyen et nombre de stations par département, région et France
        (métropolitaine), calculés par l'API ; écrits dans un JSON trié archivé comme brut."""
        releve = date.today()
        depuis = (releve - timedelta(days=FRAICHEUR_JOURS)).isoformat()
        c = self.carburant
        moyennes: dict[str, dict] = {}
        for niveau, champ in (("DEP", "code_departement"), ("REG", "code_region"),
                              ("FRANCE", None)):  # fmt: skip
            choix = f"avg({c}_prix) as prix, count({c}_prix) as stations"
            parametres = {
                "select": f"{champ}, {choix}" if champ else choix,
                "where": f'{c}_maj >= "{depuis}"',
                "limit": 100,
            }
            if champ:
                parametres["group_by"] = champ
            reponse = _lire_json_patient(f"{CARBURANTS_API}?{urllib.parse.urlencode(parametres)}")
            if not isinstance(reponse, dict) or not isinstance(reponse.get("results"), list):
                raise FichierIllisible(f"Réponse inattendue pour {c}, {niveau}")
            moyennes[niveau] = {
                (r.get(champ) if champ else "FM") or "": [r["prix"], r["stations"]]
                for r in reponse["results"]
            }
        dossier.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=dossier, suffix=".part", delete=False, encoding="utf-8"
        ) as sortie:
            json.dump({"releve": releve.isoformat(), "carburant": c, "moyennes": moyennes},
                      sortie, sort_keys=True)  # fmt: skip
        return Path(sortie.name)

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            contenu = json.loads(chemin.read_text(encoding="utf-8"))
            releve = date.fromisoformat(contenu["releve"])
            moyennes = contenu["moyennes"]
            carburant = contenu["carburant"]
        except (ValueError, KeyError, TypeError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        if carburant != self.carburant or set(moyennes) != {"DEP", "REG", "FRANCE"}:
            raise FichierIllisible(f"Relevé inattendu : {carburant}, {sorted(moyennes)}")
        # Une valeur par mois : le relevé le plus récent du mois remplace le précédent.
        mois = releve.replace(day=1)
        regions = set(referentiel.region_du_departement.values())
        for niveau, valeurs in sorted(moyennes.items()):
            for code, (prix, stations) in sorted(valeurs.items()):
                if not code:
                    continue  # stations sans département connu
                connu = (
                    (niveau == "DEP" and code in referentiel.region_du_departement)
                    or (niveau == "REG" and code in regions)
                    or (niveau == "FRANCE" and code == "FM")
                )
                if not connu:
                    raise FichierIllisible(f"Territoire inconnu : {niveau} {code}")
                if not isinstance(stations, int) or stations < STATIONS_MIN:
                    continue
                try:
                    valeur = Decimal(str(prix)).quantize(Decimal("0.001"))
                except (InvalidOperation, TypeError) as erreur:
                    raise FichierIllisible(f"Prix illisible : {prix}") from erreur
                if not PRIX_MIN <= valeur <= PRIX_MAX:
                    raise FichierIllisible(f"Prix moyen hors bornes : {niveau} {code} {valeur}")
                yield Ligne(self.indicateur, niveau, code, mois, "MOIS", "T", None, None,
                            valeur, "DEFINITIF")  # fmt: skip


def _lire_json_patient(url: str, essais: int = 4) -> object:
    """Le serveur coupe souvent la connexion : quelques essais espacés."""
    for essai in range(essais):
        try:
            return telechargement.lire_json(url)
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if essai == essais - 1:
                raise
            time.sleep(5 * (essai + 1))
    raise AssertionError("inatteignable")


PRIX_GAZOLE = PrixCarburants("gazole", "PRIX_GAZOLE")
# Le SP95-E10 n'est pas distribué en Corse.
PRIX_SP95_E10 = PrixCarburants("e10", "PRIX_SP95_E10", departements_absents=DROM | {"2A", "2B"})


# --- Recensement : trajets domicile-travail et voitures ---------------------------------

TRAJETS_TRAVAIL = JeuRecensement(
    jeu="DS_RP_NAVETTES_PRINC",
    suffixe="_mode",
    indicateur="ACTIFS_TRAJET",
    filtres={"WORK_AREA": "_T", "EMPSTA_ENQ": "1", "RP_MEASURE": "POP", "AGE": "Y_GE15"},
    dimension="TRANS",
    dimension_ref="mode_transport",
    # « 3T4 » (deux-roues) double 3 + 4 : non repris.
    modalites={
        "_T": None,
        "1": "AUCUN",
        "2": "MARCHE",
        "3": "VELO",
        "4": "DEUX_ROUES_MOTORISE",
        "5": "VOITURE",
        "6": "TRANSPORTS_COMMUN",
    },
    ages={},
    requete_par_age=False,
    controle_couverture=True,
    departements_absents=_SANS_MAYOTTE,
)

VOITURES_MENAGES = JeuRecensement(
    jeu="DS_RP_LOGEMENT_PRINC",
    suffixe="_voitures",
    indicateur="MENAGES_VOITURES",
    filtres={
        **{k: v for k, v in _LOGEMENT_TOTAUX.items() if k != "CARS"},
        "OCS": "DW_MAIN",
        "TSH": "_T",
        "NRG_SRC": "_T",
    },
    dimension="CARS",
    dimension_ref="voitures_menage",
    # « C_GE1 » (au moins une) double C1 + C_GE2 : non repris.
    modalites={"_T": None, "C0": "AUCUNE", "C1": "UNE", "C_GE2": "DEUX_OU_PLUS"},
    ages={},
    requete_par_age=False,
    controle_couverture=True,
    departements_absents=_SANS_MAYOTTE,
)


# --- Comptes nationaux : carburants ----------------------------------------------------

DEPENSE_CARBURANTS = JeuRecensement(
    jeu="DD_CNA_CONSO_MENAGES_COICOP",
    suffixe="_carburants",
    source="INSEE_CNA",
    indicateur="DEPENSE_CARBURANTS",
    filtres={
        **_COMPTES,
        "STO": "P31",
        "UNIT_MEASURE": "XDC",
        "ACCOUNTING_ENTRY": "D",
        "EXPENDITURE": "CP0722",
    },  # fmt: skip
    dimension="EXPENDITURE",
    dimension_ref="poste_conso",
    # Carburants et lubrifiants des véhicules personnels (COICOP 2018 07.2.2).
    modalites={"CP0722": None},
    ages={},
    requete_par_age=False,
    niveaux_geo=("FRANCE",),
    niveaux_publies=frozenset({"FRANCE"}),
    periode_type="ANNEE",
    statuts_provisoires=frozenset({"P"}),
)
