"""Comptes des administrations publiques (INSEE, comptes nationaux annuels, base 2020).

Tableaux XLSX de « Les comptes de la Nation » : dette (3.101), solde (3.106), dépenses et
recettes (3.201, 3.215), prélèvements obligatoires (3.216), dépenses par fonction (3.301,
3.307). Une ligne par poste, une colonne par année.

Découverte : la page stable « Dépenses par administration publique » renvoie, par son lien
« Chiffres détaillés », au sommaire de l'édition en cours ; le sommaire mène à chaque page
de tableaux par son titre. Les dépenses par fonction paraissent en décembre, six mois après
les autres tableaux : en attendant, on les lit dans l'édition précédente.

Le jeu Melodi DD_CNA_APU n'est pas utilisé : ses totaux ne sont pas consolidés entre
administrations et la ventilation par fonction y manque (vérifié le 22/11/2026).

La dette du dernier trimestre vient de la BDM (deux séries, API SDMX sans compte).
"""

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl
from defusedxml.ElementTree import iterparse

from demographie.imports import telechargement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

SITE = "https://www.insee.fr"
PAGE_STABLE = f"{SITE}/fr/statistiques/2381404"
# Sommaire de l'édition précédente (« Les comptes de la Nation en 2024 ») : secours tant que
# l'édition en cours n'a pas publié un tableau (dépenses par fonction, en décembre). À mettre
# à jour chaque année avec la nouvelle édition (docs/TASKS.md).
EDITIONS_SECOURS = ("8574832",)
# Les trois dernières années des comptes sont provisoires ou semi-définitives.
ANNEES_PROVISOIRES = 3

PAGE_DETTE = "Dette et déficit publics au sens de Maastricht"
PAGE_DEPENSES_RECETTES = "Dépenses et recettes des administrations publiques"
PAGE_FONCTIONS = "Dépenses des administrations publiques ventilées par fonction"

_ANNEE = re.compile(r"^(19|20)\d{2}$")
_CODE_SECTEUR = re.compile(r"^(S\d+)\b")
_CODE_OPERATION = re.compile(r"\((D\d+\w*)\)\s*$")


