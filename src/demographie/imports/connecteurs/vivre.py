"""Appli 3 « Comment vivent les Français ? » : jeux Melodi de l'INSEE.

- Filosofi (`DS_FILOSOFI_CC`) : déciles, indices d'inégalité et décomposition du revenu
  disponible, une mesure par indicateur, 2023 seul, France métropolitaine et La Réunion.
- Base Tous salariés (`DS_BTS_SAL_EQTP_SEX_PCS`, `DS_BTS_SAL_EQTP_SEX_AGE`) : salaire net
  mensuel moyen en équivalent temps plein du secteur privé, par sexe et catégorie
  socioprofessionnelle, puis par sexe et tranche d'âge.

Même téléchargement que le recensement (API Melodi, niveau par niveau, réponses
assemblées dans un JSON archivé) ; la lecture sait en plus traduire plusieurs mesures d'un
même jeu en plusieurs indicateurs et garder le sexe.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports.connecteurs.recensement import JeuRecensement
from demographie.imports.modele import FichierIllisible, Ligne, Referentiel

_SEXES = {"_T": "T", "F": "F", "M": "H"}
# Dimensions descriptives qui ne changent pas le sens d'une valeur.
_NEUTRES = {"GEO", "TIME_PERIOD", "FREQ", "UNIT_MEASURE"}


@dataclass(frozen=True)
class JeuMesures(JeuRecensement):
    """Un jeu Melodi dont une dimension (`dimension_mesure`) donne l'indicateur.

    `dimension` (facultative) donne la modalité, `dimension_age` la tranche d'âge et la
    colonne SEX le sexe. Avec `sans_total_age`, les lignes « tous âges » sont ignorées :
    elles sont déjà lues dans un autre jeu (salaires par catégorie).
    """

    indicateur: str = ""
    filtres: dict[str, str] = field(default_factory=dict)
    dimension: str = ""
    dimension_ref: str = ""
    modalites: dict[str, str | None] = field(default_factory=dict)
    ages: dict[str, tuple[int | None, int | None]] = field(default_factory=dict)
    dimension_mesure: str = ""
    mesures: dict[str, str] = field(default_factory=dict)
    sexes: frozenset[str] = frozenset({"_T"})
    sans_total_age: bool = False
    # Indicateurs publiés en négatif par le producteur (impôts retirés du revenu), rangés
    # en positif : le pipeline refuse les valeurs négatives.
    signe_inverse: frozenset[str] = frozenset()
    requete_par_age: bool = False
    periode_type: str = "ANNEE"

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            observations = json.loads(chemin.read_text(encoding="utf-8"))["observations"]
        except (ValueError, KeyError, TypeError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        if not observations:
            raise FichierIllisible("Aucune observation")
        connues = _NEUTRES | {"SEX", self.dimension_mesure, *self.filtres}
        if self.dimension:
            connues.add(self.dimension)
        if self.ages:
            connues.add(self.dimension_age)
        lues = 0
        for obs in observations:
            dim = obs.get("dimensions") if isinstance(obs, dict) else None
            if not isinstance(dim, dict) or self.dimension_mesure not in dim:
                raise FichierIllisible(f"Observation illisible : {obs}")
            indicateur = self.mesures.get(dim[self.dimension_mesure])
            if indicateur is None:
                continue  # mesure non retenue
            if dim.get("SEX", "_T") not in self.sexes:
                continue
            if self.dimension and dim.get(self.dimension) not in self.modalites:
                continue
            if self.ages:
                age = dim.get(self.dimension_age)
                if age not in self.ages or (self.sans_total_age and age == "_T"):
                    continue
            inattendues = {
                k: v
                for k, v in dim.items()
                if (k in self.filtres and v != self.filtres[k]) or (k not in connues and v != "_T")
            }
            if inattendues:
                raise FichierIllisible(f"Dimensions inattendues : {inattendues}")
            territoire = self._territoire(dim.get("GEO", ""))
            if territoire is None:
                continue
            try:
                valeur = Decimal(str(obs["measures"]["OBS_VALUE_NIVEAU"]["value"]))
            except (KeyError, TypeError, ArithmeticError) as erreur:
                raise FichierIllisible(f"Observation illisible : {obs}") from erreur
            if indicateur in self.signe_inverse:
                valeur = -valeur
            age_min, age_max = self.ages[dim[self.dimension_age]] if self.ages else (None, None)
            modalite = self.modalites[dim[self.dimension]] if self.dimension else None
            lues += 1
            yield Ligne(
                indicateur=indicateur,
                niveau=territoire[0],
                code=territoire[1],
                periode=date(int(dim["TIME_PERIOD"]), 1, 1),
                periode_type=self.periode_type,
                sexe=_SEXES[dim.get("SEX", "_T")],
                age_min=age_min,
                age_max=age_max,
                valeur=valeur,
                statut="DEFINITIF",
                modalite=(self.dimension_ref, modalite) if modalite else None,
            )
        if not lues:
            raise FichierIllisible("Aucune mesure attendue dans le fichier")


# Filosofi ne couvre que la France métropolitaine et La Réunion (aucun total « FR »).
_FILOSOFI_ABSENTS = frozenset({"971", "972", "973", "976"})

REVENUS_FILOSOFI = JeuMesures(
    jeu="DS_FILOSOFI_CC",
    source="INSEE_FILOSOFI",
    dimension_mesure="FILOSOFI_MEASURE",
    mesures={
        "D1_SL": "NIVEAU_VIE_D1",
        "D9_SL": "NIVEAU_VIE_D9",
        "IR_D9_D1_SL": "RAPPORT_D9_D1",
        "GI_SL": "INDICE_GINI",
        "S80S20_SL": "RAPPORT_S80_S20",
        "S_EI_DI": "PART_REVENUS_ACTIVITE",
        "S_EI_DI_SAL": "PART_SALAIRES",
        "S_EI_DI_UNE": "PART_CHOMAGE",
        "S_INC_ASS_DI": "PART_REVENUS_PATRIMOINE",
        "S_SOC_BEN_DI": "PART_PRESTATIONS",
        "S_DIR_TAX_DI": "PART_IMPOTS",
        "S_SOC_BEN_DI_MIN_SOC": "PART_MINIMA_SOCIAUX",
        "S_SOC_BEN_DI_HOU_BEN": "PART_AIDES_LOGEMENT",
        "S_RET_PEN_DI": "PART_PENSIONS",
    },
    signe_inverse=frozenset({"PART_IMPOTS"}),
    controle_couverture=True,
    departements_absents=_FILOSOFI_ABSENTS,
)

_SALAIRE = {"DERA_MEASURE": "SALAIRE_NET_EQTP_MENSUEL_MOYENNE"}
_TOUS_SEXES = frozenset({"_T", "F", "M"})

SALAIRES_CATEGORIES = JeuMesures(
    jeu="DS_BTS_SAL_EQTP_SEX_PCS",
    source="INSEE_BTS",
    filtres=_SALAIRE,
    dimension_mesure="DERA_MEASURE",
    mesures={"SALAIRE_NET_EQTP_MENSUEL_MOYENNE": "SALAIRE_NET_MOYEN"},
    sexes=_TOUS_SEXES,
    dimension="PCS_ESE",
    dimension_ref="pcs",
    modalites={
        "_T": None,
        "1T3": "CADRES_DIRIGEANTS",
        "4": "PROF_INTERMEDIAIRES",
        "5": "EMPLOYES",
        "6": "OUVRIERS",
    },
    controle_couverture=True,
)

SALAIRES_AGES = JeuMesures(
    jeu="DS_BTS_SAL_EQTP_SEX_AGE",
    source="INSEE_BTS",
    filtres=_SALAIRE,
    dimension_mesure="DERA_MEASURE",
    mesures={"SALAIRE_NET_EQTP_MENSUEL_MOYENNE": "SALAIRE_NET_MOYEN"},
    sexes=_TOUS_SEXES,
    ages={
        "_T": (None, None),
        "Y_LT25": (0, 24),
        "Y25T39": (25, 39),
        "Y40T49": (40, 49),
        "Y50T54": (50, 54),
        "Y_GE55": (55, None),
    },
    sans_total_age=True,
)
