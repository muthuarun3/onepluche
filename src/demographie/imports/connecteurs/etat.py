"""Budget de l'État (ministère de l'Économie, data.economie.gouv.fr).

- Situation mensuelle budgétaire : solde, dépenses et recettes nettes du budget général,
  cumulés depuis janvier, fin de chaque mois depuis janvier 2024 (une ligne par poste,
  une colonne par mois, en euros). Export JSON du jeu Opendatasoft.
- Crédits par mission : crédits de paiement votés en loi de finances initiale et dépenses
  constatées, par mission, programme et titre (annexe 1, état CP, du projet de loi relatif
  aux résultats de la gestion, PLRG). Un jeu par année, au nom irrégulier : on le trouve par
  le catalogue, au titre de sa pièce jointe « Annexe1-Etat_CP-AAAA.csv ».
"""

import csv
import json
import re
import unicodedata
import urllib.parse
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

API = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets"
JEU_MENSUEL = "situations-mensuelles-budgetaires-series-longues"
MILLIARD = Decimal(1_000_000_000)
# Première année des crédits par mission (dossier de conception, étape 2).
PREMIERE_ANNEE_MISSIONS = 2023


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join(sans_accents.lower().replace("’", "'").split())


def _ligne(indicateur: str, periode: date, type_periode: str, valeur: Decimal, statut: str,
           modalite: tuple[str, str] | None = None) -> Ligne:  # fmt: skip
    return Ligne(indicateur, "FRANCE", "FR", periode, type_periode, "T", None, None,
                 valeur, statut, modalite)  # fmt: skip


# --- Situation mensuelle budgétaire -----------------------------------------------------

# Libellé de la ligne (normalisé) -> (indicateur, modalité).
LIGNES_MENSUELLES = {
    "solde budgetaire": ("SOLDE_ETAT", None),
    "total depenses nettes du budget general": ("DEPENSES_ETAT", None),
    "total recettes nettes du budget general": ("RECETTES_ETAT", None),
    "total recettes fiscales": ("RECETTES_FISCALES_ETAT", None),
    "impot sur le revenu": ("RECETTES_FISCALES_ETAT", ("impot_etat", "IR")),
    "impot sur les societes": ("RECETTES_FISCALES_ETAT", ("impot_etat", "IS")),
    "taxe interieure de consommation sur les produits energetiques": (
        "RECETTES_FISCALES_ETAT",
        ("impot_etat", "TICPE"),
    ),
    "taxe sur la valeur ajoutee": ("RECETTES_FISCALES_ETAT", ("impot_etat", "TVA")),
    "autres recettes fiscales": ("RECETTES_FISCALES_ETAT", ("impot_etat", "AUTRES")),
}
_COLONNE_MOIS = re.compile(r"^(\d{2})_(\d{2})_(\d{4})$")


@dataclass(frozen=True)
class SituationMensuelle:
    source: str = "SITUATION_MENSUELLE_ETAT"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})
    nom_fichier: str = "situation-mensuelle-budgetaire.json"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=f"{API}/{JEU_MENSUEL}/exports/json", nom=self.nom_fichier)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            lignes = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        if not isinstance(lignes, list):
            raise FichierIllisible("Liste de lignes attendue")
        vues: dict[tuple, dict[date, Decimal]] = {}
        for ligne in lignes:
            cle = LIGNES_MENSUELLES.get(_normaliser(str(ligne.get("ligne_d_information", ""))))
            if cle is None:
                continue
            if cle in vues:
                raise FichierIllisible(f"Ligne en double : {ligne['ligne_d_information']}")
            valeurs = {}
            for colonne, valeur in ligne.items():
                mois = _COLONNE_MOIS.match(colonne)
                if not mois or valeur is None:
                    continue
                try:
                    montant = Decimal(str(valeur)) / MILLIARD
                except InvalidOperation as erreur:
                    raise FichierIllisible(f"Montant illisible : {colonne}={valeur}") from erreur
                # La colonne porte le jour de l'arrêté (fin de mois, parfois avant) : on
                # range la valeur au premier du mois.
                valeurs[date(int(mois[3]), int(mois[2]), 1)] = round(montant, 6)
            vues[cle] = valeurs
        absentes = sorted({c[0] + (f" {c[1][1]}" if c[1] else "") for c in
                           set(LIGNES_MENSUELLES.values()) - set(vues)})  # fmt: skip
        if absentes:
            raise FichierIllisible(f"Lignes absentes : {', '.join(absentes)}")
        derniere = max(m for valeurs in vues.values() for m in valeurs)
        for (indicateur, modalite), valeurs in sorted(vues.items(), key=lambda kv: str(kv[0])):
            for mois, valeur in sorted(valeurs.items()):
                statut = "PROVISOIRE" if mois.year == derniere.year else "DEFINITIF"
                yield _ligne(indicateur, mois, "MOIS", valeur, statut, modalite)


