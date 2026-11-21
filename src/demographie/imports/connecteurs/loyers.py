"""Carte des loyers (ANIL) : loyers d'annonce par commune, publiés sur data.gouv.fr.

Un jeu par édition (« … par commune en 2025 »), trouvé par la recherche de data.gouv.fr ;
seule la plus récente est importée. Quatre fichiers CSV : appartements (toutes tailles,
1-2 pièces, 3 pièces et plus) et maisons. Le loyer communal est ramené au département,
à la région et à la France en moyenne pondérée par les résidences principales louées de
chaque commune (poids « RP_LOUEES » du recensement, importés avant).
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.connecteurs import communes, fichier
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

RECHERCHE = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "?q=carte+des+loyers+indicateurs+de+loyers+d%27annonce+par+commune&page_size=50"
)
_JEU = re.compile(r"^carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-(\d{4})$")
# Fichier de l'ANIL -> (indicateur, modalité de taille ou None).
FICHIERS = {
    "pred-app-mef-dhup.csv": ("LOYER_APPARTEMENT_M2", None),
    "pred-app12-mef-dhup.csv": ("LOYER_APPARTEMENT_M2", "T1_T2"),
    "pred-app3-mef-dhup.csv": ("LOYER_APPARTEMENT_M2", "T3_PLUS"),
    "pred-mai-mef-dhup.csv": ("LOYER_MAISON_M2", None),
}
_NOM = re.compile(r"^carte-loyers-(\d{4})-(" + "|".join(map(re.escape, FICHIERS)) + r")$")
FORMAT = fichier.FormatCSV(encodage="latin-1")
COLONNES = frozenset({"INSEE_C", "DEP", "loypredm2"})
# Part maximale de communes sans poids (communes créées depuis le recensement…).
PART_SANS_POIDS_MAX = 0.02
DROM = frozenset({"971", "972", "973", "974", "976"})


@dataclass(frozen=True)
class CarteDesLoyers:
    source: str = "ANIL_LOYERS"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True
    departements_absents: frozenset[str] = frozenset({"976"})  # hors champ de l'ANIL
    dimension_poids: str = "RP_LOUEES"
    lit_le_nom: bool = True  # l'année et le type de logement ne sont que dans le nom

    def fichiers(self) -> list[Fichier]:
        reponse = telechargement.lire_json(RECHERCHE)
        editions = {}
        for jeu in reponse.get("data", []) if isinstance(reponse, dict) else []:
            trouve = _JEU.match(jeu.get("slug", ""))
            if trouve:
                editions[int(trouve.group(1))] = jeu
        if not editions:
            raise FichierIllisible("Aucune édition de la Carte des loyers trouvée")
        annee = max(editions)
        retenus = []
        for ressource in editions[annee].get("resources", []):
            nom = Path(ressource.get("url", "")).name
            if nom in FICHIERS:
                retenus.append(
                    Fichier(
                        url=ressource["url"],
                        nom=f"carte-loyers-{annee}-{nom}",
                        millesime=str(annee),
                    )  # fmt: skip
                )
        if len(retenus) != len(FICHIERS):
            raise FichierIllisible(f"Carte des loyers {annee} : fichiers attendus absents")
        return sorted(retenus, key=lambda f: f.nom)

    def accepte(self, nom_fichier: str) -> bool:
        return _NOM.match(nom_fichier) is not None

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        trouve = _NOM.match(chemin.name)
        if trouve is None:
            raise FichierIllisible(f"Nom de fichier inattendu : {chemin.name}")
        annee = int(trouve.group(1))
        indicateur, taille = FICHIERS[trouve.group(2)]
        valeurs = []
        for ligne in fichier.lire_csv(chemin, FORMAT, COLONNES):
            loyer = fichier.nombre(ligne["loypredm2"])
            if loyer is not None:
                valeurs.append((ligne["INSEE_C"].zfill(5), loyer))
        if not valeurs:
            raise FichierIllisible("Aucun loyer lu")
        poids = referentiel.poids(self.dimension_poids, annee)
        par_departement = communes.moyenne_ponderee(valeurs, poids)
        sans_poids = sum(a.sans_poids for a in par_departement.values())
        if sans_poids > PART_SANS_POIDS_MAX * len(valeurs):
            raise FichierIllisible(f"{sans_poids} communes sans poids sur {len(valeurs)}")

        def region(commune: str) -> str | None:
            return referentiel.region_du_departement.get(communes.departement_de(commune))

        def metropole(commune: str) -> str | None:
            return None if communes.departement_de(commune) in DROM else "FM"

        niveaux = (
            ("DEP", par_departement),
            ("REG", communes.moyenne_ponderee(valeurs, poids, region)),
            ("FRANCE", communes.moyenne_ponderee(valeurs, poids, lambda _c: "FR")),
            ("FRANCE", communes.moyenne_ponderee(valeurs, poids, metropole)),
        )
        for niveau, agregats in niveaux:
            for code, agregat in sorted(agregats.items()):
                yield Ligne(
                    indicateur=indicateur,
                    niveau=niveau,
                    code=code,
                    periode=date(annee, 1, 1),
                    periode_type="ANNEE",
                    sexe="T",
                    age_min=None,
                    age_max=None,
                    valeur=round(agregat.valeur, 2),
                    statut="DEFINITIF",
                    modalite=("taille_appartement", taille) if taille else None,
                )


CARTE_DES_LOYERS = CarteDesLoyers()
