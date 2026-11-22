"""Projections de population 2018-2070 par département (INSEE, modèle Omphale 2022).

Trois fichiers « donnees_det_<scénario>.xlsx » de la page 7747107 : scénario central,
population basse et population haute (les huit autres variantes ne sont pas reprises,
dossier de conception de l'appli 5, étape 3). Chaque fichier a trois feuilles :
- « Population » : une ligne par département (nommé en toutes lettres), sexe (1 hommes,
  2 femmes) et tranche d'âge quinquennale, une colonne POP_AAAA par année ;
- « Solde naturel » et « Solde migratoire » : une ligne par département, une colonne par
  année (flux de l'année AAAA à AAAA+1).

Le connecteur garde 2018 puis une année sur cinq (2020 à 2070), calcule les totaux
(ensemble des sexes, tous âges) et la France (FR) et la France métropolitaine (FM) comme
sommes des départements : la France ainsi obtenue est cohérente avec ses départements,
contrairement aux projections nationales de 2026 (connecteur projections_france).
"""

import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import openpyxl

from demographie.imports.connecteurs.estimations import normaliser
from demographie.imports.modele import (
    REGIONS_OUTRE_MER,
    Fichier,
    FichierIllisible,
    Projection,
    Referentiel,
)

PAGE = "https://www.insee.fr/fr/statistiques/7747107"
URL = "https://www.insee.fr/fr/statistiques/fichier/7747107/donnees_det_{}.xlsx"
SCENARIOS = {
    "Central": "INSEE_CENTRAL",
    "Pop_basse": "INSEE_POP_BASSE",
    "Pop_haute": "INSEE_POP_HAUTE",
}
ANNEES = (2018, *range(2020, 2071, 5))
# Libellés INSEE qui diffèrent de ceux du référentiel.
ALIAS = {"reunion": "974"}
_SEXES = {1: "H", 2: "F"}
_TRANCHE = re.compile(r"^\[(\d{1,3});(\d{1,3})(\+?)[\[\]]$")
_SOLDES = {"Solde naturel": "PROJ_SOLDE_NATUREL", "Solde migratoire": "PROJ_SOLDE_MIGRATOIRE"}


def tranche(libelle: object) -> tuple[int, int | None]:
    """« [0;5[ » -> (0, 4) ; « [95;99+] » -> (95, None)."""
    m = _TRANCHE.match(str(libelle).replace(" ", ""))
    if not m:
        raise FichierIllisible(f"Tranche d'âge illisible : {libelle!r}")
    if m[3]:
        return int(m[1]), None
    return int(m[1]), int(m[2]) - 1


def _codes_departements(referentiel: Referentiel) -> dict[str, str]:
    libelles = referentiel.libelles_departements
    codes = {normaliser(libelle): code for code, libelle in libelles.items()}
    return {**codes, **ALIAS}