# --- Crédits par mission (PLRG, annexe 1, état CP) --------------------------------------

_PIECE_CP = re.compile(r"^Annexe1-Etat_CP-(\d{4})\.csv$", re.I)
# Missions renommées : ancien libellé (normalisé) -> code.
RENOMMEES = {
    "travail et emploi": "TRAVAIL_EMPLOI",
    "travail, emploi et administration des ministeres sociaux": "TRAVAIL_EMPLOI",
}


def code_mission(libelle: str) -> str:
    """« Écologie, développement et mobilité durables » -> « ECOLOGIE_DEVELOPPEMENT_… »."""
    normal = _normaliser(libelle)
    if normal in RENOMMEES:
        return RENOMMEES[normal]
    return re.sub(r"[^A-Z0-9]+", "_", normal.upper()).strip("_")


def _montant(texte: str) -> Decimal:
    try:
        return Decimal((texte or "0").replace(" ", "").replace(" ", "").replace(",", "."))
    except InvalidOperation as erreur:
        raise FichierIllisible(f"Montant illisible : {texte!r}") from erreur


@dataclass(frozen=True)
class CreditsMissions:
    source: str = "PLRG_ETAT"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE"})
    lit_le_nom: bool = True  # l'année vient du nom du fichier

    def accepte(self, nom_fichier: str) -> bool:
        return re.fullmatch(r"plrg-credits-\d{4}\.csv", nom_fichier) is not None

    def fichiers(self) -> list[Fichier]:
        requete = urllib.parse.urlencode(
            {"where": 'search("plrg")', "limit": 50, "select": "dataset_id,attachments"}
        )
        reponse = json.loads(telechargement.lire_page(f"{API}?{requete}"))
        trouves: dict[int, Fichier] = {}
        for jeu in reponse.get("results", []):
            for piece in jeu.get("attachments") or []:
                titre = _PIECE_CP.match(str(piece.get("title", "")).strip())
                if titre and int(titre[1]) >= PREMIERE_ANNEE_MISSIONS:
                    annee = int(titre[1])
                    trouves[annee] = Fichier(
                        url=piece["url"], nom=f"plrg-credits-{annee}.csv", millesime=str(annee)
                    )
        if not trouves:
            raise FichierIllisible("Aucune annexe « Etat_CP » trouvée dans le catalogue")
        return [trouves[a] for a in sorted(trouves)]

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        annee = re.search(r"(\d{4})", chemin.name)
        if not annee:
            raise FichierIllisible(f"Année absente du nom : {chemin.name}")
        periode = date(int(annee[1]), 1, 1)
        try:
            with chemin.open(encoding="utf-8-sig", newline="") as f:
                lignes = list(csv.DictReader(f, delimiter=";"))
        except (OSError, UnicodeDecodeError, csv.Error) as erreur:
            raise FichierIllisible(f"CSV illisible : {erreur}") from erreur
        attendues = {"Mission", "LFI", "Depenses_constatees"}
        if not lignes or not attendues <= set(lignes[0]):
            colonnes = sorted(attendues - set(lignes[0] if lignes else {}))
            raise FichierIllisible(f"Colonnes absentes : {', '.join(colonnes)}")
        votes: dict[str, Decimal] = defaultdict(Decimal)
        consommes: dict[str, Decimal] = defaultdict(Decimal)
        for ligne in lignes:
            mission = code_mission(ligne["Mission"])
            votes[mission] += _montant(ligne["LFI"])
            consommes[mission] += _montant(ligne["Depenses_constatees"])
        for indicateur, montants in (("CREDITS_VOTES", votes), ("CREDITS_CONSOMMES", consommes)):
            total = sum(montants.values(), Decimal(0))
            yield _ligne(indicateur, periode, "ANNEE", round(total / MILLIARD, 6), "DEFINITIF")
            for mission, montant in sorted(montants.items()):
                yield _ligne(indicateur, periode, "ANNEE", round(montant / MILLIARD, 6),
                             "DEFINITIF", ("mission_etat", mission))  # fmt: skip


SITUATION_MENSUELLE = SituationMensuelle()
CREDITS_MISSIONS = CreditsMissions()
