"""Estimations de population au 1er janvier par sexe et âge quinquennal (INSEE).

Fichiers « estim-pop-dep-sexe-aq-1975-AAAA.xlsx » (départements) et
« estim-pop-nreg-sexe-aq-1975-AAAA.xlsx » (régions) : une feuille par année, un
bloc de colonnes par sexe (Ensemble, Hommes, Femmes), une colonne par tranche d'âge.

Particularités gérées :
- 1975-1989 : France métropolitaine seulement ;
- 1990-1998 : second tableau pour les départements d'outre-mer, avec une tranche
  « 90 ans et plus » au lieu de « 90 à 94 » et « 95 et plus » ;
- Mayotte à partir de 2014 ;
- les trois dernières années sont provisoires.
"""

import re
import unicodedata
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl

from demographie.imports import telechargement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

PAGE_STABLE = "https://www.insee.fr/fr/statistiques/2012692"
SITE = "https://www.insee.fr"
ANNEES_PROVISOIRES = 3

_GROUPES = {"ensemble": "T", "hommes": "H", "femmes": "F"}
_TRANCHE = re.compile(r"^(\d{1,3}) à (\d{1,3}) ans$")
_ET_PLUS = re.compile(r"^(\d{1,3}) ans et plus$")
_CODE_DEP = re.compile(r"^(\d{2}|2[AB]|97\d)$")
_AGREGATS = {
    "francemetropolitaine": ("FRANCE", "FM"),
    "francemetropolitaineetdom": ("FRANCE", "FR"),
}
_IGNORES = {"dom"}


def normaliser(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation (Centre-Val-de-Loire = Centre-Val de Loire)."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", sans_accents.lower())


def _tranche(libelle: object) -> tuple[int | None, int | None] | None:
    """(age_min, age_max) pour un en-tête de colonne d'âge, None si ce n'en est pas un."""
    if not isinstance(libelle, str):
        return None
    texte = " ".join(libelle.split())
    if texte == "Total":
        return (None, None)
    if m := _TRANCHE.match(texte):
        return (int(m[1]), int(m[2]))
    if m := _ET_PLUS.match(texte):
        return (int(m[1]), None)
    return None


def _nombre(valeur: object) -> Decimal | int | None:
    if isinstance(valeur, bool) or valeur is None:
        return None
    if isinstance(valeur, int):
        return valeur
    if isinstance(valeur, float):
        return int(valeur) if valeur.is_integer() else Decimal(str(valeur))
    return None


