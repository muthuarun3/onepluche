"""Séries de la Banque de données macroéconomiques (BDM) de l'INSEE, API SDMX sans compte.

Un appel rapatrie tout un jeu (« dataflow ») au format SDMX-ML : une balise Series par
territoire, une balise Obs par période. Lecture avec defusedxml (pas d'entités externes).
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from defusedxml.ElementTree import iterparse

from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

API = "https://api.insee.fr/series/BDM/data"
_TRIMESTRE = re.compile(r"^(\d{4})-Q([1-4])$")


@dataclass(frozen=True)
class JeuBdm:
    source: str
    jeu: str
    indicateur: str
    # REF_AREA de la BDM -> (niveau, code) dans le référentiel, pour les cas particuliers.
    zones_speciales: dict[str, tuple[str, str]] = field(default_factory=dict)
    niveaux_publies: frozenset[str] = field(default=frozenset({"FRANCE", "REG", "DEP"}))

    @property
    def nom_fichier(self) -> str:
        return f"{self.jeu}.xml"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=f"{API}/{self.jeu}", nom=self.nom_fichier)]

    def _territoires(self, zone: str, referentiel: Referentiel) -> list[tuple[str, str]]:
        if zone in self.zones_speciales:
            return [self.zones_speciales[zone]]
        if zone.startswith("R"):
            return [("REG", zone[1:])]
        if zone.startswith("D"):
            departement = zone[1:]
            region = referentiel.region_mono_departementale(departement)
            return [("DEP", departement)] + ([("REG", region)] if region else [])
        # Zone inconnue : transmise telle quelle, le pipeline rejettera le fichier.
        return [("DEP", zone)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        series = 0
        try:
            for _evenement, element in iterparse(str(chemin), events=("end",)):
                if not element.tag.endswith("}Series") and element.tag != "Series":
                    continue
                series += 1
                yield from self._lire_serie(element, referentiel)
                element.clear()
        except FichierIllisible:
            raise
        except Exception as erreur:  # XML mal formé ou interdit (entités, DTD)
            raise FichierIllisible(f"XML illisible : {erreur}") from erreur
        if series == 0:
            raise FichierIllisible("Aucune série dans le fichier")

    def _lire_serie(self, serie, referentiel: Referentiel) -> Iterator[Ligne]:
        attributs = serie.attrib
        if attributs.get("FREQ") != "T" or attributs.get("UNIT_MULT", "0") != "0":
            raise FichierIllisible(f"Série inattendue : {attributs.get('IDBANK')}")
        territoires = self._territoires(attributs.get("REF_AREA", ""), referentiel)
        for obs in serie:
            periode = _TRIMESTRE.match(obs.attrib.get("TIME_PERIOD", ""))
            if not periode:
                raise FichierIllisible(f"Période inattendue : {obs.attrib.get('TIME_PERIOD')}")
            try:
                valeur = Decimal(obs.attrib["OBS_VALUE"])
            except (KeyError, InvalidOperation) as erreur:
                raise FichierIllisible(f"Valeur illisible : {obs.attrib}") from erreur
            debut = date(int(periode[1]), 3 * int(periode[2]) - 2, 1)
            statut = "DEFINITIF" if obs.attrib.get("OBS_STATUS") == "A" else "PROVISOIRE"
            for niveau, code in territoires:
                yield Ligne(
                    indicateur=self.indicateur,
                    niveau=niveau,
                    code=code,
                    periode=debut,
                    periode_type="TRIMESTRE",
                    sexe="T",
                    age_min=None,
                    age_max=None,
                    valeur=valeur,
                    statut=statut,
                )


CHOMAGE = JeuBdm(
    source="INSEE_CHOM",
    jeu="TAUX-CHOMAGE",
    indicateur="TAUX_CHOMAGE",
    # « FR-D976 » : France hors Mayotte, seul total national publié pour ce taux.
    zones_speciales={"FM": ("FRANCE", "FM"), "FR-D976": ("FRANCE", "FR")},
)
