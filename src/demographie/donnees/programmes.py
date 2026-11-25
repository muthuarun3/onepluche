"""Fiches des programmes présidentiels (macro-catégorie « Programmes »).

Les fiches sont des fichiers TOML du dépôt (`programmes/<élection>/`) : une grille commune
(`sujets.toml`) et une fiche par candidat (`<candidat>.toml`). Ce module les lit, les valide
et répond aux questions des pages : qui est candidat, dans quel ordre, quelles mesures sur
quel sujet. Rien n'est écrit : publier une fiche, c'est fusionner une PR relue par Muthu.
"""

import re
import tomllib
import unicodedata
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import psycopg
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from demographie import config
from demographie.db import charger_sql

_SQL = Path(__file__).parent / "sql"

# Fichiers du dossier d'une élection qui ne sont pas des fiches de candidat.
FICHIERS_COMMUNS = {"sujets.toml", "suivis.toml"}

# Mots de jugement interdits dans ce qu'On épluche écrit (titres de mesures, libellés) :
# les mesures sont citées et rangées, jamais qualifiées. Comparaison sans accents ni
# majuscules, sur des mots entiers (« radical » refuse aussi « radicale », « radicales »).
MOTS_DE_JUGEMENT = (
    "absurde",
    "ambitieux",
    "ambitieuse",
    "audacieux",
    "audacieuse",
    "choc",
    "courageux",
    "courageuse",
    "credible",
    "dangereux",
    "dangereuse",
    "demagogique",
    "excessif",
    "excessive",
    "extreme",
    "fantaisiste",
    "irrealiste",
    "irresponsable",
    "laxiste",
    "phare",
    "populiste",
    "radical",
    "radicale",
    "realiste",
    "revolutionnaire",
    "scandaleux",
    "scandaleuse",
    "utopique",
)
_MOTS = re.compile(r"\b(" + "|".join(MOTS_DE_JUGEMENT) + r")s?\b")

Identifiant = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
CodeMajuscule = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$")]
Lien = Annotated[str, StringConstraints(pattern=r"^https://\S+$")]
Empreinte = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Texte = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Unite = Literal["EUR", "EUR_PAR_AN"]


class FicheInvalide(ValueError):
    """Une fiche ou la grille commune ne respecte pas les règles du dossier (étape 5)."""


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte.casefold())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def mots_de_jugement(texte: str) -> list[str]:
    """Les mots de jugement présents dans un texte (vide si le texte est neutre)."""
    return sorted({m.group(1) for m in _MOTS.finditer(_sans_accents(texte))})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Grille commune --------------------------------------------------------------------


class Election(_Strict):
    id: Texte
    libelle: Texte
    premier_tour: date


class Sujet(_Strict):
    id: Identifiant
    libelle: Texte
    indicateurs: list[CodeMajuscule] = []


class Echelle(_Strict):
    code: CodeMajuscule
    sujet: Identifiant
    libelle: Texte
    unite: Texte
    # Valeur en vigueur, toujours avec sa source officielle.
    valeur_actuelle: float | None = None
    source: Lien | None = None
    date_valeur: date | None = None

    @model_validator(mode="after")
    def _valeur_sourcee(self):
        if self.valeur_actuelle is not None and (self.source is None or self.date_valeur is None):
            raise ValueError(f"échelle {self.code} : une valeur en vigueur exige source et date")
        return self


class Grille(_Strict):
    election: Election
    sujets: list[Sujet]
    echelles: list[Echelle] = []

    @model_validator(mode="after")
    def _coherente(self):
        ids = [s.id for s in self.sujets]
        if len(ids) != len(set(ids)):
            raise ValueError("sujets en double")
        codes = [e.code for e in self.echelles]
        if len(codes) != len(set(codes)):
            raise ValueError("échelles en double")
        for echelle in self.echelles:
            if echelle.sujet not in ids:
                raise ValueError(f"échelle {echelle.code} : sujet inconnu « {echelle.sujet} »")
        for texte in [s.libelle for s in self.sujets] + [e.libelle for e in self.echelles]:
            if mots := mots_de_jugement(texte):
                raise ValueError(f"mot de jugement {mots} dans « {texte} »")
        return self


