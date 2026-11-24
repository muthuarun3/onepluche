"""Données de la DREES, portail data.drees (Opendatasoft, sans compte, Licence Ouverte).

Deux jeux :

- Enquête annuelle auprès des caisses de retraite (EACR), feuille « A-Cadrage » : nombre de
  retraités tous régimes résidant en France, au 31 décembre, de 2004 à l'avant-dernière
  année. National seulement : la DREES ne publie les retraités par lieu de résidence que
  tous les 4 ans (échantillon interrégimes), et par région. Le classeur change de nom à
  chaque édition : on le retrouve dans la liste des pièces jointes du jeu. La même feuille
  donne la pension moyenne de droit direct (colonne « m1 », euros bruts par mois), lue pour
  l'appli « Comment vivent les Français ? ».
- Panorama statistique « Cohésion sociale » : allocataires du minimum vieillesse (ASV et
  ASPA) par département, depuis 1996, exporté en CSV.
"""

import csv
import re
from collections.abc import Iterator
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from demographie.imports import telechargement
from demographie.imports.modele import (
    REGIONS_OUTRE_MER,
    Fichier,
    FichierIllisible,
    Ligne,
    Referentiel,
)

API = "https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets"

_SEXES = {"Ensemble": "T", "Femmes": "F", "Hommes": "H"}
# Champ de l'EACR -> indicateur : tous les retraités, ou ceux ayant un droit propre.
_CHAMPS = {"dtot": "PENSIONNES", "ddir": "PENSIONNES_DROIT_DIRECT"}
_COLONNES_EACR = ("Année", "CC", "Sexe", "Resid", "Champ", "Liq", "StatutSNCF", "PlusRécent")
# Effectifs ; montant mensuel moyen brut de la pension de droit direct (« m1 »).
_VALEURS = ("effectifs", "m1")


class RetraitesEacr:
    source = "DREES_PENS"
    jeu = "donnes_eacr"  # sic, identifiant du jeu sur data.drees
    feuille = "A-Cadrage"
    niveaux_publies = frozenset({"FRANCE"})
    motif = re.compile(r"\d+_eacr_diffusee_part_1_version_du_(\w+?)\.xlsx")

    def accepte(self, nom_fichier: str) -> bool:
        return self.motif.fullmatch(nom_fichier) is not None

    def fichiers(self) -> list[Fichier]:
        reponse = telechargement.lire_json(f"{API}/{self.jeu}/attachments")
        liens = [
            a.get("href", "")
            for a in (reponse.get("attachments", []) if isinstance(reponse, dict) else [])
        ]
        trouves = []
        for lien in liens:
            nom = lien.rsplit("/", 1)[-1]
            if nom.endswith("_xlsx"):
                nom = nom[: -len("_xlsx")] + ".xlsx"
            if lien.startswith(f"{API}/{self.jeu}/attachments/") and self.accepte(nom):
                trouves.append(Fichier(url=lien, nom=nom, millesime=self.motif.fullmatch(nom)[1]))
        if len(trouves) != 1:
            raise FichierIllisible(f"{len(trouves)} classeur(s) EACR « part 1 » publié(s)")
        return trouves

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            classeur = load_workbook(chemin, read_only=True, data_only=True)
        except Exception as erreur:  # zip invalide, XML interne mal formé…
            raise FichierIllisible(f"Classeur illisible : {erreur}") from erreur
        try:
            if self.feuille not in classeur.sheetnames:
                raise FichierIllisible(f"Feuille {self.feuille} absente")
            feuille = classeur[self.feuille]
            feuille.reset_dimensions()  # dimensions absentes du fichier publié
            rangs = feuille.iter_rows(values_only=True)
            entete = [str(c) if c is not None else "" for c in next(rangs, ())]
            manquantes = [c for c in (*_COLONNES_EACR, *_VALEURS) if c not in entete]
            if manquantes:
                raise FichierIllisible(f"Colonnes absentes : {', '.join(manquantes)}")
            col = {nom: entete.index(nom) for nom in (*_COLONNES_EACR, *_VALEURS)}
            lues = 0
            for rang in rangs:
                for ligne in self._lignes(rang, col):
                    lues += 1
                    yield ligne
            if lues == 0:
                raise FichierIllisible("Aucun effectif tous régimes dans le classeur")
        finally:
            classeur.close()

    @staticmethod
    def _lignes(rang: tuple, col: dict[str, int]) -> list[Ligne]:
        def v(nom):
            return rang[col[nom]] if col[nom] < len(rang) else None

        if (
            v("CC") != "0000"  # tous régimes, retraités comptés une seule fois
            or v("Resid") != "France"
            or v("Champ") not in _CHAMPS
            or v("Sexe") not in _SEXES
            or v("Liq") != "Ensemble"
            or v("StatutSNCF") != "Ensemble"
            or v("PlusRécent") is not True
        ):
            return []
        valeurs = {_CHAMPS[v("Champ")]: v("effectifs")}
        if v("Champ") == "ddir":
            valeurs["PENSION_MOYENNE"] = v("m1")
        try:
            annee = int(v("Année"))
            valeurs = {k: Decimal(str(x)) for k, x in valeurs.items()}
        except (TypeError, ValueError, InvalidOperation) as erreur:
            raise FichierIllisible(f"Ligne illisible : {rang[:12]}") from erreur
        return [
            Ligne(
                indicateur=indicateur,
                niveau="FRANCE",
                code="FR",
                periode=date(annee, 1, 1),
                periode_type="ANNEE",
                sexe=_SEXES[v("Sexe")],
                age_min=None,
                age_max=None,
                valeur=valeur,
                statut="DEFINITIF",
            )
            for indicateur, valeur in valeurs.items()
        ]


