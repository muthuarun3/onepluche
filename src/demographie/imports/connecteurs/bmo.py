"""Appli « Comment travaillent les Français ? », PR T2 : enquête Besoins en main-d'œuvre.

Chaque printemps, France Travail interroge les employeurs sur leurs projets de recrutement
de l'année et publie, sur data.gouv.fr, un fichier xlsx : une ligne par métier (217 codes
BMO, regroupés en 8 familles) et par bassin d'emploi, avec le nombre de projets, de
projets jugés difficiles et de projets saisonniers. Seuls les fichiers xlsx (2025 et
après) ont ce format ; les années précédentes sont des archives d'une autre forme.

Les bassins sont additionnés par département, puis par région et pour la France. Les
petites valeurs sont masquées par France Travail (« * ») et comptent pour zéro : les
totaux sont un peu sous-estimés, surtout pour les projets difficiles (sur la
France en 2025 : 49,6 % de projets difficiles, 55,2 % si on ne garde que les lignes où
les deux nombres sont publiés). La part de projets difficiles est calculée à la
lecture, pour l'ensemble et pour chaque famille de métiers.

Dossier de conception de l'appli travail, étapes 5 à 7.
"""

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from demographie.imports import telechargement
from demographie.imports.connecteurs import fichier
from demographie.imports.connecteurs.communes import DROM
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

JEU = "https://www.data.gouv.fr/api/1/datasets/561fa564c751df4f2acdbb48/"
RESSOURCE = "Enquête BMO "
PREMIERE_ANNEE = 2025
COLONNES = frozenset({"annee", "Code métier BMO", "Famille_met", "REG", "Dept", "met", "xmet"})
FAMILLES = frozenset("ACIOSTVZ")
# Colonne du fichier -> indicateur.
MESURES = {"met": "PROJETS_RECRUTEMENT", "xmet": "RECRUTEMENTS_DIFFICILES"}


@dataclass(frozen=True)
class BesoinsMainOeuvre:
    source: str = "FT_BMO"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    tolerance_sommes: float = 0.0  # la France est la somme des départements
    controle_couverture: bool = True
    departements_absents: frozenset[str] = frozenset()

    def fichiers(self) -> list[Fichier]:
        jeu = telechargement.lire_json(JEU)
        ressources = jeu.get("resources", []) if isinstance(jeu, dict) else []
        retenus = []
        for r in ressources:
            titre, url = str(r.get("title", "")), str(r.get("url", ""))
            annee = titre.removeprefix(RESSOURCE)
            xlsx = titre.startswith(RESSOURCE) and url.lower().endswith(".xlsx")
            if xlsx and annee.isdigit() and int(annee) >= PREMIERE_ANNEE:
                retenus.append(Fichier(url=url, nom=f"bmo-{annee}.xlsx", millesime=annee))
        if not retenus:
            raise FichierIllisible(f"Aucune ressource « {RESSOURCE}… » en xlsx")
        return sorted(retenus, key=lambda f: f.nom)

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier.startswith("bmo-") and nom_fichier.endswith(".xlsx")

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        feuille = _feuille(chemin)
        # (indicateur, niveau, code, modalité) -> somme des bassins
        sommes: dict[tuple[str, str, str, tuple[str, str] | None], int] = defaultdict(int)
        annees: set[int] = set()
        for ligne in fichier.lire_xlsx(chemin, feuille, 1, COLONNES):
            annees.add(int(str(ligne["annee"])))
            famille, metier = str(ligne["Famille_met"]), str(ligne["Code métier BMO"])
            if famille not in FAMILLES:
                raise FichierIllisible(f"Famille de métiers inattendue : {famille}")
            departement = str(ligne["Dept"]).zfill(2)
            region = referentiel.region_du_departement.get(departement, str(ligne["REG"]))
            territoires = [("DEP", departement), ("REG", region), ("FRANCE", "FR")]
            if departement not in DROM:
                territoires.append(("FRANCE", "FM"))
            for colonne, indicateur in MESURES.items():
                valeur = _effectif(ligne[colonne])
                for niveau, code in territoires:
                    for modalite in (None, ("famille_metier", famille), ("metier_bmo", metier)):
                        sommes[(indicateur, niveau, code, modalite)] += valeur
        if len(annees) != 1:
            raise FichierIllisible(f"Une seule année attendue, lues : {sorted(annees)}")
        periode = date(annees.pop(), 1, 1)
        for (indicateur, niveau, code, modalite), valeur in sorted(
            sommes.items(), key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3] or ("", ""))
        ):
            yield Ligne(indicateur, niveau, code, periode, "ANNEE", "T", None, None, valeur,
                        "DEFINITIF", modalite)  # fmt: skip
            if indicateur != "PROJETS_RECRUTEMENT" or (
                modalite and modalite[0] != "famille_metier"
            ):
                continue
            difficiles = sommes[("RECRUTEMENTS_DIFFICILES", niveau, code, modalite)]
            if valeur:
                part = (Decimal(100) * difficiles / valeur).quantize(Decimal("0.1"))
                yield Ligne("PART_RECRUTEMENTS_DIFFICILES", niveau, code, periode, "ANNEE",
                            "T", None, None, part, "DEFINITIF", modalite)  # fmt: skip


def _feuille(chemin: Path) -> str:
    """Feuille des données (« BMO_2026_open_data ») : son nom porte l'année."""
    classeur = load_workbook(chemin, read_only=True)
    try:
        feuilles = [f for f in classeur.sheetnames if f.endswith("_open_data")]
    finally:
        classeur.close()
    if len(feuilles) != 1:
        raise FichierIllisible(f"Feuille « …_open_data » introuvable ou en double : {feuilles}")
    return feuilles[0]


def _effectif(cellule: object) -> int:
    if cellule == "*":  # secret statistique : petite valeur masquée
        return 0
    valeur = fichier.nombre(cellule, ".")
    if valeur is None or valeur != int(valeur):
        raise FichierIllisible(f"Nombre de projets illisible : {cellule!r}")
    return int(valeur)


BMO = BesoinsMainOeuvre()
