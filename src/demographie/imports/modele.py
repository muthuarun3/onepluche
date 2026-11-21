"""Types communs aux connecteurs et au pipeline d'import."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol

# Régions d'outre-mer : leurs départements ne comptent pas dans la France métropolitaine.
REGIONS_OUTRE_MER = frozenset({"01", "02", "03", "04", "06"})


class FichierIllisible(ValueError):
    """Le fichier ne correspond pas à la structure attendue par le connecteur."""


@dataclass(frozen=True)
class Fichier:
    """Un fichier à importer, tel que publié par le producteur."""

    url: str
    nom: str
    millesime: str | None = None


@dataclass(frozen=True)
class Ligne:
    """Une valeur lue dans un fichier, avant rattachement aux référentiels."""

    indicateur: str
    niveau: str
    code: str
    periode: date
    periode_type: str
    sexe: str
    age_min: int | None
    age_max: int | None
    valeur: Decimal | int
    statut: str
    # (dimension, code) dans ref.modalite, ex. ("statut_activite", "RETRAITE")
    modalite: tuple[str, str] | None = None


@dataclass(frozen=True)
class Poids:
    """Poids d'une commune (résidences principales louées, population…), lu par un
    connecteur de poids communaux et rangé dans ingest.poids_commune, jamais publié."""

    dimension: str
    annee: int
    commune: str
    poids: Decimal


@dataclass(frozen=True)
class Referentiel:
    """Ce que les connecteurs doivent savoir des territoires connus en base."""

    # (niveau, code) -> territoire_id
    identifiants: dict[tuple[str, str], int]
    # code région -> libellé
    libelles_regions: dict[str, str] = field(default_factory=dict)
    # code département -> code région
    region_du_departement: dict[str, str] = field(default_factory=dict)
    # (dimension, année) -> {code commune: poids}, ex. ("RP_LOUEES", 2023)
    poids_communes: dict[tuple[str, int], dict[str, Decimal]] = field(default_factory=dict)

    def poids(self, dimension: str, annee: int | None = None) -> dict[str, Decimal]:
        """Poids communaux de la dimension, de l'année la plus récente <= annee (ou la
        plus récente tout court). Vide si aucun poids n'a encore été importé."""
        annees = sorted(
            a for d, a in self.poids_communes if d == dimension and (annee is None or a <= annee)
        )
        return self.poids_communes[(dimension, annees[-1])] if annees else {}

    def region_mono_departementale(self, departement: str) -> str | None:
        """Code de la région si elle ne compte que ce département (outre-mer), sinon None."""
        region = self.region_du_departement.get(departement)
        if region is None:
            return None
        freres = [d for d, r in self.region_du_departement.items() if r == region]
        return region if freres == [departement] else None


class Connecteur(Protocol):
    """Une source : où trouver ses fichiers et comment les lire.

    Attributs facultatifs lus par le pipeline :
    - tolerance_sommes : tolérance du contrôle des sommes (défaut 0,5 %) ;
    - controle_couverture : True pour exiger tous les départements à la dernière période ;
    - departements_absents : départements que la source ne couvre pas (ex. DVF) ;
    - poids_communaux : True pour un connecteur dont `lire` donne des `Poids` (rangés
      dans ingest.poids_commune) au lieu de lignes ; communes_min : nombre minimal de
      communes attendu par dimension et par année ;
    - lit_le_nom : True si `lire` a besoin du nom d'origine du fichier (sinon il reçoit
      le brut archivé, nommé par son empreinte).
    """

    source: str
    # Niveaux publiés ; les autres lignes lues ne servent qu'aux contrôles.
    niveaux_publies: frozenset[str]

    def fichiers(self) -> list[Fichier]: ...

    def accepte(self, nom_fichier: str) -> bool: ...

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]: ...
