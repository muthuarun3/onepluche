"""Pathologies, traitements chroniques et épisodes de soins (Assurance maladie).

Jeu « effectifs » de la cartographie des pathologies, portail data.ameli.fr (Opendatasoft,
sans compte, Licence Ouverte). Il compte, chaque année depuis 2015, les personnes prises
en charge pour chaque groupe de pathologies parmi les bénéficiaires du régime général et
des régimes rattachés ayant eu au moins un soin remboursé (environ 68 millions).

On demande au portail un export CSV limité aux grands groupes (niveau 1), tous âges et
tous sexes, pour la France, les régions et les départements (environ 20 000 lignes).
Les effectifs publiés sont arrondis à la dizaine. Une personne peut relever de
plusieurs groupes : les parts ne s'additionnent pas.
"""

import csv
import re
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

API = "https://data.ameli.fr/api/explore/v2.1/catalog/datasets"
TOTAL = "POP_TOT_IND"  # population prise en compte : total des parts
# Code « top » publié -> code de modalité. Maternité (rapportée aux femmes) et
# hospitalisations pour Covid (depuis 2020 seulement) ne sont pas retenues.
GROUPES = {
    "POP_TOT_ABS": "AUCUNE",
    "HHP_CAT_INC": "HOSPITALISATIONS",
    "TFC_CAT_EXC": "RISQUE_VASCULAIRE",
    "TPS_CAT_EXC": "PSYCHOTROPES",
    "MCV_CAT_CAT": "CARDIO_NEUROVASCULAIRE",
    "DIA_CAT_CAT": "DIABETE",
    "RES_CAT_EXC": "RESPIRATOIRE",
    "CAN_CAT_CAT": "CANCERS",
    "PSY_CAT_CAT": "PSYCHIATRIQUE",
    "NEU_CAT_CAT": "NEUROLOGIQUE",
    "ALD_CAT_CAT": "AUTRES_ALD",
    "IRV_CAT_CAT": "INFLAMMATOIRE_RARE_VIH",
    "TAA_CAT_EXC": "ANTALGIQUES",
    "MFP_CAT_EXC": "FOIE_PANCREAS",
    "IRT_CAT_CAT": "INSUFFISANCE_RENALE",
}
_DEPARTEMENT = re.compile(r"\d\d|2[AB]|97[1-6]")


@dataclass(frozen=True)
class Pathologies:
    jeu: str = "effectifs"
    nom_fichier: str = "ameli-pathologies.csv"
    indicateur: str = "PATIENTS_PATHOLOGIE"
    source: str = "CNAM_PATHO"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    # Les bénéficiaires sans département de résidence connu ne comptent qu'au total
    # national : la somme des départements est inférieure de 0,4 % (2024) à 2,9 % (2015).
    tolerance_sommes: float = 0.03

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        tops = ",".join(f'"{t}"' for t in (TOTAL, *GROUPES))
        parametres = {
            "select": "annee,top,region,dept,ntop",
            "where": f'cla_age_5="tsage" and sexe=9 and top in ({tops})',
            "order_by": "annee,region,dept,top",
            "delimiter": ";",
        }
        requete = urllib.parse.urlencode(parametres, quote_via=urllib.parse.quote)
        return [Fichier(url=f"{API}/{self.jeu}/exports/csv?{requete}", nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        vues = 0
        with chemin.open(encoding="utf-8-sig", newline="") as f:
            lecteur = csv.DictReader(f, delimiter=";")
            manquantes = {"annee", "top", "region", "dept", "ntop"} - set(lecteur.fieldnames or ())
            if manquantes:
                raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
            for rang in lecteur:
                top = rang["top"]
                if top != TOTAL and top not in GROUPES:
                    raise FichierIllisible(f"Groupe de pathologies inattendu : {top!r}")
                territoire = self._territoire(rang["region"], rang["dept"])
                if territoire is None or not rang["ntop"]:
                    continue  # effectif non publié (secret statistique, année sans Covid)
                annee = rang["annee"][:4]
                if not re.fullmatch(r"\d{4}", annee):
                    raise FichierIllisible(f"Année inattendue : {rang['annee']!r}")
                try:
                    valeur = Decimal(rang["ntop"])
                except InvalidOperation as erreur:
                    raise FichierIllisible(f"Effectif illisible : {rang['ntop']!r}") from erreur
                vues += 1
                yield Ligne(
                    indicateur=self.indicateur,
                    niveau=territoire[0],
                    code=territoire[1],
                    periode=date(int(annee), 1, 1),
                    periode_type="ANNEE",
                    sexe="T",
                    age_min=None,
                    age_max=None,
                    valeur=valeur,
                    statut="DEFINITIF",
                    modalite=None if top == TOTAL else ("pathologie", GROUPES[top]),
                )
        if not vues:
            raise FichierIllisible("Aucun effectif de patients")

    @staticmethod
    def _territoire(region: str, dept: str) -> tuple[str, str] | None:
        """(« 99 », « 999 ») -> France ; (« 11 », « 999 ») -> région ; sinon département."""
        if dept == "999":
            if region == "99":
                return ("FRANCE", "FR")
            if re.fullmatch(r"\d\d", region):
                return ("REG", region)
            raise FichierIllisible(f"Région inattendue : {region!r}")
        if _DEPARTEMENT.fullmatch(dept):
            return ("DEP", dept)
        return None  # département non renseigné ou hors France


PATHOLOGIES = Pathologies()
