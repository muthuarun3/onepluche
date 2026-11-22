"""Accidents corporels de la circulation routière (ONISR, ministère de l'Intérieur).

Dossier de conception de l'appli « Les Français sont-ils en sécurité ? », étape 6.

L'ONISR publie chaque automne sur data.gouv.fr, pour chaque année, quatre fichiers issus
des fiches d'accident (BAAC). On en lit deux, reliés par le numéro d'accident :
« caractéristiques » (le département du lieu de l'accident) et « usagers » (la gravité
pour chaque personne impliquée : tué, blessé hospitalisé, blessé léger, indemne).

Le connecteur télécharge les deux fichiers d'une année et les range dans une archive zip,
archivée comme brut. Deux formats coexistent : jusqu'en 2018, virgules, Latin-1 et
département sur trois chiffres (« 590 » pour le Nord, « 201 » pour la Corse-du-Sud) ;
depuis 2019, points-virgules, UTF-8 et code officiel. Les collectivités d'outre-mer
(Saint-Pierre-et-Miquelon, Polynésie…) sont écartées.
"""

import csv
import io
import re
import tempfile
import zipfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.connecteurs.communes import DROM
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

JEU = "https://www.data.gouv.fr/api/1/datasets/53698f4ca3a729239d2036df/"
PREMIERE_ANNEE = 2016
CARACTERISTIQUES = "caracteristiques.csv"
USAGERS = "usagers.csv"
_CARACT = re.compile(r"^(?:caract|carct)\w*[-_](\d{4})\.csv$")  # « carcteristiques » en 2021-2022
_USAGERS = re.compile(r"^usagers[-_](\d{4})\.csv$")
_NOM = re.compile(r"^accidents-(\d{4})\.zip$")
# Gravité dans le fichier « usagers » (même codage dans les deux formats).
GRAVITES = {"2": "TUES_ROUTE", "3": "BLESSES_HOSPITALISES_ROUTE"}
# Départements de France (hors collectivités d'outre-mer).
DEPARTEMENTS = frozenset({f"{n:02d}" for n in range(1, 96) if n != 20} | {"2A", "2B"} | DROM)
_ZIP_DATE = (2000, 1, 1, 0, 0, 0)  # date fixe : même contenu, même empreinte


def departement(code: str) -> str | None:
    """Code officiel du département d'un accident ; None pour une collectivité d'outre-mer."""
    code = code.strip().strip('"')
    if len(code) == 3 and not code.startswith("97"):
        # Ancien format : département sur trois chiffres, Corse en 201 et 202.
        code = {"201": "2A", "202": "2B"}.get(code, code[:2])
    if code in DEPARTEMENTS:
        return code
    if code.startswith("97") or code.startswith("98"):
        return None  # Saint-Pierre-et-Miquelon, Saint-Barthélemy, Polynésie…
    raise FichierIllisible(f"Département d'accident inconnu : {code!r}")