class _Estimations:
    """Lecture commune aux fichiers départementaux et régionaux."""

    source = "INSEE_EST"
    niveau: str
    motif: re.Pattern[str]
    niveaux_publies: frozenset[str]

    def accepte(self, nom_fichier: str) -> bool:
        return bool(self.motif.fullmatch(nom_fichier))

    def fichiers(self) -> list[Fichier]:
        """Suit le lien « Chiffres détaillés » de la page stable vers l'édition en cours."""
        page = telechargement.lire_page(PAGE_STABLE)
        lien = re.search(r'href="([^"]+/fr/statistiques/\d+)"[^>]*>\s*Chiffres détaillés', page)
        if not lien:
            raise FichierIllisible(f"Lien « Chiffres détaillés » introuvable sur {PAGE_STABLE}")
        edition = telechargement.lire_page(lien[1])
        noms = {m[1]: m[2] for m in re.finditer(r'href="([^"]+/fichier/\d+/([^"/]+))"', edition)}
        retenus = [
            Fichier(
                url=SITE + chemin if chemin.startswith("/") else chemin,
                nom=nom,
                millesime=self.motif.fullmatch(nom)[1],
            )
            for chemin, nom in noms.items()
            if self.accepte(nom)
        ]
        if len(retenus) != 1:
            raise FichierIllisible(
                f"{len(retenus)} fichier(s) {self.motif.pattern} sur {lien[1]} (1 attendu)"
            )
        return retenus

    def _territoire(self, libelle: str, referentiel: Referentiel) -> tuple[str, str] | None:
        raise NotImplementedError

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        classeur = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
        try:
            annees = sorted(int(n) for n in classeur.sheetnames if re.fullmatch(r"\d{4}", n))
            if not annees:
                raise FichierIllisible("Aucune feuille annuelle (nommée AAAA) dans le fichier")
            seuil_provisoire = annees[-1] - ANNEES_PROVISOIRES + 1
            for annee in annees:
                statut = "PROVISOIRE" if annee >= seuil_provisoire else "DEFINITIF"
                yield from self._lire_feuille(classeur[str(annee)], annee, statut, referentiel)
        finally:
            classeur.close()

    def _lire_feuille(self, feuille, annee: int, statut: str, referentiel: Referentiel):
        groupes: dict[int, str] = {}
        colonnes: dict[int, tuple[str, int | None, int | None]] = {}
        titre_vu = False
        lignes = 0
        for rang in feuille.iter_rows(values_only=True):
            cellules = list(rang)
            if not titre_vu and any(isinstance(c, str) and f"Année {annee}" in c for c in cellules):
                titre_vu = True
                continue
            trouves = {
                i: _GROUPES[c.strip().lower()]
                for i, c in enumerate(cellules)
                if isinstance(c, str) and c.strip().lower() in _GROUPES
            }
            if trouves:
                groupes = trouves
                continue
            tranches = {i: t for i, c in enumerate(cellules) if (t := _tranche(c))}
            if len(tranches) >= 3:
                if not groupes:
                    raise FichierIllisible(f"Feuille {annee} : tranches d'âge sans sexe")
                colonnes = {}
                for i, (age_min, age_max) in tranches.items():
                    debut = max((g for g in groupes if g <= i), default=None)
                    if debut is None:
                        raise FichierIllisible(f"Feuille {annee} : colonne {i} hors des groupes")
                    colonnes[i] = (groupes[debut], age_min, age_max)
                continue
            valeurs = {
                i: v
                for i in colonnes
                if i < len(cellules) and (v := _nombre(cellules[i])) is not None
            }
            if not valeurs:
                continue
            libelle = cellules[0]
            if libelle is None:
                raise FichierIllisible(f"Feuille {annee} : ligne de chiffres sans territoire")
            territoire = self._territoire(str(libelle).strip(), referentiel)
            if territoire is None:
                continue
            niveau, code = territoire
            for i, valeur in valeurs.items():
                sexe, age_min, age_max = colonnes[i]
                yield Ligne(
                    indicateur="POP",
                    niveau=niveau,
                    code=code,
                    periode=date(annee, 1, 1),
                    periode_type="1ER_JANVIER",
                    sexe=sexe,
                    age_min=age_min,
                    age_max=age_max,
                    valeur=valeur,
                    statut=statut,
                )
            lignes += 1
        if not titre_vu:
            raise FichierIllisible(f"Feuille {annee} : titre « Année {annee} » introuvable")
        if lignes == 0:
            raise FichierIllisible(f"Feuille {annee} : aucune donnée lue")


class EstimationsDepartements(_Estimations):
    niveau = "DEP"
    motif = re.compile(r"estim-pop-dep-sexe-aq-1975-(\d{4})\.xlsx")
    niveaux_publies = frozenset({"DEP", "FRANCE"})

    def _territoire(self, libelle: str, referentiel: Referentiel) -> tuple[str, str] | None:
        cle = normaliser(libelle)
        if cle in _IGNORES:
            return None
        if cle in _AGREGATS:
            return _AGREGATS[cle]
        # Code inconnu ou libellé inattendu : transmis tel quel, le pipeline le rejettera.
        return ("DEP", libelle.upper() if _CODE_DEP.match(libelle.upper()) else libelle)


class EstimationsRegions(_Estimations):
    """Le fichier régional ne donne que les libellés : on les rapproche du référentiel."""

    niveau = "REG"
    motif = re.compile(r"estim-pop-nreg-sexe-aq-1975-(\d{4})\.xlsx")
    # France et France métropolitaine viennent du fichier départemental ;
    # ici elles servent seulement à contrôler la somme des régions.
    niveaux_publies = frozenset({"REG"})

    def _territoire(self, libelle: str, referentiel: Referentiel) -> tuple[str, str] | None:
        cle = normaliser(libelle)
        if cle in _IGNORES:
            return None
        if cle in _AGREGATS:
            return _AGREGATS[cle]
        for code, lib in referentiel.libelles_regions.items():
            if normaliser(lib) == cle:
                return ("REG", code)
        return ("REG", libelle)
