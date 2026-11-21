"""Lecture générique de fichiers CSV ou XLSX publiés par les producteurs (data.gouv.fr…).

Chaque source décrit son format (encodage, séparateur, séparateur décimal) ; les colonnes
sont toujours lues par leur nom, jamais par leur position. Les fichiers .gz et .zip
(un seul CSV dedans, ou celui qu'on nomme) sont ouverts sans être décompressés sur disque.
"""

import csv
import gzip
import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from demographie.imports.modele import FichierIllisible

# Champs de plus de 128 Ko (géométries, listes de parcelles) : rares mais présents dans DVF.
csv.field_size_limit(16 * 1024 * 1024)


@dataclass(frozen=True)
class FormatCSV:
    encodage: str = "utf-8-sig"
    separateur: str = ";"
    decimale: str = ","
    # Nom du fichier à lire dans une archive .zip qui en contient plusieurs.
    membre: str | None = None


def _ouvrir_texte(chemin: Path, fmt: FormatCSV) -> io.TextIOBase:
    nom = chemin.name.lower()
    if nom.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(chemin, "rb"), encoding=fmt.encodage, newline="")
    if nom.endswith(".zip"):
        archive = zipfile.ZipFile(chemin)
        csvs = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if fmt.membre is not None:
            csvs = [n for n in csvs if Path(n).name == fmt.membre]
        if len(csvs) != 1:
            raise FichierIllisible(f"Archive {chemin.name} : CSV attendu introuvable ({csvs})")
        return io.TextIOWrapper(archive.open(csvs[0]), encoding=fmt.encodage, newline="")
    return chemin.open(encoding=fmt.encodage, newline="")


def lire_csv(
    chemin: Path, fmt: FormatCSV, colonnes: frozenset[str] = frozenset()
) -> Iterator[dict[str, str]]:
    """Lignes du CSV sous forme de dictionnaires ; vérifie la présence des colonnes."""
    try:
        with _ouvrir_texte(chemin, fmt) as texte:
            lecteur = csv.DictReader(texte, delimiter=fmt.separateur)
            entete = {(c or "").strip() for c in lecteur.fieldnames or []}
            manquantes = colonnes - entete
            if manquantes:
                raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
            for ligne in lecteur:
                yield {(k or "").strip(): (v or "").strip() for k, v in ligne.items()}
    except (UnicodeDecodeError, csv.Error, zipfile.BadZipFile, gzip.BadGzipFile) as erreur:
        raise FichierIllisible(f"{chemin.name} : {erreur}") from erreur


def lire_xlsx(
    chemin: Path, feuille: str | None, ligne_entete: int, colonnes: frozenset[str] = frozenset()
) -> Iterator[dict[str, object]]:
    """Lignes d'une feuille XLSX (en-tête à la ligne indiquée, numérotée à partir de 1)."""
    try:
        classeur = load_workbook(chemin, read_only=True, data_only=True)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as erreur:
        raise FichierIllisible(f"{chemin.name} : {erreur}") from erreur
    try:
        if feuille is not None and feuille not in classeur.sheetnames:
            raise FichierIllisible(f"Feuille absente : {feuille}")
        onglet = classeur[feuille] if feuille is not None else classeur.worksheets[0]
        lignes = onglet.iter_rows(min_row=ligne_entete, values_only=True)
        entete = [str(c).strip() if c is not None else "" for c in next(lignes, ())]
        manquantes = colonnes - set(entete)
        if manquantes:
            raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
        for valeurs in lignes:
            if all(v is None for v in valeurs):
                continue
            yield dict(zip(entete, valeurs, strict=False))
    finally:
        classeur.close()


def nombre(texte: object, decimale: str = ",") -> Decimal | None:
    """Nombre lu dans une cellule ; None si vide ou secret statistique (« s », « nd »…)."""
    if texte is None:
        return None
    if isinstance(texte, int | float | Decimal):
        return Decimal(str(texte))
    brut = str(texte).strip().replace(" ", "").replace(" ", "")
    if brut in {"", "s", "nd", "NA", "n.d.", "-", "."}:
        return None
    if decimale != ".":
        brut = brut.replace(decimale, ".")
    try:
        return Decimal(brut)
    except InvalidOperation as erreur:
        raise FichierIllisible(f"Nombre illisible : {texte!r}") from erreur
