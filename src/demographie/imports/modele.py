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


@dataclass(frozen=True)
class Referentiel:
    """Ce que les connecteurs doivent savoir des territoires connus en base."""

    # (niveau, code) -> territoire_id
    identifiants: dict[tuple[str, str], int]
    # code région -> libellé
    libelles_regions: dict[str, str] = field(default_factory=dict)


class Connecteur(Protocol):
    """Une source : où trouver ses fichiers et comment les lire."""

    source: str
    # Niveaux publiés ; les autres lignes lues ne servent qu'aux contrôles.
    niveaux_publies: frozenset[str]

    def fichiers(self) -> list[Fichier]: ...

    def accepte(self, nom_fichier: str) -> bool: ...

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]: ...
