"""Projections climatiques par département (Banque mondiale, CMIP6 à 0,25°).

Le Climate Change Knowledge Portal de la Banque mondiale publie, sans compte, les sorties
des modèles climatiques du sixième rapport du GIEC (CMIP6), corrigées de leurs biais et
ramenées à une grille mondiale de 0,25° (721 × 1440 mailles), un fichier NetCDF par
variable, scénario, période de 20 ans et statistique de l'ensemble des modèles :

    https://wbg-cckp.s3.amazonaws.com/data/cmip6-x0.25/{variable}/ensemble-all-{ssp}/
    anomaly-{variable}-annual-mean_cmip6-x0.25_ensemble-all-{ssp}_climatology_{stat}_{période}.nc

Les fichiers « anomaly » donnent l'écart à 1995-2014. Pour chaque variable et scénario, le
téléchargement ne lit que les lignes de la grille qui couvrent la métropole (requêtes HTTP
« Range », 250 Ko au lieu de 4 à 8 Mo par fichier) et range dans un CSV la valeur de chaque
maille utile : c'est le fichier archivé. La lecture en tire la moyenne de chaque département,
pondérée par sa surface dans chaque maille (``mailles_climat.csv``, préparé par
``outils/mailles_climat.py``), et la France métropolitaine (FM), moyenne des départements
pondérée par leur surface. Une maille sans valeur (mer) est ignorée.
"""

import csv
import io
import re
import struct
import tempfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path

from demographie.imports import netcdf3, telechargement
from demographie.imports.modele import Fichier, FichierIllisible, Projection, Referentiel

PAGE = "https://climateknowledgeportal.worldbank.org/"
BASE = "https://wbg-cckp.s3.amazonaws.com/data/cmip6-x0.25"
# Variable de la Banque mondiale -> indicateur du catalogue.
VARIABLES = {
    "tas": "CLIM_TAS",
    "hd35": "CLIM_HD35",
    "tr": "CLIM_TR",
    "fd": "CLIM_FD",
    "pr": "CLIM_PR",
    "r20mm": "CLIM_R20MM",
    "cdd": "CLIM_CDD",
}
SCENARIOS = {"ssp126": "GIEC_SSP126", "ssp245": "GIEC_SSP245", "ssp585": "GIEC_SSP585"}
PERIODES = ((2020, 2039), (2040, 2059), (2060, 2079), (2080, 2099))
STATISTIQUES = {"p10": "BAS", "median": "MEDIANE", "p90": "HAUT"}
TAILLE_ENTETE = 131072
MILLESIME = "CMIP6 x0.25, mai 2023"
COLONNES = ("statistique", "debut", "fin", "latitude", "longitude", "valeur")
_NOM = re.compile(r"^climat-cmip6-([a-z0-9]+)-(ssp\d{3})\.csv$")
_MAILLES = Path(__file__).parent / "mailles_climat.csv"


def url_fichier(variable: str, ssp: str, statistique: str, periode: tuple[int, int]) -> str:
    return (
        f"{BASE}/{variable}/ensemble-all-{ssp}/anomaly-{variable}-annual-mean_cmip6-x0.25_"
        f"ensemble-all-{ssp}_climatology_{statistique}_{periode[0]}-{periode[1]}.nc"
    )


