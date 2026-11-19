"""Configuration : lecture des variables d'environnement, rien d'autre."""

import os
from dataclasses import dataclass
from pathlib import Path


class ConfigurationManquante(RuntimeError):
    """Une variable d'environnement obligatoire est absente."""


def _obligatoire(nom: str) -> str:
    valeur = os.environ.get(nom, "").strip()
    if not valeur:
        raise ConfigurationManquante(f"Variable d'environnement manquante : {nom}")
    return valeur


@dataclass(frozen=True)
class Config:
    db_proprietaire_url: str | None
    db_import_url: str | None
    db_lecture_url: str | None
    donnees_brutes: Path
    ping_import: str | None = None

    def url(self, role: str) -> str:
        valeur = {
            "proprietaire": self.db_proprietaire_url,
            "import": self.db_import_url,
            "lecture": self.db_lecture_url,
        }[role]
        if not valeur:
            raise ConfigurationManquante(f"Aucune URL de connexion pour le rôle « {role} »")
        return valeur


def charger() -> Config:
    """Lit la configuration. Les URL absentes ne sont signalées qu'à l'usage."""
    return Config(
        db_proprietaire_url=os.environ.get("DEMO_DB_PROPRIETAIRE_URL") or None,
        db_import_url=os.environ.get("DEMO_DB_IMPORT_URL") or None,
        db_lecture_url=os.environ.get("DEMO_DB_LECTURE_URL") or None,
        donnees_brutes=Path(os.environ.get("DEMO_DONNEES_BRUTES", "./donnees-brutes")),
        ping_import=os.environ.get("DEMO_PING_IMPORT") or None,
    )