# --- Fiche d'un candidat ---------------------------------------------------------------


class Candidat(_Strict):
    id: Identifiant
    prenom: Texte
    nom: Texte
    parti: Texte  # libellé tel que le candidat l'écrit
    statut: Literal["declare", "officiel", "non_retenu", "retire"]
    declare_le: date
    ordre_officiel: int | None = Field(default=None, ge=1)

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom}"


class Version(_Strict):
    id: Identifiant
    titre: Texte
    url: Lien
    publie_le: date
    releve_le: date
    sha256: Empreinte


class Cout(_Strict):
    """Coût écrit par le candidat dans son programme."""

    montant: float
    unite: Unite
    version: Identifiant
    page: int | None = Field(default=None, ge=1)
    ancre: Texte | None = None


class Chiffrage(_Strict):
    """Chiffrage indépendant (organisme qui publie sa méthode), cité tel quel."""

    organisme: Texte
    montant: float
    unite: Unite
    url: Lien
    publie_le: date


class ValeurEchelle(_Strict):
    code: CodeMajuscule
    valeur: float


class Mesure(_Strict):
    id: Identifiant
    sujet: Identifiant
    titre: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    citation: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
    version: Identifiant
    page: int | None = Field(default=None, ge=1)
    ancre: Texte | None = None
    echelle: ValeurEchelle | None = None
    indicateurs: list[CodeMajuscule] = []
    cout_annonce: Cout | None = None
    retiree_dans: Identifiant | None = None
    chiffrages: list[Chiffrage] = []

    @model_validator(mode="after")
    def _reperee_et_neutre(self):
        if self.page is None and self.ancre is None:
            raise ValueError(f"mesure {self.id} : page ou ancre obligatoire")
        if mots := mots_de_jugement(self.titre):
            raise ValueError(f"mesure {self.id} : mot de jugement {mots} dans le titre")
        return self


class Fiche(_Strict):
    candidat: Candidat
    versions: list[Version] = Field(min_length=1)
    mesures: list[Mesure] = []

    @model_validator(mode="after")
    def _coherente(self):
        versions = {v.id: v for v in self.versions}
        if len(versions) != len(self.versions):
            raise ValueError("versions en double")
        ids = [m.id for m in self.mesures]
        if len(ids) != len(set(ids)):
            raise ValueError("mesures en double")
        for m in self.mesures:
            if m.version not in versions:
                raise ValueError(f"mesure {m.id} : version inconnue « {m.version} »")
            if m.cout_annonce and m.cout_annonce.version not in versions:
                raise ValueError(f"mesure {m.id} : version du coût inconnue")
            if m.retiree_dans is not None:
                retrait = versions.get(m.retiree_dans)
                if retrait is None:
                    raise ValueError(f"mesure {m.id} : version de retrait inconnue")
                if retrait.publie_le <= versions[m.version].publie_le:
                    raise ValueError(f"mesure {m.id} : retirée avant ou pendant sa version")
        return self

    def version(self, identifiant: str) -> Version:
        return next(v for v in self.versions if v.id == identifiant)

    @property
    def derniere_version(self) -> Version:
        return max(self.versions, key=lambda v: (v.publie_le, v.releve_le))

    @property
    def mesures_en_vigueur(self) -> list[Mesure]:
        return [m for m in self.mesures if m.retiree_dans is None]


# --- Lecture et questions des pages ----------------------------------------------------


