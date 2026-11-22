"""Projections de population pour la France à l'horizon 2070 (INSEE, juin 2026).

Fichier « ip2108.xlsx », données des figures de l'Insee Première n° 2108 :
- « Figure 3 » : population par scénario, en millions, de 2026 à 2070 (central,
  population basse et haute retenus) ;
- « Figure 5 » : population par grand groupe d'âge, en millions, scénario central.
Les valeurs sont publiées en millions avec trois décimales : arrondies au millier.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl

from demographie.imports.connecteurs.estimations import normaliser
from demographie.imports.modele import Fichier, FichierIllisible, Projection, Referentiel

PAGE = "https://www.insee.fr/fr/statistiques/9004289"
URL = "https://www.insee.fr/fr/statistiques/fichier/9004289/ip2108.xlsx"
NOM = "ip2108.xlsx"
PREMIERE_ANNEE = 2026
# Colonnes de la figure 3 (en-têtes normalisés) -> scénario.
SCENARIOS = {
    "scenariocentral": "INSEE_CENTRAL",
    "scenariodepopulationbasse": "INSEE_POP_BASSE",
    "scenariodepopulationhaute": "INSEE_POP_HAUTE",
}
# Colonnes de la figure 5 (en-têtes normalisés) -> (age_min, age_max).
GROUPES = {
    "moinsde20ans": (0, 19),
    "de20a44ans": (20, 44),
    "de45a64ans": (45, 64),
    "65ansouplus": (65, None),
    "dont80ansouplus": (80, None),
}


def _millions(valeur: object) -> int | None:
    if isinstance(valeur, int | float) and not isinstance(valeur, bool):
        return int(Decimal(str(valeur)) * 1_000_000)
    return None


@dataclass(frozen=True)
class ProjectionsFrance:
    source: str = "INSEE_PROJ_FR"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})
    projections: bool = True

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=URL, nom=NOM, millesime="2026")]

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == NOM

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Projection]:
        classeur = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
        try:
            for feuille in ("Figure 3", "Figure 5"):
                if feuille not in classeur.sheetnames:
                    raise FichierIllisible(f"Feuille « {feuille} » absente")
            yield from self._scenarios(list(classeur["Figure 3"].iter_rows(values_only=True)))
            yield from self._ages(list(classeur["Figure 5"].iter_rows(values_only=True)))
        finally:
            classeur.close()

    @staticmethod
    def _projection(annee: int, valeur: int, scenario: str, ages=(None, None)) -> Projection:
        return Projection(
            indicateur="PROJ_POP_FRANCE",
            niveau="FRANCE",
            code="FR",
            scenario=scenario,
            periode=date(annee, 1, 1),
            valeur=valeur,
            age_min=ages[0],
            age_max=ages[1],
        )

    def _scenarios(self, lignes: list[tuple]) -> Iterator[Projection]:
        entete = next((r for r in lignes if r and r[0] == "Année"), None)
        if entete is None:
            raise FichierIllisible("Figure 3 : en-tête « Année » introuvable")
        colonnes = {
            SCENARIOS[normaliser(n)]: i
            for i, n in enumerate(entete)
            if isinstance(n, str) and normaliser(n) in SCENARIOS
        }
        if len(colonnes) != len(SCENARIOS):
            raise FichierIllisible(f"Figure 3 : scénarios trouvés {sorted(colonnes)}")
        for ligne in lignes:
            if not isinstance(ligne[0], int) or ligne[0] < PREMIERE_ANNEE:
                continue
            for scenario, i in colonnes.items():
                if (valeur := _millions(ligne[i])) is not None:
                    yield self._projection(ligne[0], valeur, scenario)

    def _ages(self, lignes: list[tuple]) -> Iterator[Projection]:
        # Deux lignes d'en-tête : « Bilan démographique » puis « Scénario central » ; les
        # groupes d'âge du scénario sont les colonnes qui suivent « Scénario central ».
        titres = next((r for r in lignes if r and r[0] == "Année"), None)
        if titres is None or "Scénario central" not in titres:
            raise FichierIllisible("Figure 5 : colonne « Scénario central » introuvable")
        debut = titres.index("Scénario central")
        groupes = lignes[lignes.index(titres) + 1]
        colonnes = {
            GROUPES[normaliser(n)]: i
            for i, n in enumerate(groupes)
            if i >= debut and isinstance(n, str) and normaliser(n) in GROUPES
        }
        if len(colonnes) != len(GROUPES):
            raise FichierIllisible(f"Figure 5 : groupes d'âge trouvés {sorted(colonnes)}")
        for ligne in lignes:
            if not isinstance(ligne[0], int) or ligne[0] < PREMIERE_ANNEE:
                continue
            for ages, i in colonnes.items():
                if (valeur := _millions(ligne[i])) is not None:
                    yield self._projection(ligne[0], valeur, "INSEE_CENTRAL", ages)


PROJECTIONS_FRANCE = ProjectionsFrance()