def _normaliser(texte: str) -> str:
    """Minuscules, sans accents ni espaces superflus ; « -Dépenses » -> « depenses »."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().replace("\xa0", " ").split()).lstrip("- ").strip()


@dataclass(frozen=True)
class Regle:
    """Une ligne du tableau à lire : sa clé (code de secteur, de fonction, d'opération ou
    libellé), et au besoin la section (« milliards », « % du produit », « recettes ») et le
    bloc (« ensemble ») où elle se trouve, ou le code de la première colonne."""

    indicateur: str
    cle: str
    modalite: tuple[str, str] | None = None
    section: str | None = None
    bloc: str | None = None
    premiere: str | None = None


@dataclass(frozen=True)
class TableauComptes:
    tableau: str  # « 3101 »
    page: str  # titre de la page de l'édition qui publie le tableau
    regles: tuple[Regle, ...]
    # Indicateur -> (dimension, modalité « autres » = total − modalités lues)
    reste: tuple[tuple[str, str, str], ...] = ()
    source: str = "INSEE_COMPTES_APU"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})

    @property
    def nom_fichier(self) -> str:
        return f"t_{self.tableau}.xlsx"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        stable = telechargement.lire_page(PAGE_STABLE)
        lien = re.search(r'href="([^"]*/fr/statistiques/(\d+))"[^>]*>\s*Chiffres détaillés', stable)
        if not lien:
            raise FichierIllisible(f"Lien « Chiffres détaillés » introuvable sur {PAGE_STABLE}")
        for edition in (lien[2], *EDITIONS_SECOURS):
            url = self._chercher(edition)
            if url:
                return [Fichier(url=url, nom=self.nom_fichier, millesime=f"édition {edition}")]
        raise FichierIllisible(f"Tableau {self.tableau} absent ({lien[2]} et secours)")

    def _chercher(self, edition: str) -> str | None:
        sommaire = telechargement.lire_page(f"{SITE}/fr/statistiques/{edition}")
        page = None
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', sommaire, re.S):
            texte = re.sub(r"<[^>]+>", " ", m[2]).replace("&nbsp;", " ")
            if _normaliser(texte) == _normaliser(self.page):
                page = m[1]
                break
        if page is None:
            return None
        contenu = telechargement.lire_page(SITE + page if page.startswith("/") else page)
        motif = rf'href="([^"]+/fichier/\d+/t_{self.tableau}(?:_fr)?\.xlsx)"'
        fichier = re.search(motif, contenu, re.I)
        if not fichier:
            return None
        return SITE + fichier[1] if fichier[1].startswith("/") else fichier[1]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            classeur = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
        except Exception as erreur:  # archive XLSX illisible
            raise FichierIllisible(f"XLSX illisible : {erreur}") from erreur
        try:
            feuilles = [f for f in classeur.worksheets if f.title.lower() != "métadonnées"]
            if not feuilles:
                raise FichierIllisible("Aucune feuille de données")
            valeurs = self._lire_feuille(feuilles[-1])
        finally:
            classeur.close()
        vues = {cle[0] for cle in valeurs}
        attendus = {r.indicateur for r in self.regles}
        if vues != attendus:
            raise FichierIllisible(f"Lignes absentes : {', '.join(sorted(attendus - vues))}")
        for indicateur, dimension, autres in self.reste:
            for (ind, modalite, annee), total in list(valeurs.items()):
                if ind != indicateur or modalite is not None:
                    continue
                parts = [v for (i, m, a), v in valeurs.items() if i == ind and a == annee and m]
                valeurs[(ind, (dimension, autres), annee)] = total - sum(parts, Decimal(0))
        derniere = max(annee for (*_x, annee) in valeurs)
        for (indicateur, modalite, annee), valeur in sorted(
            valeurs.items(), key=lambda kv: (kv[0][0], kv[0][2], str(kv[0][1]))
        ):
            yield Ligne(
                indicateur=indicateur,
                niveau="FRANCE",
                code="FR",
                periode=date(annee, 1, 1),
                periode_type="ANNEE",
                sexe="T",
                age_min=None,
                age_max=None,
                valeur=valeur,
                statut="PROVISOIRE" if annee > derniere - ANNEES_PROVISOIRES else "DEFINITIF",
                modalite=modalite,
            )

    def _lire_feuille(self, feuille) -> dict[tuple[str, tuple | None, int], Decimal]:
        annees: dict[int, int] = {}
        section = bloc = ""
        valeurs: dict[tuple[str, tuple | None, int], Decimal] = {}
        for rang in feuille.iter_rows(values_only=True):
            cellules = list(rang)
            entetes = {i: int(c) for i, c in enumerate(cellules) if _ANNEE.match(str(c or ""))}
            if len(entetes) >= 5:
                annees = entetes  # la ligne des années (une seule par tableau)
                continue
            textes = [c for c in cellules if isinstance(c, str) and c.strip()]
            nombres = {i: c for i, c in enumerate(cellules) if i in annees and _est_nombre(c)}
            if not textes:
                continue
            libelle = _normaliser(textes[1] if len(textes) > 1 and not nombres else textes[0])
            if not nombres:
                texte = _normaliser(" ".join(textes))
                if re.search(r"milliard|% du produit|^depenses|^recettes", texte):
                    section, bloc = texte, ""
                else:
                    bloc = _normaliser(textes[0])
                continue
            for regle in self.regles:
                if self._correspond(regle, cellules, textes, section, bloc):
                    for i, annee in annees.items():
                        if i in nombres:
                            cle = (regle.indicateur, regle.modalite, annee)
                            if cle in valeurs:
                                raise FichierIllisible(f"Ligne en double : {libelle}")
                            # Arrondi : les cellules calculées ont du bruit de virgule flottante.
                            valeurs[cle] = Decimal(str(round(nombres[i], 6))).normalize()
        if not annees:
            raise FichierIllisible("Ligne des années introuvable")
        return valeurs

    @staticmethod
    def _correspond(regle: Regle, cellules, textes, section: str, bloc: str) -> bool:
        if regle.section and regle.section not in section:
            return False
        if regle.bloc and _normaliser(regle.bloc) != bloc:
            return False
        premiere = str(cellules[0]).strip() if cellules and cellules[0] is not None else ""
        if regle.premiere is not None and premiere != regle.premiere:
            return False
        cles = {str(c).strip() for c in cellules[:4] if isinstance(c, str)}
        for texte in textes[:2]:
            if m := _CODE_SECTEUR.match(texte.strip()):
                cles.add(m[1])
            if m := _CODE_OPERATION.search(texte):
                cles.add(m[1])
            cles.add(_normaliser(texte))
        return regle.cle in cles or _normaliser(regle.cle) in cles


def _est_nombre(valeur: object) -> bool:
    return isinstance(valeur, int | float) and not isinstance(valeur, bool)


_ETAGES = {"S1311": "CENTRALE", "S1313": "LOCALE", "S1314": "SECU"}
FONCTIONS = {
    "GF01": "SERVICES_GENERAUX",
    "GF02": "DEFENSE",
    "GF03": "ORDRE_SECURITE",
    "GF04": "AFFAIRES_ECONOMIQUES",
    "GF05": "ENVIRONNEMENT",
    "GF06": "LOGEMENT_EQUIPEMENTS",
    "GF07": "SANTE",
    "GF08": "LOISIRS_CULTURE",
    "GF09": "ENSEIGNEMENT",
    "GF10": "PROTECTION_SOCIALE",
}

DETTE = TableauComptes(
    tableau="3101",
    page=PAGE_DETTE,
    regles=(
        Regle("DETTE_APU", "S13", section="milliard"),
        *(Regle("DETTE_APU", s, ("etage_apu", e), section="milliard") for s, e in _ETAGES.items()),
        Regle("DETTE_APU_PIB", "S13", section="% du produit"),
    ),
)

SOLDE = TableauComptes(
    tableau="3106",
    page=PAGE_DETTE,
    regles=(
        Regle("SOLDE_APU", "S13", section="milliard"),
        *(Regle("SOLDE_APU", s, ("etage_apu", e), section="milliard") for s, e in _ETAGES.items()),
        Regle("SOLDE_APU_PIB", "S13", section="% du produit"),
    ),
)

DEPENSES_RECETTES = TableauComptes(
    tableau="3215",
    page=PAGE_DEPENSES_RECETTES,
    regles=(
        Regle("DEPENSES_APU", "Dépenses", section="milliard", bloc="Ensemble"),
        Regle("RECETTES_APU", "Recettes", section="milliard", bloc="Ensemble"),
        Regle("DEPENSES_APU_PIB", "Dépenses", section="% du produit", bloc="Ensemble"),
        Regle("RECETTES_APU_PIB", "Recettes", section="% du produit", bloc="Ensemble"),
    ),
)

RECETTES_NATURE = TableauComptes(
    tableau="3201",
    page=PAGE_DEPENSES_RECETTES,
    regles=(
        Regle("CHARGE_INTERETS", "D41", section="depenses"),
        Regle("RECETTE_NATURE", "Total des recettes", section="recettes"),
        Regle("RECETTE_NATURE", "D2", ("nature_recette", "PRODUCTION"), section="recettes"),
        Regle("RECETTE_NATURE", "D5", ("nature_recette", "REVENU_PATRIMOINE"), section="recettes"),
        Regle("RECETTE_NATURE", "D61", ("nature_recette", "COTISATIONS"), section="recettes"),
    ),
    reste=(("RECETTE_NATURE", "nature_recette", "AUTRES"),),
)

PRELEVEMENTS = TableauComptes(
    tableau="3216",
    page=PAGE_DEPENSES_RECETTES,
    regles=(
        Regle("PRELEVEMENTS_OBLIGATOIRES", "S13", section="milliard"),
        Regle("PRELEVEMENTS_PIB", "S13", section="% du produit"),
    ),
)

FONCTIONS_APU = TableauComptes(
    tableau="3301",
    page=PAGE_FONCTIONS,
    regles=(
        Regle("DEPENSE_FONCTION", "_Z", premiere="OTE"),
        *(
            Regle("DEPENSE_FONCTION", gf, ("fonction_apu", m), premiere="OTE")
            for gf, m in FONCTIONS.items()
        ),
    ),
)

ETAGES_APU = TableauComptes(
    tableau="3307",
    page=PAGE_FONCTIONS,
    regles=(
        Regle("DEPENSE_ETAGE", "_Z", premiere="S13"),
        *(Regle("DEPENSE_ETAGE", "_Z", ("etage_apu", e), premiere=s) for s, e in _ETAGES.items()),
    ),
)


# --- Dette du dernier trimestre (BDM) ---------------------------------------------------

BDM = "https://api.insee.fr/series/BDM/data/SERIES_BDM/"
SERIES_DETTE = {"010777616": "DETTE_TRIMESTRIELLE", "010777608": "DETTE_TRIMESTRIELLE_PIB"}
# Multiplicateur attendu : milliards d'euros (10^9) et points de PIB.
_MULTIPLICATEURS = {"010777616": "9", "010777608": "0"}
_TRIMESTRE = re.compile(r"^(\d{4})-Q([1-4])$")


@dataclass(frozen=True)
class DetteTrimestrielle:
    source: str = "INSEE_DETTE_TRIM"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})
    nom_fichier: str = "dette-trimestrielle-apu.xml"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=BDM + "+".join(SERIES_DETTE), nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        vues: set[str] = set()
        try:
            for _evenement, element in iterparse(str(chemin), events=("end",)):
                if not element.tag.endswith("Series"):
                    continue
                attributs = element.attrib
                idbank = attributs.get("IDBANK", "")
                if (
                    idbank not in SERIES_DETTE
                    or attributs.get("FREQ") != "T"
                    or attributs.get("UNIT_MULT") != _MULTIPLICATEURS[idbank]
                    or "Base 2020" not in attributs.get("TITLE_FR", "")
                ):
                    raise FichierIllisible(f"Série inattendue : {dict(attributs)}")
                vues.add(idbank)
                for obs in element:
                    periode = _TRIMESTRE.match(obs.attrib.get("TIME_PERIOD", ""))
                    if not periode:
                        raise FichierIllisible(f"Période inattendue : {obs.attrib}")
                    debut = date(int(periode[1]), 3 * int(periode[2]) - 2, 1)
                    statut = "DEFINITIF" if obs.attrib.get("OBS_QUAL") == "DEF" else "PROVISOIRE"
                    yield Ligne(SERIES_DETTE[idbank], "FRANCE", "FR", debut, "TRIMESTRE", "T",
                                None, None, Decimal(obs.attrib["OBS_VALUE"]), statut)  # fmt: skip
                element.clear()
        except FichierIllisible:
            raise
        except Exception as erreur:  # XML mal formé ou interdit, valeur illisible
            raise FichierIllisible(f"XML illisible : {erreur}") from erreur
        manquantes = set(SERIES_DETTE) - vues
        if manquantes:
            raise FichierIllisible(f"Séries absentes : {', '.join(sorted(manquantes))}")


DETTE_TRIMESTRIELLE = DetteTrimestrielle()