@dataclass(frozen=True)
class ProjectionsDepartementales:
    source: str = "INSEE_OMPHALE"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "DEP"})
    projections: bool = True
    lit_le_nom: bool = True
    departements_attendus: int = 101

    def fichiers(self) -> list[Fichier]:
        return [
            Fichier(url=URL.format(nom), nom=f"donnees_det_{nom}.xlsx", millesime="Omphale 2022")
            for nom in SCENARIOS
        ]

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier in {f"donnees_det_{nom}.xlsx" for nom in SCENARIOS}

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Projection]:
        nom = re.fullmatch(r"donnees_det_(.+)\.xlsx", chemin.name)
        if not nom or nom[1] not in SCENARIOS:
            raise FichierIllisible(f"Nom de fichier inattendu : {chemin.name}")
        scenario = SCENARIOS[nom[1]]
        codes = _codes_departements(referentiel)
        classeur = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
        try:
            for feuille in ("Population", *_SOLDES):
                if feuille not in classeur.sheetnames:
                    raise FichierIllisible(f"Feuille « {feuille} » absente")
            yield from self._population(classeur["Population"], scenario, codes, referentiel)
            for feuille, indicateur in _SOLDES.items():
                yield from self._soldes(classeur[feuille], indicateur, scenario, codes, referentiel)
        finally:
            classeur.close()

    @staticmethod
    def _code(zone: str, codes: dict[str, str]) -> str:
        code = codes.get(normaliser(zone))
        if code is None:
            raise FichierIllisible(f"Département inconnu : {zone!r}")
        return code

    @staticmethod
    def _agreges(code: str, referentiel: Referentiel) -> tuple[str, ...]:
        """Agrégats France auxquels le département contribue."""
        if referentiel.region_du_departement.get(code) in REGIONS_OUTRE_MER:
            return ("FR",)
        return ("FR", "FM")

    def _population(self, feuille, scenario, codes, referentiel) -> Iterator[Projection]:
        lignes = feuille.iter_rows(values_only=True)
        entete = next((r for r in lignes if r and r[0] == "ZONE"), None)
        if entete is None or tuple(entete[:3]) != ("ZONE", "SEXE", "TRAGE"):
            raise FichierIllisible("En-tête ZONE, SEXE, TRAGE introuvable (feuille Population)")
        colonnes = {}
        for i, nom in enumerate(entete):
            m = re.fullmatch(r"POP_(\d{4})", nom) if isinstance(nom, str) else None
            if m and int(m[1]) in ANNEES:
                colonnes[int(m[1])] = i
        if set(colonnes) != set(ANNEES):
            raise FichierIllisible(f"Années manquantes : {sorted(set(ANNEES) - set(colonnes))}")
        # (code, annee, sexe, age_min, age_max) -> effectif
        valeurs: dict[tuple, int] = defaultdict(int)
        for ligne in lignes:
            if not ligne or not ligne[0]:
                continue
            code = self._code(ligne[0], codes)
            if ligne[1] not in _SEXES:
                raise FichierIllisible(f"Sexe inattendu : {ligne[1]!r}")
            sexe = _SEXES[ligne[1]]
            age_min, age_max = tranche(ligne[2])
            for annee, i in colonnes.items():
                effectif = ligne[i]
                if not isinstance(effectif, int | float):
                    raise FichierIllisible(f"{ligne[0]} {annee} : effectif illisible {effectif!r}")
                for territoire in (code, *self._agreges(code, referentiel)):
                    for s in (sexe, "T"):
                        for ages in ((age_min, age_max), (None, None)):
                            valeurs[(territoire, annee, s, *ages)] += int(effectif)
        if not valeurs:
            raise FichierIllisible("Aucune ligne de population")
        for (territoire, annee, sexe, age_min, age_max), effectif in valeurs.items():
            yield Projection(
                indicateur="PROJ_POP",
                niveau="FRANCE" if territoire in ("FR", "FM") else "DEP",
                code=territoire,
                scenario=scenario,
                periode=date(annee, 1, 1),
                valeur=effectif,
                sexe=sexe,
                age_min=age_min,
                age_max=age_max,
            )

    def _soldes(self, feuille, indicateur, scenario, codes, referentiel) -> Iterator[Projection]:
        lignes = feuille.iter_rows(values_only=True)
        entete = next((r for r in lignes if r and r[0] == "ZONE"), None)
        if entete is None:
            raise FichierIllisible(f"En-tête ZONE introuvable ({indicateur})")
        colonnes = {int(str(n)): i for i, n in enumerate(entete) if re.fullmatch(r"\d{4}", str(n))}
        colonnes = {a: i for a, i in colonnes.items() if a in ANNEES}
        if not colonnes:
            raise FichierIllisible(f"Aucune année retenue ({indicateur})")
        valeurs: dict[tuple[str, int], int] = defaultdict(int)
        for ligne in lignes:
            if not ligne or not ligne[0]:
                continue
            code = self._code(ligne[0], codes)
            for annee, i in colonnes.items():
                if not isinstance(ligne[i], int | float):
                    raise FichierIllisible(f"{ligne[0]} {annee} : valeur illisible {ligne[i]!r}")
                for territoire in (code, *self._agreges(code, referentiel)):
                    valeurs[(territoire, annee)] += int(ligne[i])
        for (territoire, annee), valeur in valeurs.items():
            yield Projection(
                indicateur=indicateur,
                niveau="FRANCE" if territoire in ("FR", "FM") else "DEP",
                code=territoire,
                scenario=scenario,
                periode=date(annee, 1, 1),
                periode_fin=date(annee, 12, 31),
                valeur=valeur,
            )


PROJECTIONS_DEPARTEMENTALES = ProjectionsDepartementales()
