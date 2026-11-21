"""Parc locatif social (RPLS, SDES) : logements des bailleurs sociaux au 1er janvier.

Les données détaillées sont publiées logement par logement (5,4 millions de lignes) sur
l'API DIDO du SDES. On ne demande que la colonne du département, pour chaque millésime,
et on compte les logements. Le fichier ouvert ne donne ni les loyers ni la vacance.
"""

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.connecteurs import fichier
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

DATAFILE = (
    "https://data.statistiques.developpement-durable.gouv.fr/dido/api/v1/datafiles/"
    "f3c2f2cb-8fb1-40fd-8733-964247744c9a"
)
PREMIER_MILLESIME = 2022  # millésimes servis par l'API (les plus anciens : fichiers à part)
FORMAT = fichier.FormatCSV(encodage="utf-8-sig", separateur=";", decimale=".")
DROM = frozenset({"971", "972", "973", "974", "976"})
_NOM = re.compile(r"^rpls-(\d{4})\.csv$")


@dataclass(frozen=True)
class ParcSocial:
    source: str = "SDES_RPLS"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True
    lit_le_nom: bool = True  # le millésime n'est que dans le nom du fichier

    def fichiers(self) -> list[Fichier]:
        meta = telechargement.lire_json(DATAFILE)
        dernier = meta.get("millesime", "") if isinstance(meta, dict) else ""
        if not re.match(r"^\d{4}-01$", dernier):
            raise FichierIllisible(f"Millésime RPLS inattendu : {dernier!r}")
        return [
            Fichier(
                url=f"{DATAFILE}/csv?millesime={a}-01&withColumnName=true"
                "&withColumnDescription=false&columns=DEP_CODE",
                nom=f"rpls-{a}.csv",
                millesime=str(a),
            )
            for a in range(PREMIER_MILLESIME, int(dernier[:4]) + 1)
        ]

    def accepte(self, nom_fichier: str) -> bool:
        return _NOM.match(nom_fichier) is not None

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        trouve = _NOM.match(chemin.name)
        if trouve is None:
            raise FichierIllisible(f"Nom de fichier inattendu : {chemin.name}")
        annee = int(trouve.group(1))
        par_departement = Counter(
            ligne["DEP_CODE"] for ligne in fichier.lire_csv(chemin, FORMAT, frozenset({"DEP_CODE"}))
        )
        sans_departement = par_departement.pop("", 0)
        total = sum(par_departement.values())
        if total == 0:
            raise FichierIllisible("Aucun logement lu")
        if sans_departement > 0.001 * total:
            raise FichierIllisible(f"{sans_departement} logements sans département")
        comptes: Counter[tuple[str, str]] = Counter()
        for departement, nombre in par_departement.items():
            comptes[("DEP", departement)] += nombre
            comptes[("FRANCE", "FR")] += nombre
            if departement not in DROM:
                comptes[("FRANCE", "FM")] += nombre
            region = referentiel.region_du_departement.get(departement)
            if region:
                comptes[("REG", region)] += nombre
        for (niveau, code), nombre in sorted(comptes.items()):
            yield Ligne(
                indicateur="LOGEMENTS_SOCIAUX",
                niveau=niveau,
                code=code,
                periode=date(annee, 1, 1),
                periode_type="1ER_JANVIER",
                sexe="T",
                age_min=None,
                age_max=None,
                valeur=nombre,
                statut="DEFINITIF",
            )


PARC_SOCIAL = ParcSocial()