class MinimumVieillesse:
    source = "DREES_ASPA"
    jeu = "panorama-statistique-toutes-thematiques"
    niveaux_publies = frozenset({"FRANCE", "REG", "DEP"})
    nom_fichier = "panorama-minimum-vieillesse.csv"
    # Identifiant DREES -> (indicateur, facteur) ; le taux est publié en proportion.
    indicateurs = {
        "ms_nb_alloc_asv_aspa": ("MIN_VIEILLESSE", 1),
        "ms_tx_alloc_asv_aspa_60p": ("TAUX_MIN_VIEILLESSE_60P", 100),
    }
    # Totaux nationaux : France entière (avec Mayotte) et France métropolitaine.
    _france = {"FE": "FR", "M": "FM"}

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        ids = ",".join(f'"{i}"' for i in sorted(self.indicateurs))
        requete = f"where=id_indicateur in ({ids})&delimiter=;&order_by=id_indicateur,annee"
        url = f"{API}/{self.jeu}/exports/csv?" + requete.replace(" ", "%20").replace('"', "%22")
        return [Fichier(url=url, nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        with chemin.open(encoding="utf-8-sig", newline="") as f:
            lecteur = csv.DictReader(f, delimiter=";")
            attendues = {"annee", "code_reg", "code_dep", "value", "id_indicateur"}
            manquantes = attendues - set(lecteur.fieldnames or ())
            if manquantes:
                raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
            lues = 0
            for rang in lecteur:
                if rang["id_indicateur"] not in self.indicateurs or rang["value"] in ("", "NA"):
                    continue
                territoires = self._territoires(rang["code_reg"], rang["code_dep"], referentiel)
                if not territoires:
                    continue
                indicateur, facteur = self.indicateurs[rang["id_indicateur"]]
                if not re.fullmatch(r"\d{4}", rang["annee"]):
                    raise FichierIllisible(f"Année inattendue : {rang['annee']!r}")
                try:
                    valeur = Decimal(rang["value"]) * facteur
                except InvalidOperation as erreur:
                    raise FichierIllisible(f"Valeur illisible : {rang['value']!r}") from erreur
                for niveau, code in territoires:
                    lues += 1
                    yield Ligne(
                        indicateur=indicateur,
                        niveau=niveau,
                        code=code,
                        periode=date(int(rang["annee"]), 1, 1),
                        periode_type="ANNEE",
                        sexe="T",
                        age_min=None,
                        age_max=None,
                        valeur=valeur,
                        statut="DEFINITIF",
                    )
            if lues == 0:
                raise FichierIllisible("Aucune valeur du minimum vieillesse")

    def _territoires(
        self, region: str, departement: str, referentiel: Referentiel
    ) -> list[tuple[str, str]]:
        if region in self._france:
            return [("FRANCE", self._france[region])]
        if departement == "1000":  # total régional
            # Outre-mer : déjà repris de l'unique département, ci-dessous.
            return [] if region in REGIONS_OUTRE_MER else [("REG", region)]
        if re.fullmatch(r"\d{2}|2[AB]|97[1-6]", departement):
            mono = referentiel.region_mono_departementale(departement)
            return [("DEP", departement)] + ([("REG", mono)] if mono else [])
        # « 20R » (Collectivité de Corse = région 94), Rhône et Lyon séparés, Alsace,
        # Saint-Pierre-et-Miquelon, « France entière hors Mayotte » : non retenus.
        return []


EACR = RetraitesEacr()
MINIMUM_VIEILLESSE = MinimumVieillesse()
