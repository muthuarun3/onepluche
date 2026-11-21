"""Recensement de la population : jeux Melodi interrogés par l'API de données.

Les fichiers complets descendent à la commune (plus de 100 Mo) : on interroge plutôt
l'API, niveau par niveau (France, régions, départements) et pour chaque combinaison de
filtres utile, puis on assemble les réponses dans un seul fichier JSON trié, archivé
comme brut. Quelques appels espacés de 2 secondes par jeu.

Chaque jeu est décrit par un `JeuRecensement` : les dimensions fixées, la dimension
traduite en modalités (statut d'activité, catégorie socioprofessionnelle…) et les
tranches d'âge retenues.

Les millésimes du recensement sont des moyennes sur 5 ans : l'INSEE déconseille de
comparer deux millésimes séparés de moins de 5 ans (avertissement porté par les
indicateurs).
"""

import itertools
import json
import tempfile
import time
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

API = "https://api.insee.fr/melodi/data"
PAR_PAGE = 1000
PAUSE = 2.0  # secondes entre deux appels (limite officielle : 30 par minute)
_FRANCE = {"F": "FR", "FM": "FM"}


@dataclass(frozen=True)
class JeuRecensement:
    jeu: str
    indicateur: str
    # Dimensions fixées à une valeur ; les autres doivent valoir « _T » ou être absentes.
    filtres: dict[str, str]
    # Dimension détaillée -> code de modalité (None = total de la dimension).
    dimension: str
    dimension_ref: str  # dimension de ref.modalite
    modalites: dict[str, str | None]
    # Code d'âge -> (âge minimal ou None, âge maximal ou None) ; (None, None) = tous âges.
    ages: dict[str, tuple[int | None, int | None]]
    source: str = "INSEE_RP"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    niveaux_geo: tuple[str, ...] = ("FRANCE", "REG", "DEP")
    # Ages interrogés un par un (sinon : tous les âges en un seul appel).
    requete_par_age: bool = True
    # Nom de la dimension d'âge du jeu (« AGE_GP » pour Filosofi). Avec `ages` vide, le jeu
    # n'a pas de tranche d'âge : toutes les valeurs sont « tous âges ».
    dimension_age: str = "AGE"
    periode_type: str = "RP"
    # Distingue plusieurs indicateurs tirés du même jeu (un fichier brut chacun).
    suffixe: str = ""
    # Contrôle de couverture départementale (voir modele.Connecteur).
    controle_couverture: bool = False
    departements_absents: frozenset[str] = frozenset()
    # Contrôle des sommes France = somme des départements (voir modele.Connecteur).
    tolerance_sommes: float = 0.005
    # Valeurs de l'attribut OBS_STATUS qui signalent une valeur provisoire (comptes
    # nationaux) ; vide : tout est définitif (recensement).
    statuts_provisoires: frozenset[str] = frozenset()

    @property
    def nom_fichier(self) -> str:
        return f"{self.jeu}{self.suffixe}.json"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=f"{API}/{self.jeu}", nom=self.nom_fichier)]

    def _requetes(self) -> Iterator[str]:
        if self.requete_par_age and self.ages:
            ages = [{self.dimension_age: a} for a in self.ages]
        else:
            ages = [{}]
        for niveau, age in itertools.product(self.niveaux_geo, ages):
            filtres = {"GEO": niveau, **age, **self.filtres}
            yield f"{API}/{self.jeu}?{urllib.parse.urlencode(filtres)}&maxResult={PAR_PAGE}"

    def telecharger(self, fichier: Fichier, dossier: Path) -> Path:
        """Interroge l'API page par page et écrit les observations triées dans un JSON."""
        observations = []
        premier = True
        for requete in self._requetes():
            page = 1
            while True:
                if not premier:
                    time.sleep(PAUSE)
                premier = False
                reponse = telechargement.lire_json(f"{requete}&page={page}")
                if not isinstance(reponse, dict) or "observations" not in reponse:
                    raise FichierIllisible(f"Réponse inattendue de Melodi pour {requete}")
                observations += reponse["observations"]
                # « isLast » n'est présent qu'à partir de la 2e page : une page pleine
                # sans lui appelle la suivante.
                dernier = reponse.get("paging", {}).get("isLast", False)
                if dernier or len(reponse["observations"]) < PAR_PAGE:
                    break
                page += 1
        observations.sort(key=lambda o: json.dumps(o["dimensions"], sort_keys=True))
        dossier.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=dossier, suffix=".part", delete=False, encoding="utf-8"
        ) as sortie:
            json.dump({"jeu": self.jeu, "observations": observations}, sortie, sort_keys=True)
        return Path(sortie.name)

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            contenu = json.loads(chemin.read_text(encoding="utf-8"))
            observations = contenu["observations"]
        except (ValueError, KeyError, TypeError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        if not observations:
            raise FichierIllisible("Aucune observation")
        connues = {"GEO", "TIME_PERIOD", "FREQ", self.dimension_age, self.dimension, *self.filtres}
        for obs in observations:
            dim = obs.get("dimensions") if isinstance(obs, dict) else None
            if not isinstance(dim, dict):
                raise FichierIllisible(f"Observation illisible : {obs}")
            if dim.get(self.dimension) not in self.modalites:
                continue  # sous-catégories plus fines non retenues
            try:
                valeur = Decimal(str(obs["measures"]["OBS_VALUE_NIVEAU"]["value"]))
            except (KeyError, TypeError, ArithmeticError) as erreur:
                raise FichierIllisible(f"Observation illisible : {obs}") from erreur
            if self.ages and dim.get(self.dimension_age) not in self.ages:
                continue
            inattendues = {
                k: v
                for k, v in dim.items()
                if (k in self.filtres and v != self.filtres[k]) or (k not in connues and v != "_T")
            }
            if inattendues:
                raise FichierIllisible(f"Dimensions inattendues : {inattendues}")
            territoire = self._territoire(dim.get("GEO", ""))
            if territoire is None:
                continue
            age_min, age_max = self.ages[dim[self.dimension_age]] if self.ages else (None, None)
            modalite = self.modalites[dim[self.dimension]]
            yield Ligne(
                indicateur=self.indicateur,
                niveau=territoire[0],
                code=territoire[1],
                periode=date(int(dim["TIME_PERIOD"]), 1, 1),
                periode_type=self.periode_type,
                sexe="T",
                age_min=age_min,
                age_max=age_max,
                valeur=valeur,
                statut=(
                    "PROVISOIRE"
                    if obs.get("attributes", {}).get("OBS_STATUS") in self.statuts_provisoires
                    else "DEFINITIF"
                ),
                modalite=(self.dimension_ref, modalite) if modalite else None,
            )

    @staticmethod
    def _territoire(geo: str) -> tuple[str, str] | None:
        """« 2026-DEP-75 » -> ("DEP", "75") ; « 2026-FRANCE-F » -> ("FRANCE", "FR")."""
        morceaux = geo.split("-", 2)
        if len(morceaux) != 3:
            raise FichierIllisible(f"Code géographique inattendu : {geo}")
        _millesime, niveau, code = morceaux
        if niveau == "FRANCE":
            return ("FRANCE", _FRANCE[code]) if code in _FRANCE else None
        if niveau in ("REG", "DEP"):
            return (niveau, code)
        return None


# Population de 15 ans ou plus selon le statut d'activité déclaré.
RECENSEMENT = JeuRecensement(
    jeu="DS_RP_EMPLOI_LR_PRINC",
    indicateur="POP_RP",
    filtres={"SEX": "_T", "EDUC": "_T", "RP_MEASURE": "POP"},
    dimension="EMPSTA_ENQ",
    dimension_ref="statut_activite",
    modalites={
        "_T": None,
        "1T2": "ACTIF",
        "1": "ACTIF_OCCUPE",
        "2": "CHOMEUR",
        "3": "INACTIF",
        "31": "RETRAITE",
        "33": "ETUDIANT",
        "35T36": "AUTRE_INACTIF",
    },
    ages={"Y15T64": (15, 64), "Y_GE15": (15, None)},
)

# Population de 15 ans ou plus selon la catégorie socioprofessionnelle (groupes).
CATEGORIES = JeuRecensement(
    jeu="DS_RP_POPULATION_COMP",
    indicateur="POP_PCS",
    filtres={"SEX": "_T", "RP_MEASURE": "POP"},
    dimension="PCS",
    dimension_ref="pcs",
    modalites={
        "_T": None,
        "1": "AGRICULTEURS",
        "2": "ARTISANS_COMMERCANTS",
        "3": "CADRES",
        "4": "PROF_INTERMEDIAIRES",
        "5": "EMPLOYES",
        "6": "OUVRIERS",
        "7": "RETRAITES",
        "9": "AUTRES_SANS_ACTIVITE",
    },
    ages={"Y_GE15": (15, None)},
)

# Actifs en emploi (15 ans ou plus) selon le secteur d'activité.
SECTEURS = JeuRecensement(
    jeu="DS_RP_TD_ACTIVITE_PCSACTIVITY_COMP",
    indicateur="EMPLOIS_RP",
    filtres={"SEX": "_T", "PCS": "_T", "EMPSTA_ENQ": "1", "RP_MEASURE": "POP"},
    dimension="EMP_ACTIVITY",
    dimension_ref="secteur",
    modalites={
        "_T": None,
        "AZ": "AGRICULTURE",
        "BE": "INDUSTRIE",
        "FZ": "CONSTRUCTION",
        "GU": "COMMERCE_SERVICES",
        "OQ": "ADMIN_ENSEIGNEMENT_SANTE",
    },
    ages={"Y_GE15": (15, None)},
)

# Population de 2 ans ou plus selon la scolarisation, par tranche d'âge.
SCOLARISATION = JeuRecensement(
    jeu="DS_RP_EDUCATION_PRINC",
    indicateur="POP_SCOLARISATION",
    filtres={"SEX": "_T", "STUD_AREA": "_T", "RP_MEASURE": "POP"},
    dimension="STUD",
    dimension_ref="scolarisation",
    modalites={"_T": None, "1": "SCOLARISE"},
    ages={
        "Y2T5": (2, 5),
        "Y6T10": (6, 10),
        "Y11T14": (11, 14),
        "Y15T17": (15, 17),
        "Y18T24": (18, 24),
        "Y25T29": (25, 29),
        "Y_GE30": (30, None),
    },
    requete_par_age=False,
)
