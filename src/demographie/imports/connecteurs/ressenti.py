"""Sentiment d'insécurité : enquêtes de victimation du SSMSI (ministère de l'Intérieur).

Dossier de conception de l'appli « Les Français sont-ils en sécurité ? », étape 6.

Deux enquêtes se suivent sans se raccorder :

- « Cadre de vie et sécurité » (CVS, Insee et SSMSI), en face à face, chaque année de 2007
  à 2019 pour les données ouvertes, personnes de 14 ans ou plus de France métropolitaine.
  Fichier « cube » sur data.gouv.fr, chargé une fois puisque l'enquête est arrêtée.
- « Vécu et ressenti en matière de sécurité » (VRS, SSMSI), par internet depuis 2022,
  personnes de 18 ans ou plus. Le SSMSI ne publie ses résultats qu'en rapports ; l'Insee
  en reprend chaque mois de novembre les parts nationales dans la fiche « Insécurité,
  victimation » de France, portrait social, avec un tableur. Le connecteur cherche ces
  fiches dans le moteur de recherche de l'Insee et lit la figure du sentiment
  d'insécurité (colonne de l'ensemble des 18 ans ou plus).

Les deux sont rangés en France métropolitaine (le champ de VRS 2024 ajoute trois DROM,
signalé dans l'avertissement des indicateurs).
"""

import re
import unicodedata
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

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

# Fiches « Insécurité, victimation » de l'Insee (France, portrait social), depuis
# l'édition de novembre 2024, la première à reprendre l'enquête VRS.
RECHERCHE_INSEE = "https://www.insee.fr/fr/solr/consultation"
TITRE_FICHE = "Insécurité, victimation"
PREMIERE_FICHE_VRS = "2024-11-01"
PAGE_FICHE = "https://www.insee.fr/fr/statistiques/{id}"
_TABLEUR = re.compile(r'href="(/fr/statistiques/fichier/(\d+)/[\w.-]+\.xlsx)"')
_NOM_VRS = re.compile(r"^insee-victimation-(\d+)\.xlsx$")
_ANNEE_VRS = re.compile(r"\(VRS\) (\d{4})")
# Début du libellé de ligne de la figure (sans accents ni apostrophes) -> indicateur.
LIGNES_VRS = {
    "sentiment dinsecurite dans le quartier": "PART_INSECURITE_QUARTIER",
    "sentiment dinsecurite au domicile": "PART_INSECURITE_DOMICILE",
    "renoncement a sortir seul": "PART_RENONCE_SORTIR",
}
COLONNES_ENSEMBLE = ("18 ans ou plus", "ensemble")


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


def _simple(texte: object) -> str:
    """« Sentiment d’insécurité » -> « sentiment dinsecurite » (comparaison des libellés)."""
    sans_accents = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore")
    return re.sub(r"[^a-z0-9 ]", "", sans_accents.decode().lower().replace("\xa0", " "))


@dataclass(frozen=True)
class FichesInsee:
    source: str = "SSMSI_VRS"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})

    def fichiers(self) -> list[Fichier]:
        reponse = telechargement.lire_json(
            RECHERCHE_INSEE,
            donnees={
                "q": TITRE_FICHE,
                "start": 0,
                "rows": 50,
                "sortFields": [{"field": "dateDiffusion", "order": "desc"}],
                "filters": [],
                "facetsField": [],
            },
        )
        documents = reponse.get("documents", []) if isinstance(reponse, dict) else []
        fiches = [
            d
            for d in documents
            if d.get("titre") == TITRE_FICHE
            and str(d.get("dateDiffusion", "")) >= PREMIERE_FICHE_VRS
        ]
        if not fiches:
            raise FichierIllisible(f"Aucune fiche « {TITRE_FICHE} » trouvée à l'Insee")
        resultat = []
        for fiche in fiches:
            page = telechargement.lire_page(PAGE_FICHE.format(id=int(fiche["id"])))
            tableurs = {
                chemin for chemin, ident in _TABLEUR.findall(page) if ident == str(fiche["id"])
            }
            if len(tableurs) != 1:
                raise FichierIllisible(f"Tableur de la fiche Insee {fiche['id']} introuvable")
            resultat.append(
                Fichier(
                    url="https://www.insee.fr" + tableurs.pop(),
                    nom=f"insee-victimation-{int(fiche['id'])}.xlsx",
                    millesime=str(fiche.get("dateDiffusion", ""))[:10] or None,
                )
            )
        return resultat

    def accepte(self, nom_fichier: str) -> bool:
        return _NOM_VRS.match(nom_fichier) is not None

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        # Ouvert par son contenu : le brut archivé n'a pas l'extension .xlsx.
        flux = chemin.open("rb")
        try:
            classeur = load_workbook(flux, read_only=True, data_only=True)
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as erreur:
            flux.close()
            raise FichierIllisible(f"{chemin.name} : {erreur}") from erreur
        try:
            for onglet in classeur.worksheets:
                lignes = [list(r) for r in onglet.iter_rows(values_only=True)]
                if any(_simple(r[0]).startswith(tuple(LIGNES_VRS)) for r in lignes if r):
                    yield from _figure_vrs(lignes)
                    return
        finally:
            classeur.close()
            flux.close()
        raise FichierIllisible(f"{chemin.name} : figure du sentiment d'insécurité absente")


def _figure_vrs(lignes: list[list]) -> Iterator[Ligne]:
    """Les trois parts de la figure « sentiment d'insécurité » d'une fiche Insee."""
    texte = " ".join(str(c) for r in lignes for c in r if c is not None)
    annees = set(_ANNEE_VRS.findall(texte))
    if len(annees) != 1:
        raise FichierIllisible(f"Année de l'enquête VRS illisible : {sorted(annees)}")
    annee = int(annees.pop())
    colonne = None
    for r in lignes:
        entetes = [_simple(c).strip() for c in r]
        trouvees = [i for i, e in enumerate(entetes) if e in COLONNES_ENSEMBLE]
        if trouvees:
            colonne = trouvees[-1]
            break
    if colonne is None:
        raise FichierIllisible("Colonne de l'ensemble des 18 ans ou plus absente")
    vus = set()
    for r in lignes:
        libelle = _simple(r[0]) if r else ""
        indicateur = next((i for d, i in LIGNES_VRS.items() if libelle.startswith(d)), None)
        if indicateur is None:
            continue
        valeur = fichier.nombre(r[colonne] if colonne < len(r) else None)
        if valeur is None:
            raise FichierIllisible(f"{indicateur} {annee} : valeur vide")
        vus.add(indicateur)
        yield _ligne(indicateur, annee, valeur)
    if vus != INDICATEURS:
        raise FichierIllisible(f"Lignes absentes : {', '.join(sorted(INDICATEURS - vus))}")


CVS = EnqueteCVS()
VRS = FichesInsee()