@dataclass(frozen=True)
class Programmes:
    grille: Grille
    fiches: tuple[Fiche, ...]

    def sujet(self, identifiant: str) -> Sujet | None:
        return next((s for s in self.grille.sujets if s.id == identifiant), None)

    def fiche(self, identifiant: str) -> Fiche | None:
        return next((f for f in self.fiches if f.candidat.id == identifiant), None)

    @property
    def candidats(self) -> list[Fiche]:
        """Ordre d'affichage : l'ordre officiel quand il existe, sinon alphabétique par nom.

        Les candidats officiels viennent d'abord, dans l'ordre du Conseil constitutionnel ;
        les autres suivent, par nom de famille puis prénom. Les retirés et non retenus
        restent en fin de liste.
        """

        def cle(fiche: Fiche):
            c = fiche.candidat
            en_course = c.statut in ("declare", "officiel")
            return (
                not en_course,
                c.ordre_officiel is None,
                c.ordre_officiel or 0,
                _sans_accents(c.nom),
                _sans_accents(c.prenom),
            )

        return sorted(self.fiches, key=cle)

    def comparer(self, sujet: str) -> list[tuple[Fiche, list[Mesure]]]:
        """Pour un sujet, les mesures en vigueur de chaque candidat en course.

        Une liste vide veut dire « pas de proposition » : ce n'est jamais écrit dans une
        fiche, c'est déduit ici.
        """
        if self.sujet(sujet) is None:
            raise KeyError(sujet)
        return [
            (f, [m for m in f.mesures_en_vigueur if m.sujet == sujet])
            for f in self.candidats
            if f.candidat.statut in ("declare", "officiel")
        ]


def _lire_toml(chemin: Path) -> dict:
    try:
        with chemin.open("rb") as fichier:
            return tomllib.load(fichier)
    except tomllib.TOMLDecodeError as erreur:
        raise FicheInvalide(f"{chemin.name} : TOML illisible ({erreur})") from erreur


def _valider(modele: type[BaseModel], chemin: Path):
    try:
        return modele.model_validate(_lire_toml(chemin))
    except ValueError as erreur:
        if isinstance(erreur, FicheInvalide):
            raise
        raise FicheInvalide(f"{chemin.name} : {erreur}") from erreur


def charger(dossier: Path) -> Programmes:
    """Lit et valide la grille et toutes les fiches d'une élection.

    Lève FicheInvalide, avec le nom du fichier, à la première règle non respectée.
    """
    grille = _valider(Grille, dossier / "sujets.toml")
    sujets = {s.id for s in grille.sujets}
    echelles = {e.code: e for e in grille.echelles}
    fiches = []
    for chemin in sorted(dossier.glob("*.toml")):
        if chemin.name in FICHIERS_COMMUNS:
            continue
        fiche = _valider(Fiche, chemin)
        if fiche.candidat.id != chemin.stem:
            raise FicheInvalide(f"{chemin.name} : l'id du candidat doit être « {chemin.stem} »")
        for m in fiche.mesures:
            if m.sujet not in sujets:
                raise FicheInvalide(f"{chemin.name} : mesure {m.id}, sujet inconnu « {m.sujet} »")
            if m.echelle is not None:
                echelle = echelles.get(m.echelle.code)
                if echelle is None or echelle.sujet != m.sujet:
                    raise FicheInvalide(
                        f"{chemin.name} : mesure {m.id}, échelle « {m.echelle.code} » "
                        f"inconnue ou hors du sujet « {m.sujet} »"
                    )
        fiches.append(fiche)
    officiels = [f.candidat.ordre_officiel for f in fiches if f.candidat.ordre_officiel]
    if len(officiels) != len(set(officiels)):
        raise FicheInvalide("ordre officiel en double")
    return Programmes(grille=grille, fiches=tuple(fiches))


@lru_cache(maxsize=4)
def election(code: str = "2027") -> Programmes:
    """Fiches d'une élection, lues une fois par processus (un redémarrage les relit)."""
    return charger(config.charger().programmes / code)


def contexte_france(conn: psycopg.Connection, codes: list[str]) -> dict[str, dict]:
    """Pour chaque code d'indicateur : définition, source, appli de « Données » et dernière
    valeur France (``valeur`` à None si l'indicateur n'a pas de valeur nationale)."""
    if not codes:
        return {}
    lignes = conn.execute(charger_sql(_SQL, "programmes_contexte"), {"codes": codes}).fetchall()
    return {ligne["code"]: ligne for ligne in lignes}