@dataclass(frozen=True)
class AccidentsRoute:
    source: str = "ONISR_ACCIDENTS"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True

    def _ressources(self) -> dict[int, dict[str, dict]]:
        jeu = telechargement.lire_json(JEU)
        par_annee: dict[int, dict[str, dict]] = {}
        for r in jeu.get("resources", []) if isinstance(jeu, dict) else []:
            nom = Path(str(r.get("url", ""))).name.lower()
            for type_, motif in ((CARACTERISTIQUES, _CARACT), (USAGERS, _USAGERS)):
                trouve = motif.match(nom)
                if trouve and int(trouve.group(1)) >= PREMIERE_ANNEE:
                    deja = par_annee.setdefault(int(trouve.group(1)), {}).get(type_)
                    # Une année republiée : la ressource la plus récente.
                    if deja is None or r.get("last_modified", "") > deja.get("last_modified", ""):
                        par_annee[int(trouve.group(1))][type_] = r
        return {a: f for a, f in par_annee.items() if len(f) == 2}

    def fichiers(self) -> list[Fichier]:
        annees = self._ressources()
        if not annees:
            raise FichierIllisible("Aucune année complète (caractéristiques et usagers)")
        manquantes = set(range(PREMIERE_ANNEE, max(annees) + 1)) - set(annees)
        if manquantes:
            raise FichierIllisible(f"Années incomplètes : {sorted(manquantes)}")
        return [
            Fichier(url=f[USAGERS]["url"], nom=f"accidents-{a}.zip", millesime=str(a))
            for a, f in sorted(annees.items())
        ]

    def telecharger(self, fichier: Fichier, dossier: Path) -> Path:
        """Les deux fichiers de l'année, rangés dans une archive zip."""
        trouve = _NOM.match(fichier.nom)
        if trouve is None:
            raise FichierIllisible(f"Nom de fichier inattendu : {fichier.nom}")
        ressources = self._ressources().get(int(trouve.group(1)))
        if ressources is None:
            raise FichierIllisible(f"Fichiers de {trouve.group(1)} introuvables")
        dossier.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dossier, suffix=".part", delete=False) as sortie:
            chemin = Path(sortie.name)
        try:
            with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as archive:
                for membre in (CARACTERISTIQUES, USAGERS):
                    brut = telechargement.telecharger(ressources[membre]["url"], dossier)
                    try:
                        info = zipfile.ZipInfo(membre, _ZIP_DATE)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        archive.writestr(info, brut.read_bytes())
                    finally:
                        brut.unlink(missing_ok=True)
        except BaseException:
            chemin.unlink(missing_ok=True)
            raise
        return chemin

    def accepte(self, nom_fichier: str) -> bool:
        return _NOM.match(nom_fichier) is not None

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            archive = zipfile.ZipFile(chemin)
        except zipfile.BadZipFile as erreur:
            raise FichierIllisible(f"Archive illisible : {erreur}") from erreur
        with archive:
            lieux = {
                ligne["Num_Acc"]: ligne["dep"]
                for ligne in _lignes(archive, CARACTERISTIQUES, {"Num_Acc", "dep"})
            }
            comptes: Counter[tuple[str, str, str]] = Counter()
            departements: set[str] = set()
            annees: set[int] = set()
            for ligne in _lignes(archive, USAGERS, {"Num_Acc", "grav"}):
                indicateur = GRAVITES.get(ligne["grav"].strip())
                if indicateur is None:
                    continue
                accident = ligne["Num_Acc"]
                if accident not in lieux:
                    raise FichierIllisible(f"Accident {accident} absent des caractéristiques")
                dep = departement(lieux[accident])
                if dep is None:
                    continue
                annees.add(int(accident[:4]))
                departements.add(dep)
                territoires = [("DEP", dep), ("FRANCE", "FR")]
                if dep not in DROM:
                    territoires.append(("FRANCE", "FM"))
                region = referentiel.region_du_departement.get(dep)
                if region:
                    territoires.append(("REG", region))
                for niveau, code in territoires:
                    comptes[(indicateur, niveau, code)] += 1
        if len(annees) != 1:
            raise FichierIllisible(f"Une seule année attendue par archive, lues : {annees}")
        annee = annees.pop()
        # Un département sans tué (ou sans blessé hospitalisé) compte zéro, pas « vide ».
        for indicateur in GRAVITES.values():
            for dep in departements:
                comptes[(indicateur, "DEP", dep)] += 0
        for (indicateur, niveau, code), nombre in sorted(comptes.items()):
            yield Ligne(
                indicateur=indicateur,
                niveau=niveau,
                code=code,
                periode=date(annee, 1, 1),
                periode_type="ANNEE",
                sexe="T",
                age_min=None,
                age_max=None,
                valeur=nombre,
                statut="DEFINITIF",
            )


def _lignes(archive: zipfile.ZipFile, membre: str, colonnes: set[str]) -> Iterator[dict]:
    """Lignes d'un membre de l'archive, dans l'un ou l'autre des deux formats."""
    try:
        brut = archive.read(membre)
    except KeyError as erreur:
        raise FichierIllisible(f"{membre} absent de l'archive") from erreur
    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = brut.decode("latin-1")  # ancien format
    premiere = texte.split("\n", 1)[0]
    separateur = ";" if premiere.count(";") > premiere.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(texte, newline=""), delimiter=separateur)
    entete = {(c or "").strip() for c in lecteur.fieldnames or []}
    if colonnes - entete:
        raise FichierIllisible(f"{membre} : colonnes absentes {sorted(colonnes - entete)}")
    for ligne in lecteur:
        yield {(k or "").strip(): (v or "").strip() for k, v in ligne.items()}


ACCIDENTS = AccidentsRoute()
