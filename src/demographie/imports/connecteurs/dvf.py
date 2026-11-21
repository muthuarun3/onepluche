"""Ventes immobilières (DVF géolocalisées, Etalab) : prix de vente médian au m².

Un fichier national par année (`full.csv.gz`, environ 100 Mo), une ligne par parcelle et
par local vendu : les lignes d'une même vente (`id_mutation`) se suivent. Règles du
dossier de conception de l'appli 2, étape 6 :
- ventes (« Vente ») d'un seul logement, appartement ou maison ; les dépendances
  (garage, cave) sont admises, tout autre local (commerce, bureau) exclut la vente ;
- surface réelle bâtie d'au moins 9 m² et prix d'au moins 1 000 € ;
- dans chaque territoire, le 1 % des prix au m² les plus bas et le 1 % les plus hauts
  sont écartés, puis la médiane est publiée si au moins 30 ventes restent.
Les médianes de région et de France sont calculées sur les ventes elles-mêmes, pas sur
les médianes départementales. Alsace-Moselle et Mayotte sont absentes de DVF : la région
Grand Est n'est pas publiée, la France l'est (hors ces départements).
"""

import re
import statistics
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.connecteurs import communes, fichier
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

INDEX = "https://files.data.gouv.fr/geo-dvf/latest/csv/"
URL = INDEX + "{annee}/full.csv.gz"
FORMAT = fichier.FormatCSV(encodage="utf-8", separateur=",", decimale=".")
COLONNES = frozenset({
    "id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere", "code_commune",
    "code_departement", "type_local", "surface_reelle_bati", "id_parcelle", "lot1_numero",
})  # fmt: skip
LOGEMENTS = {"Appartement": "APPARTEMENT", "Maison": "MAISON"}
DEPENDANCE = "Dépendance"
SURFACE_MIN = Decimal(9)
PRIX_MIN = Decimal(1000)
EXCLUS = 0.01  # part écartée de chaque côté
VENTES_MIN = 30
ABSENTS = frozenset({"57", "67", "68", "976"})
REGIONS_INCOMPLETES = frozenset({"44"})  # Grand Est, sans l'Alsace ni la Moselle
DROM = frozenset({"971", "972", "973", "974", "976"})
_NOM = re.compile(r"^dvf-(\d{4})\.csv\.gz$")


@dataclass(frozen=True)
class _Vente:
    departement: str
    type_logement: str
    prix_m2: float


def _ventes(chemin: Path) -> Iterator[tuple[_Vente, date]]:
    """Ventes retenues du fichier, avec leur date."""
    courante: list[dict[str, str]] = []
    vues: set[str] = set()
    for ligne in fichier.lire_csv(chemin, FORMAT, COLONNES):
        if courante and ligne["id_mutation"] != courante[0]["id_mutation"]:
            yield from _retenue(courante)
            courante = []
        if not courante:
            if ligne["id_mutation"] in vues:
                raise FichierIllisible(f"Lignes de la vente {ligne['id_mutation']} dispersées")
            vues.add(ligne["id_mutation"])
        courante.append(ligne)
    if courante:
        yield from _retenue(courante)


def _retenue(lignes: list[dict[str, str]]) -> Iterator[tuple[_Vente, date]]:
    premiere = lignes[0]
    if premiere["nature_mutation"] != "Vente":
        return
    locaux = set()
    for ligne in lignes:
        type_local = ligne["type_local"]
        if not type_local or type_local == DEPENDANCE:
            continue
        if type_local not in LOGEMENTS:
            return  # commerce, bureau, local industriel
        # Un même local revient sur chaque parcelle ou culture de la vente.
        locaux.add(
            (type_local, ligne["surface_reelle_bati"], ligne["id_parcelle"], ligne["lot1_numero"])
        )
    if len(locaux) != 1:
        return
    type_local, surface_texte, _parcelle, _lot = locaux.pop()
    surface = fichier.nombre(surface_texte, ".")
    prix = fichier.nombre(premiere["valeur_fonciere"], ".")
    if surface is None or prix is None or surface < SURFACE_MIN or prix < PRIX_MIN:
        return
    departement = premiere["code_departement"] or communes.departement_de(premiere["code_commune"])
    vente = _Vente(departement, LOGEMENTS[type_local], float(prix / surface))
    yield vente, date.fromisoformat(premiere["date_mutation"])


def mediane_tronquee(prix: list[float]) -> Decimal | None:
    """Médiane après exclusion des 1 % extrêmes ; None sous 30 ventes restantes."""
    prix = sorted(prix)
    exclus = int(len(prix) * EXCLUS)
    gardes = prix[exclus : len(prix) - exclus]
    if len(gardes) < VENTES_MIN:
        return None
    return Decimal(statistics.median(gardes)).quantize(Decimal(1))


@dataclass(frozen=True)
class VentesDVF:
    source: str = "DGFIP_DVF"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True
    departements_absents: frozenset[str] = ABSENTS
    lit_le_nom: bool = True  # l'année n'est que dans le nom du fichier

    def fichiers(self) -> list[Fichier]:
        """Une année par dossier de l'index (DVF couvre les 5 dernières années)."""
        page = telechargement.lire_page(INDEX)
        annees = sorted({int(a) for a in re.findall(r'href="[^"]*/(\d{4})/"', page)})
        if not annees:
            raise FichierIllisible("Aucune année trouvée dans l'index DVF")
        return [
            Fichier(url=URL.format(annee=a), nom=f"dvf-{a}.csv.gz", millesime=str(a))
            for a in annees
        ]

    def accepte(self, nom_fichier: str) -> bool:
        return _NOM.match(nom_fichier) is not None

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        trouve = _NOM.match(chemin.name)
        if trouve is None:
            raise FichierIllisible(f"Nom de fichier inattendu : {chemin.name}")
        annee = int(trouve.group(1))
        prix: dict[tuple[str, str, str | None], list[float]] = defaultdict(list)
        derniere_vente = None
        for vente, jour in _ventes(chemin):
            if jour.year != annee:
                raise FichierIllisible(f"Vente du {jour} dans le fichier {annee}")
            derniere_vente = max(derniere_vente or jour, jour)
            region = referentiel.region_du_departement.get(vente.departement)
            territoires = [("DEP", vente.departement), ("FRANCE", "FR")]
            if region and region not in REGIONS_INCOMPLETES:
                territoires.append(("REG", region))
            if vente.departement not in DROM:
                territoires.append(("FRANCE", "FM"))
            for territoire in territoires:
                prix[(*territoire, None)].append(vente.prix_m2)
                prix[(*territoire, vente.type_logement)].append(vente.prix_m2)
        if derniere_vente is None:
            raise FichierIllisible("Aucune vente retenue")
        # Une année est complète une fois décembre publié (DVF paraît par semestre).
        statut = "DEFINITIF" if derniere_vente.month == 12 else "PROVISOIRE"
        for (niveau, code, type_logement), valeurs in sorted(
            prix.items(), key=lambda e: (e[0][0], e[0][1], e[0][2] or "")
        ):
            mediane = mediane_tronquee(valeurs)
            if mediane is None:
                continue
            yield Ligne(
                indicateur="PRIX_VENTE_M2",
                niveau=niveau,
                code=code,
                periode=date(annee, 1, 1),
                periode_type="ANNEE",
                sexe="T",
                age_min=None,
                age_max=None,
                valeur=mediane,
                statut=statut,
                modalite=("type_logement", type_logement) if type_logement else None,
            )


VENTES = VentesDVF()
