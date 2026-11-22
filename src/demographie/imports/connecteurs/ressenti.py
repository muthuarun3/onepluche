"""Sentiment d'insécurité : enquêtes de victimation du SSMSI (ministère de l'Intérieur).

Dossier de conception de l'appli « Les Français sont-ils en sécurité ? », étape 6.

Deux enquêtes se suivent sans se raccorder :

- « Cadre de vie et sécurité » (CVS, Insee et SSMSI), en face à face, chaque année de 2007
  à 2019 pour les données ouvertes, personnes de 14 ans ou plus de France métropolitaine.
  Fichier « cube » sur data.gouv.fr, chargé une fois puisque l'enquête est arrêtée.
- « Vécu et ressenti en matière de sécurité » (VRS, SSMSI), par internet depuis 2022,
  personnes de 18 ans ou plus. Ses résultats ne sont publiés qu'en rapports : les chiffres
  sont recopiés dans `imports/fichiers/vrs.csv`, chacun avec l'adresse de sa page.

Les deux sont rangés en France métropolitaine (le champ de VRS 2024 ajoute trois DROM,
signalé dans l'avertissement des indicateurs). En décembre, si l'année précédente manque
dans `vrs.csv`, l'import le signale : un nouveau rapport est sans doute paru.
"""

import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.connecteurs import fichier
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

JEU_CVS = "https://www.data.gouv.fr/api/1/datasets/62029493ff5c2e6d510b42b6/"
RESSOURCE_CVS = "Résultats détaillés (format .csv)"
FORMAT_CVS = fichier.FormatCSV(encodage="utf-8-sig", separateur=",", decimale=".")
COLONNES_CVS = frozenset({"MODULE_ENQUETE", "VENTILATION", "MILLESIME", "PROP_ENSEMBLE"})
# Module de l'enquête CVS -> indicateur.
MODULES = {
    "Sentiment d’insécurité dans le quartier ou le village": "PART_INSECURITE_QUARTIER",
    "Sentiment d’insécurité au domicile": "PART_INSECURITE_DOMICILE",
    "Renoncement à sortir seul de chez soi pour des raisons de sécurité": "PART_RENONCE_SORTIR",
}
INDICATEURS = frozenset(MODULES.values())

VRS = Path(__file__).resolve().parents[1] / "fichiers" / "vrs.csv"
URL_VRS = (
    "https://github.com/muthuarun3/onepluche/blob/main/src/demographie/imports/fichiers/vrs.csv"
)
FORMAT_VRS = fichier.FormatCSV(encodage="utf-8", separateur=";", decimale=",")
COLONNES_VRS = frozenset({"indicateur", "annee", "valeur", "champ", "source"})


def _ligne(indicateur: str, annee: int, valeur: Decimal) -> Ligne:
    if not 0 <= valeur <= 100:
        raise FichierIllisible(f"{indicateur} {annee} : part hors de 0-100 ({valeur})")
    return Ligne(
        indicateur=indicateur,
        niveau="FRANCE",
        code="FM",
        periode=date(annee, 1, 1),
        periode_type="ANNEE",
        sexe="T",
        age_min=None,
        age_max=None,
        valeur=valeur,
        statut="DEFINITIF",
    )


@dataclass(frozen=True)
class EnqueteCVS:
    source: str = "SSMSI_CVS"
    nom_fichier: str = "cvs-cube.csv"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})

    def fichiers(self) -> list[Fichier]:
        jeu = telechargement.lire_json(JEU_CVS)
        ressources = jeu.get("resources", []) if isinstance(jeu, dict) else []
        retenues = [r for r in ressources if str(r.get("title", "")).startswith(RESSOURCE_CVS)]
        if len(retenues) != 1:
            raise FichierIllisible(f"Ressource « {RESSOURCE_CVS} » introuvable ou en double")
        return [Fichier(url=retenues[0]["url"], nom=self.nom_fichier)]

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        vus = set()
        for ligne in fichier.lire_csv(chemin, FORMAT_CVS, COLONNES_CVS):
            indicateur = MODULES.get(ligne["MODULE_ENQUETE"])
            # Ventilation vide = ensemble des personnes interrogées.
            if indicateur is None or ligne["VENTILATION"]:
                continue
            part = fichier.nombre(ligne["PROP_ENSEMBLE"], ".")
            if part is None:
                continue
            vus.add(indicateur)
            yield _ligne(indicateur, int(ligne["MILLESIME"]), part.quantize(Decimal("0.1")))
        if vus != INDICATEURS:
            raise FichierIllisible(f"Modules absents : {', '.join(sorted(INDICATEURS - vus))}")


@dataclass(frozen=True)
class EnqueteVRS:
    source: str = "SSMSI_VRS"
    nom_fichier: str = "vrs.csv"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})
    chemin: Path = field(default=VRS)

    def fichiers(self) -> list[Fichier]:
        aujourd_hui = date.today()
        annees = {int(x["annee"]) for x in fichier.lire_csv(self.chemin, FORMAT_VRS)}
        if aujourd_hui.month == 12 and max(annees, default=0) < aujourd_hui.year - 1:
            raise FichierIllisible(
                f"Rapport VRS {aujourd_hui.year - 1} sans doute paru : compléter "
                "src/demographie/imports/fichiers/vrs.csv"
            )
        return [Fichier(url=URL_VRS, nom=self.nom_fichier)]

    def telecharger(self, fichier_: Fichier, dossier: Path) -> Path:
        """Le fichier est dans le dépôt : simple copie."""
        dossier.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dossier, suffix=".part", delete=False) as sortie:
            copie = Path(sortie.name)
        shutil.copyfile(self.chemin, copie)
        return copie

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        for ligne in fichier.lire_csv(chemin, FORMAT_VRS, COLONNES_VRS):
            if ligne["indicateur"] not in INDICATEURS:
                raise FichierIllisible(f"Indicateur inconnu dans vrs.csv : {ligne['indicateur']}")
            if not ligne["source"].startswith("https://"):
                raise FichierIllisible(f"Source manquante : {ligne['indicateur']} {ligne['annee']}")
            valeur = fichier.nombre(ligne["valeur"], ",")
            if valeur is None:
                raise FichierIllisible(f"Valeur vide : {ligne['indicateur']} {ligne['annee']}")
            yield _ligne(ligne["indicateur"], int(ligne["annee"]), valeur)


CVS = EnqueteCVS()
VRS_RAPPORTS = EnqueteVRS()
