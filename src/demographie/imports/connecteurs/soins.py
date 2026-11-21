"""Accès aux soins (dossier de conception de l'appli 2, étape 6, thème « soins »).

Trois sources, sans compte et sous Licence Ouverte :

- DREES, accessibilité potentielle localisée (APL) aux médecins généralistes : un classeur
  avec une feuille par année et une ligne par commune. L'APL est le nombre de consultations
  de médecine générale accessibles par habitant et par an, compte tenu de l'offre des
  communes voisines et de l'âge des habitants. Comme la DREES dans ses publications, on
  retient les médecins de 65 ans ou moins (ceux qui ne partiront pas bientôt à la
  retraite). La DREES le ramène à un territoire plus
  large en pondérant par la population standardisée, fournie dans la même feuille ; la
  part des habitants sous 2,5 consultations (seuil des zones sous-denses) est comptée en
  population totale. France hors Mayotte.
- Assurance maladie, observatoire de l'accès aux soins : part des patients en affection
  longue durée (ALD) sans médecin traitant, par département et région, chaque année.
- INSEE, base permanente des équipements (BPE), jeu Melodi DS_BPE : médecins
  généralistes, pharmacies, services d'urgences et maisons de santé de chaque territoire.
  La BPE compte les lieux d'exercice : un médecin qui consulte à deux adresses compte deux
  fois.
"""

import csv
import re
import urllib.parse
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from openpyxl import load_workbook

from demographie.imports.connecteurs.communes import DROM, departement_de, moyenne_ponderee
from demographie.imports.connecteurs.recensement import JeuRecensement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

DREES = "https://data.drees.solidarites-sante.gouv.fr/api/explore/v2.1/catalog/datasets"
AMELI = "https://data.ameli.fr/api/explore/v2.1/catalog/datasets"

# Seuil des zones sous-denses en médecins généralistes retenu par la DREES.
SEUIL_APL_FAIBLE = Decimal("2.5")
_FEUILLE_APL = re.compile(r"APL (\d{4})")
_DEPARTEMENT = re.compile(r"\d\d|2[AB]|97[1-6]")


