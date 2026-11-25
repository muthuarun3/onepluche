"""Allocataires des CAF : portail data.caf.fr (Opendatasoft, sans compte, Licence Ouverte).

Deux jeux départementaux, mensuels depuis juin 2016, régime général seul (hors MSA) :

- `rsa_s_dem_2_dep` : foyers bénéficiaires du RSA, ventilés par année de la demande ;
  on les additionne ;
- `al_s_type_log_dep` : foyers bénéficiaires d'une aide au logement (APL, ALF, ALS) et
  montant versé dans le mois, par type de logement (location, accession, foyer, inconnu).

Seul le mois de décembre est retenu (dossier de conception de l'appli 3, étape 6) : l'export
CSV est filtré par l'API. Les codes hors référentiel (« 99 », « 978 », « XX ») sont ignorés.
La France est la somme des départements, signalée comme telle dans le catalogue.
"""

import csv
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

API = "https://data.caf.fr/api/explore/v2.1/catalog/datasets"


@dataclass(frozen=True)
class JeuCaf:
    jeu: str
    nom_fichier: str
    # Colonne de la ventilation (None : on additionne toutes les lignes).
    colonne_type: str | None
    # Libellé du type -> code de modalité (None : compté dans le total seulement).
    types: dict[str, str | None]
    # Colonne de la valeur -> indicateur.
    valeurs: dict[str, str]
    dimension_ref: str = ""
    source: str = "CNAF"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "DEP"})
    controle_couverture: bool = True
    departements_absents: frozenset[str] = frozenset()

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        requete = "where=month(dtreffre)%3D12&delimiter=%3B&order_by=dtreffre,numdep"
        return [Fichier(url=f"{API}/{self.jeu}/exports/csv?{requete}", nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        departements = set(referentiel.region_du_departement)
        # (indicateur, année, département, modalité) -> valeur
        cumuls: dict[tuple, Decimal] = defaultdict(Decimal)
        with chemin.open(encoding="utf-8-sig", newline="") as f:
            lecteur = csv.DictReader(f, delimiter=";")
            attendues = {"dtreffre", "numdep", *self.valeurs}
            if self.colonne_type:
                attendues.add(self.colonne_type)
            manquantes = attendues - set(lecteur.fieldnames or ())
            if manquantes:
                raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
            for rang in lecteur:
                mois = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", rang["dtreffre"])
                if mois is None:
                    raise FichierIllisible(f"Date inattendue : {rang['dtreffre']!r}")
                if mois[2] != "12" or rang["numdep"] not in departements:
                    continue
                if self.colonne_type:
                    if rang[self.colonne_type] not in self.types:
                        raise FichierIllisible(f"Type inattendu : {rang[self.colonne_type]!r}")
                    modalites = {None, self.types[rang[self.colonne_type]]}
                else:
                    modalites = {None}
                for colonne, indicateur in self.valeurs.items():
                    try:
                        valeur = Decimal(rang[colonne] or "0")
                    except InvalidOperation as erreur:
                        raise FichierIllisible(f"Valeur illisible : {rang[colonne]!r}") from erreur
                    for modalite in modalites:
                        cumuls[(indicateur, int(mois[1]), rang["numdep"], modalite)] += valeur
        if not cumuls:
            raise FichierIllisible("Aucune valeur de décembre pour un département connu")
        france: dict[tuple, Decimal] = defaultdict(Decimal)
        for (indicateur, annee, departement, modalite), valeur in cumuls.items():
            france[(indicateur, annee, modalite)] += valeur
            yield self._ligne(indicateur, annee, "DEP", departement, modalite, valeur)
        for (indicateur, annee, modalite), valeur in france.items():
            yield self._ligne(indicateur, annee, "FRANCE", "FR", modalite, valeur)

    def _ligne(self, indicateur, annee, niveau, code, modalite, valeur) -> Ligne:
        return Ligne(
            indicateur=indicateur,
            niveau=niveau,
            code=code,
            periode=date(annee, 12, 1),
            periode_type="MOIS",
            sexe="T",
            age_min=None,
            age_max=None,
            valeur=valeur,
            statut="DEFINITIF",
            modalite=(self.dimension_ref, modalite) if modalite else None,
        )


RSA = JeuCaf(
    jeu="rsa_s_dem_2_dep",
    nom_fichier="caf_rsa_decembre.csv",
    colonne_type=None,
    types={},
    valeurs={"indfoy_rsa": "FOYERS_RSA"},
)

AIDES_LOGEMENT = JeuCaf(
    jeu="al_s_type_log_dep",
    nom_fichier="caf_aides_logement_decembre.csv",
    colonne_type="al_type_log",
    types={
        "Location": "LOCATION",
        "Accession": "ACCESSION",
        "Foyers": "FOYER",
        "Inconnu": None,
    },
    valeurs={
        "indfoy_ndural": "FOYERS_AIDES_LOGEMENT",
        "indmtt_ndural": "MONTANT_AIDES_LOGEMENT",
    },
    dimension_ref="logement_aide",
)