@cache
def mailles() -> dict[str, list[tuple[float, float, float]]]:
    """Département -> [(latitude, longitude, km²)] des mailles qui le couvrent."""
    resultat: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    with _MAILLES.open(encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            resultat[ligne["departement"]].append(
                (float(ligne["latitude"]), float(ligne["longitude"]), float(ligne["km2"]))
            )
    return dict(resultat)


def _cellules() -> set[tuple[float, float]]:
    return {(lat, lon) for liste in mailles().values() for lat, lon, _ in liste}


def _grille_france(url: str) -> dict[tuple[float, float], float | None]:
    """Valeurs des mailles utiles d'un fichier, lues par plages d'octets."""
    try:
        entete = netcdf3.lire_octets(telechargement.lire_plage(url, 0, TAILLE_ENTETE - 1))
    except (netcdf3.NetCDFIllisible, struct.error, UnicodeDecodeError) as erreur:
        raise FichierIllisible(f"En-tête NetCDF illisible ({erreur}) : {url}") from erreur
    donnees = [v for v in entete.variables.values() if v.nom.startswith("anomaly-")]
    if len(donnees) != 1 or donnees[0].dimensions != ("time", "lat", "lon"):
        raise FichierIllisible(f"Variable « anomaly-… » (time, lat, lon) introuvable : {url}")
    variable = donnees[0]
    latitudes = entete.variables["lat"]
    longitudes = entete.variables["lon"]
    # Les axes sont réguliers (-90 à 90, -180 à 179,75, pas de 0,25) : on le vérifie sur
    # les premiers et derniers points, lus avec l'en-tête.
    if latitudes.type_nc != 5 or longitudes.type_nc != 5 or variable.type_nc != 5:
        raise FichierIllisible(f"Réels simple précision attendus : {url}")
    lat = struct.unpack(">2f", telechargement.lire_plage(url, latitudes.debut, latitudes.debut + 7))
    lon = struct.unpack(
        ">2f", telechargement.lire_plage(url, longitudes.debut, longitudes.debut + 7)
    )
    if (lat, lon, variable.forme[1:]) != ((-90.0, -89.75), (-180.0, -179.75), (721, 1440)):
        raise FichierIllisible(f"Grille inattendue : {url}")
    utiles = _cellules()
    lignes = sorted({round((la + 90) / 0.25) for la, _ in utiles})
    premiere, derniere = lignes[0], lignes[-1]
    largeur = variable.forme[2]
    debut = variable.debut + premiere * largeur * variable.taille_valeur
    fin = variable.debut + (derniere + 1) * largeur * variable.taille_valeur - 1
    brut = telechargement.lire_plage(url, debut, fin)
    valeurs = struct.unpack(f">{len(brut) // 4}f", brut)
    manquante = variable.attributs.get("_FillValue", [None])[0]
    resultat = {}
    for la, lo in utiles:
        i = round((la + 90) / 0.25) - premiere
        j = round((lo + 180) / 0.25)
        x = valeurs[i * largeur + j]
        absente = x != x or (manquante is not None and abs(x - manquante) < 1e10)
        resultat[(la, lo)] = None if absente or abs(x) > 1e10 else round(x, 4)
    return resultat


@dataclass(frozen=True)
class ClimatCMIP6:
    source: str = "BM_CMIP6"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "DEP"})
    projections: bool = True
    lit_le_nom: bool = True
    departements_attendus: int = 96
    # Les fichiers datent de mai 2023 (attribut « creation_date ») : une fois importés, ils
    # ne sont pas relus chaque semaine. Une nouvelle version changera ce millésime.
    saute_si_millesime_connu: bool = True

    def fichiers(self) -> list[Fichier]:
        return [
            Fichier(
                url=f"{BASE}/{variable}/ensemble-all-{ssp}/",
                nom=f"climat-cmip6-{variable}-{ssp}.csv",
                millesime=MILLESIME,
            )
            for variable in VARIABLES
            for ssp in SCENARIOS
        ]

    def accepte(self, nom_fichier: str) -> bool:
        trouve = _NOM.match(nom_fichier)
        return bool(trouve) and trouve[1] in VARIABLES and trouve[2] in SCENARIOS

    def telecharger(self, fichier: Fichier, dossier: Path) -> Path:
        """Les douze fichiers de la variable et du scénario (4 périodes × 3 statistiques),
        réduits aux mailles de la métropole, dans un CSV."""
        trouve = _NOM.match(fichier.nom)
        if trouve is None or not self.accepte(fichier.nom):
            raise FichierIllisible(f"Nom de fichier inattendu : {fichier.nom}")
        variable, ssp = trouve[1], trouve[2]
        texte = io.StringIO()
        ecrivain = csv.writer(texte, lineterminator="\n")
        ecrivain.writerow(COLONNES)
        for statistique in STATISTIQUES:
            for periode in PERIODES:
                grille = _grille_france(url_fichier(variable, ssp, statistique, periode))
                for (lat, lon), valeur in sorted(grille.items()):
                    ecrivain.writerow(
                        (statistique, *periode, lat, lon, "" if valeur is None else valeur)
                    )
        dossier.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=dossier, suffix=".part", delete=False, encoding="utf-8"
        ) as sortie:
            sortie.write(texte.getvalue())
        return Path(sortie.name)

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Projection]:
        trouve = _NOM.match(chemin.name)
        if trouve is None or not self.accepte(chemin.name):
            raise FichierIllisible(f"Nom de fichier inattendu : {chemin.name}")
        indicateur, scenario = VARIABLES[trouve[1]], SCENARIOS[trouve[2]]
        # (statistique, début, fin) -> {(lat, lon): valeur}
        grilles: dict[tuple[str, int, int], dict[tuple[float, float], float]] = defaultdict(dict)
        with chemin.open(encoding="utf-8") as f:
            lecteur = csv.DictReader(f)
            if tuple(lecteur.fieldnames or ()) != COLONNES:
                raise FichierIllisible(f"Colonnes inattendues : {lecteur.fieldnames}")
            for ligne in lecteur:
                if ligne["statistique"] not in STATISTIQUES:
                    raise FichierIllisible(f"Statistique inconnue : {ligne['statistique']}")
                if ligne["valeur"] == "":
                    continue
                cle = (ligne["statistique"], int(ligne["debut"]), int(ligne["fin"]))
                position = (float(ligne["latitude"]), float(ligne["longitude"]))
                grilles[cle][position] = float(ligne["valeur"])
        attendues = {(s, *p) for s in STATISTIQUES for p in PERIODES}
        if set(grilles) != attendues:
            manquantes = sorted(attendues - set(grilles))
            raise FichierIllisible(f"Périodes ou statistiques manquantes : {manquantes}")
        for (statistique, debut, fin), grille in sorted(grilles.items()):
            france_somme = france_surface = 0.0
            for departement, liste in sorted(mailles().items()):
                connues = [(grille[(la, lo)], km2) for la, lo, km2 in liste if (la, lo) in grille]
                surface = sum(km2 for _, _, km2 in liste)
                couverte = sum(km2 for _, km2 in connues)
                # Un département dont moins de la moitié de la surface a une valeur (mailles
                # en mer) est laissé sans valeur plutôt que décrit par une maille voisine.
                if couverte < surface / 2:
                    continue
                valeur = sum(v * km2 for v, km2 in connues) / couverte
                france_somme += valeur * surface
                france_surface += surface
                yield self._projection(indicateur, "DEP", departement, scenario, statistique,
                                       debut, fin, valeur)  # fmt: skip
            if france_surface:
                yield self._projection(indicateur, "FRANCE", "FM", scenario, statistique,
                                       debut, fin, france_somme / france_surface)  # fmt: skip

    @staticmethod
    def _projection(indicateur, niveau, code, scenario, statistique, debut, fin, valeur):
        return Projection(
            indicateur=indicateur,
            niveau=niveau,
            code=code,
            scenario=scenario,
            periode=date(debut, 1, 1),
            periode_fin=date(fin, 12, 31),
            valeur=round(valeur, 2),
            statistique=STATISTIQUES[statistique],
        )


CLIMAT = ClimatCMIP6()
