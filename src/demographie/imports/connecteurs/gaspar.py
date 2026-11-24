"""Risques naturels par département : base GASPAR de Géorisques.

Le ministère de la Transition écologique publie chaque mois, sans compte, une archive de
la base GASPAR (https://files.georisques.fr/GASPAR/gaspar.zip, 8 Mo, huit CSV séparés
par des points-virgules et nommés par la date d'extraction). On en lit deux :

- ``catnat_gaspar_AAAA-MM-JJ.csv`` : chaque reconnaissance de l'état de catastrophe
  naturelle (arrêté × commune × péril) depuis 1982 ;
- ``pprn_gaspar_AAAA-MM-JJ.csv`` : les plans de prévention des risques naturels, une
  ligne par plan et par commune, avec leur état (approuvé, prescrit, abrogé…).

Les communes sont ramenées à leur département, à leur région et à la France (« FR »,
« FM » sans l'outre-mer). Les parts de communes se rapportent aux communes du code
officiel géographique (``communes_cog.csv``, préparé par ``outils/communes_cog.py``) :
GASPAR utilise les codes des communes actuelles, et les rares codes disparus sont écartés
des parts (pas des nombres d'arrêtés). Quelques libellés de communes sont mal encodés
dans les fichiers : on ne lit que les codes.
"""

import csv
import io
import re
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

from demographie.imports.connecteurs.communes import DROM, departement_de
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

URL = "https://files.georisques.fr/GASPAR/gaspar.zip"
PREMIERE_ANNEE = 1982
# Années d'événement encore incomplètes (l'arrêté vient souvent un an après) : provisoires.
ANNEES_PROVISOIRES = 2
FENETRE_SECHERESSE = 10
# Code du péril dans GASPAR -> modalité de la dimension peril_catnat. Un code inconnu
# arrête l'import : il faut le ranger ici.
PERILS = {
    "ICB": "INONDATION",  # Inondations et/ou coulées de boue
    "IRN": "INONDATION",  # Inondations par remontée de nappe
    "COB": "INONDATION",  # Coulée de boue
    "LVT": "INONDATION",  # Lave torrentielle
    "SEC": "SECHERESSE",
    "MVT": "MOUVEMENT_TERRAIN",
    "GLT": "MOUVEMENT_TERRAIN",  # Glissement de terrain
    "EFA": "MOUVEMENT_TERRAIN",  # Effondrement et/ou affaissement
    "ECB": "MOUVEMENT_TERRAIN",  # Éboulement et/ou chute de blocs
    "GET": "MOUVEMENT_TERRAIN",  # Glissement et effondrement de terrain
    "GER": "MOUVEMENT_TERRAIN",  # Glissement et éboulement rocheux
    "CMV": "VAGUES",  # Chocs mécaniques liés à l'action des vagues
    "RAZ": "VAGUES",  # Raz de marée
    "TMP": "TEMPETE",
    "VCY": "TEMPETE",  # Vents cycloniques
    "GRL": "AUTRES",  # Grêle
    "PDN": "AUTRES",  # Poids de la neige
    "SEI": "AUTRES",  # Secousse sismique
    "AVA": "AUTRES",  # Avalanche
    "VOL": "AUTRES",  # Éruption volcanique
    "DIV": "AUTRES",  # Divers
}
MODALITES = ("INONDATION", "SECHERESSE", "MOUVEMENT_TERRAIN", "VAGUES", "TEMPETE", "AUTRES")
COLONNES_CATNAT = frozenset({"code_commune", "num_risque_jo", "date_debut", "id_gaspar"})
COLONNES_PPRN = frozenset({"CODE INSEE COMMUNE", "LIBELLE ETAT", "LIBELLE SOUS-ETAT"})
# Un plan « opposable » (approuvé, ou appliqué par anticipation) règle la construction.
ETAT_EN_VIGUEUR = "Opposable"
_NOM = re.compile(r"^(catnat|pprn)_gaspar_(\d{4})-(\d{2})-(\d{2})\.csv$")
_COG = Path(__file__).parent / "communes_cog.csv"


