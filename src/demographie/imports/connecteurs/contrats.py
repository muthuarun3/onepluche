"""Appli « Comment travaillent les Français ? », PR T4 : « Comment » (contrats, temps partiel).

Jeu Melodi « DS_RP_TD_ACTIVITE_AGEEMPFORMD_COMP » du recensement (tableau ACT2B) : actifs
en emploi de 15 ans ou plus, par forme d'emploi (non-salariés, emploi à durée
indéterminée, autres contrats : CDD, intérim, apprentissage, stage…), temps de travail
(complet ou partiel), sexe et âge, au lieu de résidence. Téléchargé par l'API de données,
niveau par niveau, comme les autres jeux du recensement.

On ne garde que deux parts, calculées à la lecture, par sexe et par grande tranche d'âge :
- PART_CONTRATS_COURTS : autres contrats pour 100 salariés ;
- PART_TEMPS_PARTIEL : personnes à temps partiel pour 100 actifs en emploi.

Dossier de conception de l'appli travail, étapes 2 et 5 (thèmes après le MVP).
"""

import json
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports.connecteurs.recensement import JeuRecensement
from demographie.imports.modele import FichierIllisible, Ligne, Referentiel

SEXES = {"_T": "T", "F": "F", "M": "H"}
# Âges du jeu -> grande tranche ; Y_GE15 = tous âges (15 ans ou plus).
AGES = {
    "Y_GE15": (None, None),
    "Y15T19": (15, 24),
    "Y20T24": (15, 24),
    "Y25T39": (25, 54),
    "Y40T54": (25, 54),
    "Y55T64": (55, None),
    "Y_GE65": (55, None),
}
FORMES = {"1": "non_salaries", "211": "stables", "22T27": "courts", "_T": "total"}
TEMPS = {"PT": "partiel", "FT": "complet", "_T": "total"}
UN_DIXIEME = Decimal("0.1")
# Écart admis entre le total et la somme des formes d'emploi (valeurs pondérées).
TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class ContratsTempsPartiel(JeuRecensement):
    jeu: str = "DS_RP_TD_ACTIVITE_AGEEMPFORMD_COMP"
    indicateur: str = "PART_CONTRATS_COURTS"
    filtres: dict[str, str] = field(
        default_factory=lambda: {"EMPSTA_ENQ": "1", "RP_MEASURE": "POP"}
    )
    dimension: str = "EMPFORM"
    dimension_ref: str = ""
    modalites: dict[str, str | None] = field(default_factory=dict)
    ages: dict[str, tuple[int | None, int | None]] = field(default_factory=dict)
    requete_par_age: bool = False
    controle_couverture: bool = True
    # Mayotte n'est pas dans ce tableau du recensement.
    departements_absents: frozenset[str] = frozenset({"976"})

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            observations = json.loads(chemin.read_text(encoding="utf-8"))["observations"]
        except (ValueError, KeyError, TypeError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        if not observations:
            raise FichierIllisible("Aucune observation")
        # (niveau, code, année, sexe, âges) -> {(forme, temps): effectif}
        cases: dict[tuple, dict[tuple[str, str], Decimal]] = defaultdict(
            lambda: defaultdict(Decimal)
        )
        for obs in observations:
            dim = obs.get("dimensions") if isinstance(obs, dict) else None
            if not isinstance(dim, dict):
                raise FichierIllisible(f"Observation illisible : {obs}")
            try:
                cle = (dim["SEX"], dim["AGE"], dim["EMPFORM"], dim["WKTIME"])
                valeur = Decimal(str(obs["measures"]["OBS_VALUE_NIVEAU"]["value"]))
            except (KeyError, TypeError, ArithmeticError) as erreur:
                raise FichierIllisible(f"Observation illisible : {obs}") from erreur
            if (
                cle[0] not in SEXES
                or cle[1] not in AGES
                or cle[2] not in FORMES
                or cle[3] not in TEMPS
                or any(dim.get(k) != v for k, v in self.filtres.items())
            ):
                raise FichierIllisible(f"Dimensions inattendues : {dim}")
            territoire = self._territoire(dim.get("GEO", ""))
            if territoire is None:
                continue
            annee = int(dim["TIME_PERIOD"])
            groupe = (*territoire, annee, SEXES[cle[0]], AGES[cle[1]])
            cases[groupe][(FORMES[cle[2]], TEMPS[cle[3]])] += valeur
        for (niveau, code, annee, sexe, (age_min, age_max)), v in sorted(
            cases.items(), key=lambda x: (x[0][:4], x[0][4][0] or 0)
        ):
            total = v[("total", "total")]
            formes = v[("non_salaries", "total")] + v[("stables", "total")] + v[("courts", "total")]
            if total and abs(formes - total) > TOLERANCE * total:
                raise FichierIllisible(
                    f"{niveau} {code} {annee} : formes d'emploi {formes} pour un total de {total}"
                )
            salaries = v[("stables", "total")] + v[("courts", "total")]
            parts = {
                "PART_CONTRATS_COURTS": (v[("courts", "total")], salaries),
                "PART_TEMPS_PARTIEL": (v[("total", "partiel")], total),
            }
            for indicateur, (numerateur, denominateur) in parts.items():
                if denominateur:
                    part = (100 * numerateur / denominateur).quantize(UN_DIXIEME)
                    yield Ligne(indicateur, niveau, code, date(annee, 1, 1), self.periode_type,
                                sexe, age_min, age_max, part, "DEFINITIF")  # fmt: skip


CONTRATS = ContratsTempsPartiel()
