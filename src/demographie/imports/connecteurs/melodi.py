"""Jeux de données du catalogue INSEE Melodi, téléchargés en entier (CSV zippé).

Un seul appel par jeu et par exécution, bien en dessous de la limite de 30 requêtes
par minute. Le fichier contient un en-tête de colonnes SDMX (GEO, GEO_OBJECT, FREQ,
TIME_PERIOD, OBS_VALUE, OBS_STATUS…) dont l'ordre varie d'un jeu à l'autre : on lit
par nom de colonne, jamais par position.
"""

import csv
import io
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

API = "https://api.insee.fr/melodi"
_COLONNES = {"GEO", "GEO_OBJECT", "FREQ", "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS"}
_FRANCE = {"F": "FR", "FM": "FM"}
_SEXES = {"_T": "T", "F": "F", "M": "H"}


@dataclass(frozen=True)
class Mesure:
    """Une mesure du jeu (EC_MEASURE…) traduite en indicateur de l'application."""

    indicateur: str
    filtre: dict[str, str]  # colonne -> valeur attendue, ex. {"EC_MEASURE": "BRTHRT"}
    sexes: frozenset[str] = frozenset({"_T"})  # codes SEX retenus si la colonne existe
    diviseur: int = 1  # ex. 100 pour un indicateur publié « pour 100 femmes »


@dataclass(frozen=True)
class JeuMelodi:
    source: str
    jeu: str
    mesures: tuple[Mesure, ...]
    frequence: str = "A"
    niveaux_publies: frozenset[str] = field(default=frozenset({"FRANCE", "REG", "DEP"}))

    @property
    def nom_fichier(self) -> str:
        return f"{self.jeu}.zip"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        url = f"{API}/file/{self.jeu}/{self.jeu}_CSV_FR"
        return [Fichier(url=url, nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        for rang in self._rangs(chemin):
            if rang["FREQ"] != self.frequence:
                continue
            mesure = self._mesure(rang)
            if mesure is None:
                continue
            territoires = self._territoires(rang["GEO_OBJECT"], rang["GEO"], referentiel)
            if not territoires:
                continue
            valeur = self._valeur(rang, mesure)
            annee = rang["TIME_PERIOD"]
            if not re.fullmatch(r"\d{4}", annee):
                raise FichierIllisible(f"Période annuelle inattendue : {annee}")
            statut = "PROVISOIRE" if rang["OBS_STATUS"] == "P" else "DEFINITIF"
            sexe = _SEXES[rang.get("SEX", "_T")]
            for niveau, code in territoires:
                yield Ligne(
                    indicateur=mesure.indicateur,
                    niveau=niveau,
                    code=code,
                    periode=date(int(annee), 1, 1),
                    periode_type="ANNEE",
                    sexe=sexe,
                    age_min=None,
                    age_max=None,
                    valeur=valeur,
                    statut=statut,
                )

    def _rangs(self, chemin: Path) -> Iterator[dict[str, str]]:
        try:
            archive = zipfile.ZipFile(chemin)
        except zipfile.BadZipFile as erreur:
            raise FichierIllisible(f"Archive illisible : {erreur}") from erreur
        with archive:
            noms = [n for n in archive.namelist() if n.endswith("_data.csv")]
            if len(noms) != 1:
                raise FichierIllisible(f"{len(noms)} fichier(s) *_data.csv dans l'archive")
            with archive.open(noms[0]) as brut:
                lecteur = csv.DictReader(
                    io.TextIOWrapper(brut, encoding="utf-8-sig"), delimiter=";"
                )
                manquantes = _COLONNES - set(lecteur.fieldnames or ())
                if manquantes:
                    raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
                yield from lecteur

    def _mesure(self, rang: dict[str, str]) -> Mesure | None:
        for mesure in self.mesures:
            filtre_ok = all(rang.get(col) == val for col, val in mesure.filtre.items())
            if filtre_ok and rang.get("SEX", "_T") in mesure.sexes:
                return mesure
        return None

    @staticmethod
    def _territoires(objet: str, geo: str, referentiel: Referentiel) -> list[tuple[str, str]]:
        if objet == "FRANCE":
            return [("FRANCE", _FRANCE[geo])] if geo in _FRANCE else []
        if objet == "REG":
            return [("REG", geo)]
        if objet == "DEP":
            # Les régions d'outre-mer ne comptent qu'un département : même valeur.
            region = referentiel.region_mono_departementale(geo)
            return [("DEP", geo)] + ([("REG", region)] if region else [])
        return []  # OTHER : agrégats « DOM », etc.

    @staticmethod
    def _valeur(rang: dict[str, str], mesure: Mesure) -> Decimal:
        if rang.get("UNIT_MULT", "0") != "0":
            raise FichierIllisible(f"Multiplicateur d'unité inattendu pour {mesure.indicateur}")
        try:
            valeur = Decimal(rang["OBS_VALUE"])
        except InvalidOperation as erreur:
            raise FichierIllisible(f"Valeur non numérique : {rang['OBS_VALUE']!r}") from erreur
        return valeur / mesure.diviseur if mesure.diviseur != 1 else valeur


NAISSANCES = JeuMelodi(
    source="INSEE_EC",
    jeu="DS_NAISSANCES_FECONDITE_SERIES",
    mesures=(
        Mesure("NAISSANCES", {"EC_MEASURE": "LVB_PLACE_RES", "AGE": "_T"}),
        Mesure("TAUX_NATALITE", {"EC_MEASURE": "BRTHRT", "AGE": "_T"}),
        # Publié pour 100 femmes : 126 = 1,26 enfant par femme.
        Mesure("ICF", {"EC_MEASURE": "FERIND", "AGE": "_T"}, diviseur=100),
    ),
)

DECES = JeuMelodi(
    source="INSEE_EC",
    jeu="DS_DECES_MORTALITE_SERIES",
    mesures=(
        Mesure("DECES", {"EC_MEASURE": "DTH_PLACE_RES", "AGE": "_T"}),
        Mesure("TAUX_MORTALITE", {"EC_MEASURE": "MOR_RT", "AGE": "_T"}),
        Mesure("ESPERANCE_VIE", {"EC_MEASURE": "LEXPEC", "AGE": "Y0"}, sexes=frozenset({"F", "M"})),
    ),
)