@cache
def communes_cog() -> frozenset[str]:
    with _COG.open(encoding="utf-8") as f:
        return frozenset(ligne["commune"] for ligne in csv.DictReader(f))


def _lecteur(archive: zipfile.ZipFile, nom: str, colonnes: frozenset[str]) -> csv.DictReader:
    flux = io.TextIOWrapper(archive.open(nom), encoding="utf-8", errors="replace", newline="")
    lecteur = csv.DictReader(flux, delimiter=";")
    manquantes = colonnes - set(lecteur.fieldnames or ())
    if manquantes:
        raise FichierIllisible(f"{nom} : colonnes absentes {sorted(manquantes)}")
    return lecteur


def _fichiers(archive: zipfile.ZipFile) -> tuple[str, str, date]:
    """Noms des fichiers catnat et pprn de l'archive, et leur date d'extraction."""
    trouves: dict[str, tuple[str, date]] = {}
    for nom in archive.namelist():
        trouve = _NOM.match(Path(nom).name)
        if trouve:
            trouves[trouve[1]] = (nom, date(int(trouve[2]), int(trouve[3]), int(trouve[4])))
    if set(trouves) != {"catnat", "pprn"}:
        raise FichierIllisible(f"Fichiers catnat et pprn introuvables : {archive.namelist()}")
    return trouves["catnat"][0], trouves["pprn"][0], trouves["catnat"][1]


