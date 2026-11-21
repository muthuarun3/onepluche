"""Étudiants inscrits dans l'enseignement supérieur (ministère de l'Enseignement supérieur).

Portail data.enseignementsup-recherche.gouv.fr (Opendatasoft, sans compte, Licence
Ouverte). On demande au portail un export CSV déjà agrégé par rentrée, département et
catégorie (quelques milliers de lignes) ; régions et France sont recalculées ici en
additionnant les départements, ce qui garantit leur cohérence.

Deux jeux :

- Atlas régional : tous les étudiants (universités, BTS, classes prépas, écoles…) par
  type de formation, depuis la rentrée 2001, au département de l'établissement.
- SISE : étudiants des universités publiques par grande discipline, depuis 2017, au
  département du site d'enseignement.

Les effectifs sont comptés là où l'on étudie, pas là où l'on habite.
"""

import csv
import re
import urllib.parse
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from demographie.imports.modele import (
    REGIONS_OUTRE_MER,
    Fichier,
    FichierIllisible,
    Ligne,
    Referentiel,
)

API = "https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets"
_DEPARTEMENT = re.compile(r"D(0\d[\dAB]|97[1-6])")


@dataclass(frozen=True)
class JeuEsr:
    jeu: str
    nom_fichier: str
    indicateur: str
    colonne_departement: str
    colonne_categorie: str
    dimension_ref: str
    # Libellé publié -> code de modalité ; un libellé inconnu fait échouer l'import.
    categories: dict[str, str]
    filtre: str | None = None  # clause « where » de l'export
    source: str = "MESR_ETU"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        groupes = f"rentree,{self.colonne_departement},{self.colonne_categorie}"
        parametres = {
            "select": f"{groupes},sum(effectif) as effectif",
            "group_by": groupes,
            "order_by": groupes,
            "delimiter": ";",
        }
        if self.filtre:
            parametres["where"] = self.filtre
        requete = urllib.parse.urlencode(parametres, quote_via=urllib.parse.quote)
        return [Fichier(url=f"{API}/{self.jeu}/exports/csv?{requete}", nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        # (rentrée, département, modalité) -> effectif
        effectifs: dict[tuple[int, str, str], Decimal] = defaultdict(Decimal)
        with chemin.open(encoding="utf-8-sig", newline="") as f:
            lecteur = csv.DictReader(f, delimiter=";")
            attendues = {"rentree", "effectif", self.colonne_departement, self.colonne_categorie}
            manquantes = attendues - set(lecteur.fieldnames or ())
            if manquantes:
                raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
            for rang in lecteur:
                departement = _DEPARTEMENT.fullmatch(rang[self.colonne_departement])
                if departement is None:
                    continue  # collectivités d'outre-mer, étranger, non renseigné
                categorie = rang[self.colonne_categorie]
                if categorie not in self.categories:
                    raise FichierIllisible(f"Catégorie inconnue : {categorie!r}")
                if not re.fullmatch(r"\d{4}", rang["rentree"]):
                    raise FichierIllisible(f"Rentrée inattendue : {rang['rentree']!r}")
                try:
                    valeur = Decimal(rang["effectif"] or "0")
                except InvalidOperation as erreur:
                    raise FichierIllisible(f"Effectif illisible : {rang['effectif']!r}") from erreur
                # « D001 » -> « 01 », « D02A » -> « 2A », « D971 » -> « 971 »
                brut = departement[1]
                code = brut[1:] if brut.startswith("0") else brut
                cle = (int(rang["rentree"]), code, self.categories[categorie])
                effectifs[cle] += valeur
        if not effectifs:
            raise FichierIllisible("Aucun effectif d'étudiants")
        yield from self._lignes(effectifs, referentiel)

    def _lignes(self, effectifs, referentiel: Referentiel) -> Iterator[Ligne]:
        totaux: dict[tuple[int, str, str, str | None], Decimal] = defaultdict(Decimal)
        for (rentree, departement, modalite), valeur in effectifs.items():
            region = referentiel.region_du_departement.get(departement)
            territoires = [("DEP", departement), ("FRANCE", "FR")]
            if region:
                territoires.append(("REG", region))
                if region not in REGIONS_OUTRE_MER:
                    territoires.append(("FRANCE", "FM"))
            for niveau, code in territoires:
                totaux[(rentree, niveau, code, modalite)] += valeur
                totaux[(rentree, niveau, code, None)] += valeur
        for (rentree, niveau, code, modalite), valeur in sorted(
            totaux.items(), key=lambda e: (e[0][0], e[0][1], e[0][2], e[0][3] or "")
        ):
            yield Ligne(
                indicateur=self.indicateur,
                niveau=niveau,
                code=code,
                periode=date(rentree, 1, 1),  # année de la rentrée (année universitaire)
                periode_type="ANNEE",
                sexe="T",
                age_min=None,
                age_max=None,
                valeur=valeur,
                statut="DEFINITIF",
                modalite=(self.dimension_ref, modalite) if modalite else None,
            )


FORMATIONS = JeuEsr(
    jeu="fr-esr-atlas_regional-effectifs-d-etudiants-inscrits_agregeables",
    nom_fichier="esr-etudiants-formations.csv",
    indicateur="ETUDIANTS",
    colonne_departement="dep_id",
    colonne_categorie="rgp_formations_ou_etablissements",
    dimension_ref="formation",
    categories={
        "Universités": "UNIVERSITES",
        "Universités de technologie (UT)": "UNIVERSITES",
        "Instituts nationaux polytechniques (INP)": "UNIVERSITES",
        "Grands établissements MESRE": "UNIVERSITES",
        "Établissements d'enseignement universitaire privés": "UNIVERSITES",
        "Instituts universitaires de formation des maîtres": "UNIVERSITES",
        "Sections de techniciens supérieurs (STS) et assimilés": "STS",
        "Classes préparatoires aux grandes écoles (CPGE)": "CPGE",
        "Autres formations d'ingénieurs": "INGENIEURS",
        "Écoles de commerce, gestion et comptabilité": "COMMERCE",
        "Écoles paramédicales et sociales": "PARAMEDICAL_SOCIAL",
        "Écoles supérieures art et culture": "ART_CULTURE",
        "Écoles normales supérieures (ENS)": "AUTRES_ECOLES",
        "Écoles juridiques et administratives": "AUTRES_ECOLES",
        "Autres écoles de spécialités diverses": "AUTRES_ECOLES",
    },
)

DISCIPLINES = JeuEsr(
    jeu="fr-esr-sise-effectifs-d-etudiants-inscrits-esr-public",
    nom_fichier="esr-etudiants-disciplines.csv",
    indicateur="ETUDIANTS_UNIVERSITE",
    colonne_departement="implantation_id_departement",
    colonne_categorie="gd_discipline",
    dimension_ref="discipline",
    categories={
        "DSA": "DROIT_ECO_GESTION",
        "LLSH": "LETTRES_SHS",
        "SI": "SCIENCES",
        "SANTE": "SANTE",
        "STAPS": "STAPS",
        "INTERD": "AUTRES_DISCIPLINES",
        "THEO": "AUTRES_DISCIPLINES",
    },
    filtre='etablissement_type="Université"',
)