@dataclass(frozen=True)
class AccessibiliteMedecins:
    source: str = "DREES_APL"
    jeu: str = "530_l-accessibilite-potentielle-localisee-apl"
    piece_jointe: str = "indicateur_d_apl_aux_medecins_generalistes_xlsx"
    nom_fichier: str = "apl-medecins-generalistes.xlsx"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    communes_min: int = 30_000
    controle_couverture: bool = True
    departements_absents: frozenset[str] = frozenset({"976"})

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        url = f"{DREES}/{self.jeu}/attachments/{self.piece_jointe}"
        return [Fichier(url=url, nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            classeur = load_workbook(chemin, read_only=True, data_only=True)
        except Exception as erreur:  # zip invalide, XML interne mal formé…
            raise FichierIllisible(f"Classeur illisible : {erreur}") from erreur
        try:
            annees = {
                int(m[1]): nom for nom in classeur.sheetnames if (m := _FEUILLE_APL.fullmatch(nom))
            }
            if not annees:
                raise FichierIllisible("Aucune feuille « APL <année> » dans le classeur")
            for annee, nom in sorted(annees.items()):
                yield from self._lire_feuille(classeur[nom], annee, referentiel)
        finally:
            classeur.close()

    def _lire_feuille(self, feuille, annee: int, referentiel: Referentiel) -> Iterator[Ligne]:
        rangs = feuille.iter_rows(values_only=True)
        colonnes = None
        for rang in rangs:
            if rang and rang[0] == "Code commune INSEE":
                colonnes = self._colonnes(rang, annee)
                break
        if colonnes is None:
            raise FichierIllisible(f"APL {annee} : ligne d'en-tête introuvable")
        apl, standardisee, totale = {}, {}, {}
        for rang in rangs:
            commune = rang[0] if rang else None
            if commune is None or str(commune).strip() == "":
                continue
            commune = str(commune).strip()
            if not re.fullmatch(r"[0-9][0-9AB][0-9]{3}", commune):
                continue  # ligne de sous-titre (unités) ou note
            try:
                valeurs = [rang[i] for i in colonnes]
                if any(v is None for v in valeurs):
                    continue  # commune sans APL calculé
                a, s, t = (Decimal(str(v)) for v in valeurs)
            except (IndexError, InvalidOperation) as erreur:
                raise FichierIllisible(f"APL {annee} : ligne illisible {rang[:8]}") from erreur
            if a < 0 or s < 0 or t < 0:
                raise FichierIllisible(f"APL {annee} : valeur négative pour {commune}")
            apl[commune], standardisee[commune], totale[commune] = a, s, t
        if len(apl) < self.communes_min:
            raise FichierIllisible(f"APL {annee} : {len(apl)} communes seulement")

        def region(commune: str) -> str | None:
            return referentiel.region_du_departement.get(departement_de(commune))

        def metropole(commune: str) -> str | None:
            return None if departement_de(commune) in DROM else "FM"

        regroupements = (
            ("DEP", departement_de),
            ("REG", region),
            ("FRANCE", lambda _c: "FR"),
            ("FRANCE", metropole),
        )
        for niveau, groupe in regroupements:
            moyennes = moyenne_ponderee(apl.items(), standardisee, groupe)
            faibles = _part_sous_seuil(apl, totale, groupe)
            for code in sorted(moyennes):
                yield self._ligne("APL_MG", niveau, code, annee, round(moyennes[code].valeur, 2))
                if code in faibles:
                    yield self._ligne("PART_POP_APL_MG_FAIBLE", niveau, code, annee, faibles[code])

    @staticmethod
    def _colonnes(entete: tuple, annee: int) -> tuple[int, int, int]:
        noms = [str(c).strip() if c is not None else "" for c in entete]

        def index(predicat, libelle: str) -> int:
            trouves = [i for i, n in enumerate(noms) if predicat(n)]
            if len(trouves) != 1:
                raise FichierIllisible(f"APL {annee} : colonne « {libelle} » introuvable")
            return trouves[0]

        return (
            # « de 65 ans et moins » (2022, 2023) puis « de 65 ans ou moins » (2024).
            index(lambda n: n.startswith("APL aux médecins généralistes de 65 ans"), "APL"),
            index(lambda n: n.startswith("Population standardisée"), "population standardisée"),
            index(lambda n: n.startswith("Population totale"), "population totale"),
        )

    def _ligne(self, indicateur: str, niveau: str, code: str, annee: int, valeur) -> Ligne:
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
            statut="DEFINITIF",
        )


def _part_sous_seuil(apl: dict, population: dict, groupe) -> dict[str, Decimal]:
    """Part (en %) des habitants de chaque groupe vivant dans une commune sous le seuil."""
    sous_seuil: dict[str, Decimal] = defaultdict(Decimal)
    total: dict[str, Decimal] = defaultdict(Decimal)
    for commune, valeur in apl.items():
        code = groupe(commune)
        if code is None:
            continue
        total[code] += population[commune]
        if valeur < SEUIL_APL_FAIBLE:
            sous_seuil[code] += population[commune]
    return {code: round(100 * sous_seuil[code] / t, 1) for code, t in total.items() if t > 0}


@dataclass(frozen=True)
class AldSansMedecinTraitant:
    source: str = "CNAM_ACCES"
    jeu: str = "patients-longueduree-annuelle"
    nom_fichier: str = "ameli-ald-sans-medecin-traitant.csv"
    indicateur: str = "ALD_SANS_MT"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        parametres = {
            "select": "annee,region,departement,taux_patients_ald_sans_mt",
            "order_by": "annee,region,departement",
            "delimiter": ";",
        }
        requete = urllib.parse.urlencode(parametres, quote_via=urllib.parse.quote)
        return [Fichier(url=f"{AMELI}/{self.jeu}/exports/csv?{requete}", nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        colonnes = {"annee", "region", "departement", "taux_patients_ald_sans_mt"}
        vues = 0
        with chemin.open(encoding="utf-8-sig", newline="") as f:
            lecteur = csv.DictReader(f, delimiter=";")
            manquantes = colonnes - set(lecteur.fieldnames or ())
            if manquantes:
                raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
            for rang in lecteur:
                territoire = _territoire_ameli(rang["region"], rang["departement"])
                taux = rang["taux_patients_ald_sans_mt"].strip()
                if territoire is None or taux in ("", "NC"):
                    continue  # résidence inconnue, taux non calculable
                if not re.fullmatch(r"\d{4}", rang["annee"]):
                    raise FichierIllisible(f"Année inattendue : {rang['annee']!r}")
                try:
                    part = Decimal(taux)
                except InvalidOperation as erreur:
                    raise FichierIllisible(f"Taux illisible : {taux!r}") from erreur
                if not 0 <= part <= 1:
                    raise FichierIllisible(f"Taux hors de [0, 1] : {taux!r}")
                vues += 1
                yield Ligne(
                    indicateur=self.indicateur,
                    niveau=territoire[0],
                    code=territoire[1],
                    periode=date(int(rang["annee"]), 1, 1),
                    periode_type="ANNEE",
                    sexe="T",
                    age_min=None,
                    age_max=None,
                    valeur=round(100 * part, 1),
                    statut="DEFINITIF",
                )
        if not vues:
            raise FichierIllisible("Aucun taux de patients en ALD sans médecin traitant")


def _territoire_ameli(region: str, departement: str) -> tuple[str, str] | None:
    """(« 99 », « 999 ») -> France ; (« 11 », « 999 ») -> région ; sinon département."""
    if departement == "999":
        if region == "99":
            return ("FRANCE", "FR")
        if re.fullmatch(r"\d\d", region):
            return ("REG", region)
        raise FichierIllisible(f"Région inattendue : {region!r}")
    if _DEPARTEMENT.fullmatch(departement):
        return ("DEP", departement)
    return None  # « inconnu » : résidence non renseignée


def _equipements(suffixe: str, indicateur: str, sous_domaine: str, type_: str) -> JeuRecensement:
    """Un type d'équipement de santé de la BPE : un indicateur, un fichier brut."""
    return JeuRecensement(
        jeu="DS_BPE",
        suffixe=suffixe,
        source="INSEE_BPE",
        indicateur=indicateur,
        filtres={
            "BPE_MEASURE": "FACILITIES",
            "UNIT_MEASURE": "NR",
            "FACILITY_DOM": "D",
            "FACILITY_SDOM": sous_domaine,
            "FACILITY_TYPE": type_,
        },
        dimension="FACILITY_TYPE",
        dimension_ref="equipement",
        modalites={type_: None},
        ages={},
        requete_par_age=False,
        periode_type="ANNEE",
        controle_couverture=True,
    )


APL_MEDECINS = AccessibiliteMedecins()
ALD_SANS_MEDECIN_TRAITANT = AldSansMedecinTraitant()
MEDECINS_GENERALISTES = _equipements("_medecins", "LIEUX_MG", "D2", "D265")
PHARMACIES = _equipements("_pharmacies", "PHARMACIES", "D3", "D307")
URGENCES = _equipements("_urgences", "URGENCES", "D1", "D106")
MAISONS_DE_SANTE = _equipements("_maisons_sante", "MAISONS_SANTE", "D1", "D113")