@dataclass(frozen=True)
class RisquesGaspar:
    source: str = "GEORISQUES_GASPAR"
    nom_fichier: str = "gaspar.zip"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True
    # La sécheresse est reconnue en métropole seulement, et peu de DROM ont un PPRN : leurs
    # zéros sont publiés comme les autres.

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=URL, nom=self.nom_fichier)]

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        departements = sorted(referentiel.region_du_departement)
        if not departements:
            raise FichierIllisible("Référentiel des départements vide")
        try:
            archive = zipfile.ZipFile(chemin)
        except zipfile.BadZipFile as erreur:
            raise FichierIllisible(f"Archive illisible : {erreur}") from erreur
        with archive:
            catnat, pprn, extraction = _fichiers(archive)
            arretes, secheresses, derniere = self._catnat(archive, catnat, departements)
            couvertes = self._pprn(archive, pprn)
        cog = communes_cog()
        communes_par_dep: dict[str, int] = defaultdict(int)
        for commune in cog:
            communes_par_dep[departement_de(commune)] += 1

        # Reconnaissances par année d'événement, total et par péril, zéros compris.
        for annee in range(PREMIERE_ANNEE, derniere + 1):
            statut = "PROVISOIRE" if annee > derniere - ANNEES_PROVISOIRES else "DEFINITIF"
            for modalite in (None, *MODALITES):
                par_dep = {d: arretes.get((annee, modalite, d), 0) for d in departements}
                for niveau, code, valeur in _agreger(par_dep, referentiel):
                    yield _ligne("CATNAT_ARRETES", niveau, code, annee, valeur, statut, modalite)

        # Part des communes reconnues en sécheresse sur dix ans (années N-9 à N).
        for annee in range(PREMIERE_ANNEE + FENETRE_SECHERESSE - 1, derniere + 1):
            statut = "PROVISOIRE" if annee > derniere - ANNEES_PROVISOIRES else "DEFINITIF"
            touchees = {
                c
                for a in range(annee - FENETRE_SECHERESSE + 1, annee + 1)
                for c in secheresses.get(a, ())
                if c in cog
            }
            yield from self._parts("CATNAT_SECHERESSE_10ANS", touchees, communes_par_dep,
                                   annee, statut, referentiel)  # fmt: skip

        # Part des communes couvertes par un PPRN en vigueur, à la date du fichier.
        yield from self._parts("COMMUNES_PPRN", couvertes & cog, communes_par_dep,
                               extraction.year, "DEFINITIF", referentiel)  # fmt: skip

    def _catnat(self, archive, nom, departements):
        """(année, modalité ou None, département) -> nombre ; année -> communes reconnues
        en sécheresse ; dernière année d'événement."""
        connus = set(departements)
        arretes: dict[tuple[int, str | None, str], int] = defaultdict(int)
        secheresses: dict[int, set[str]] = defaultdict(set)
        vues: set[tuple[str, str, str, str]] = set()
        derniere = 0
        for ligne in _lecteur(archive, nom, COLONNES_CATNAT):
            code = ligne["num_risque_jo"].strip()
            if code not in PERILS:
                raise FichierIllisible(f"Péril inconnu « {code} » ({ligne.get('lib_risque_jo')})")
            commune = ligne["code_commune"].strip()
            departement = departement_de(commune)
            if departement not in connus:
                continue  # Saint-Pierre-et-Miquelon, Saint-Martin… : hors référentiel
            # Un arrêté peut reconnaître plusieurs événements (périodes) pour la même
            # commune et le même péril : chacun compte. Une ligne répétée ne compte qu'une fois.
            cle = (ligne["id_gaspar"].strip(), commune, code, ligne["date_debut"].strip())
            if cle in vues:
                continue
            vues.add(cle)
            try:
                annee = int(ligne["date_debut"][:4])
            except ValueError as erreur:
                raise FichierIllisible(f"Date illisible : {ligne['date_debut']!r}") from erreur
            if annee < PREMIERE_ANNEE:
                continue
            derniere = max(derniere, annee)
            modalite = PERILS[code]
            arretes[(annee, None, departement)] += 1
            arretes[(annee, modalite, departement)] += 1
            if modalite == "SECHERESSE":
                secheresses[annee].add(commune)
        if derniere == 0:
            raise FichierIllisible(f"{nom} : aucune reconnaissance lue")
        return arretes, secheresses, derniere

    @staticmethod
    def _pprn(archive, nom) -> set[str]:
        return {
            ligne["CODE INSEE COMMUNE"].strip().zfill(5)
            for ligne in _lecteur(archive, nom, COLONNES_PPRN)
            if ligne["LIBELLE ETAT"] == ETAT_EN_VIGUEUR and ligne["CODE INSEE COMMUNE"].strip()
        }

    @staticmethod
    def _parts(indicateur, communes, communes_par_dep, annee, statut, referentiel):
        par_dep: dict[str, int] = defaultdict(int)
        for commune in communes:
            par_dep[departement_de(commune)] += 1
        departements = sorted(referentiel.region_du_departement)
        numerateurs = {
            (niveau, code): valeur
            for niveau, code, valeur in _agreger(
                {d: par_dep.get(d, 0) for d in departements}, referentiel
            )
        }
        totaux = _agreger({d: communes_par_dep.get(d, 0) for d in departements}, referentiel)
        for niveau, code, total in totaux:
            if total:
                part = Decimal(100) * numerateurs[(niveau, code)] / total
                yield _ligne(indicateur, niveau, code, annee, part.quantize(Decimal("0.01")),
                             statut)  # fmt: skip


def _agreger(par_dep: dict[str, int], referentiel: Referentiel) -> Iterator[tuple]:
    """(niveau, code, valeur) des départements, puis des régions et de la France (FR, FM)."""
    regions: dict[str, int] = defaultdict(int)
    france = metropole = 0
    for departement, valeur in sorted(par_dep.items()):
        yield ("DEP", departement, valeur)
        region = referentiel.region_du_departement.get(departement)
        if region:
            regions[region] += valeur
        france += valeur
        if departement not in DROM:
            metropole += valeur
    for region, valeur in sorted(regions.items()):
        yield ("REG", region, valeur)
    yield ("FRANCE", "FR", france)
    yield ("FRANCE", "FM", metropole)


def _ligne(indicateur, niveau, code, annee, valeur, statut, modalite=None) -> Ligne:
    return Ligne(
        indicateur=indicateur,
        niveau=niveau,
        code=code,
        periode=date(annee, 1, 1),
        periode_type="ANNEE",
        sexe="T",
        age_min=None,
        age_max=None,
        valeur=valeur,
        statut=statut,
        modalite=("peril_catnat", modalite) if modalite else None,
    )


GASPAR = RisquesGaspar()
