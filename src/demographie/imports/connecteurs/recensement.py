"""Recensement de la population : population de 15 ans ou plus selon le statut d'activité.

Jeu Melodi DS_RP_EMPLOI_LR_PRINC (« Population active et chômage »). Le fichier complet
pèse 120 Mo car il descend à la commune : on interroge plutôt l'API de données, niveau
par niveau (France, régions, départements), et on assemble les réponses dans un seul
fichier JSON trié, archivé comme brut. Une dizaine d'appels espacés de 2 secondes.

Les millésimes du recensement sont des moyennes sur 5 ans : l'INSEE déconseille de
comparer deux millésimes séparés de moins de 5 ans (avertissement porté par les
indicateurs).
"""

import json
import tempfile
import time
import urllib.parse
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

API = "https://api.insee.fr/melodi/data"
PAR_PAGE = 1000
PAUSE = 2.0  # secondes entre deux appels (limite officielle : 30 par minute)
_FRANCE = {"F": "FR", "FM": "FM"}
_AGES = {"Y15T64": (15, 64), "Y_GE15": (15, None)}
# Statut d'activité déclaré au recensement -> modalité « statut_activite ».
_STATUTS = {
    "_T": None,
    "1T2": "ACTIF",
    "1": "ACTIF_OCCUPE",
    "2": "CHOMEUR",
    "3": "INACTIF",
    "31": "RETRAITE",
    "33": "ETUDIANT",
    "35T36": "AUTRE_INACTIF",
}


class RecensementActivite:
    source = "INSEE_RP"
    jeu = "DS_RP_EMPLOI_LR_PRINC"
    niveaux_publies = frozenset({"FRANCE", "REG", "DEP"})
    niveaux_geo = ("FRANCE", "REG", "DEP")

    @property
    def nom_fichier(self) -> str:
        return f"{self.jeu}.json"

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def fichiers(self) -> list[Fichier]:
        return [Fichier(url=f"{API}/{self.jeu}", nom=self.nom_fichier)]

    def _requetes(self) -> Iterator[str]:
        for niveau in self.niveaux_geo:
            for age in _AGES:
                filtres = {"GEO": niveau, "AGE": age, "SEX": "_T", "EDUC": "_T"}
                yield f"{API}/{self.jeu}?{urllib.parse.urlencode(filtres)}&maxResult={PAR_PAGE}"

    def telecharger(self, fichier: Fichier, dossier: Path) -> Path:
        """Interroge l'API page par page et écrit les observations triées dans un JSON."""
        observations = []
        premier = True
        for requete in self._requetes():
            page = 1
            while True:
                if not premier:
                    time.sleep(PAUSE)
                premier = False
                reponse = telechargement.lire_json(f"{requete}&page={page}")
                if not isinstance(reponse, dict) or "observations" not in reponse:
                    raise FichierIllisible(f"Réponse inattendue de Melodi pour {requete}")
                observations += reponse["observations"]
                # « isLast » n'est présent qu'à partir de la 2e page : une page pleine
                # sans lui appelle la suivante.
                dernier = reponse.get("paging", {}).get("isLast", False)
                if dernier or len(reponse["observations"]) < PAR_PAGE:
                    break
                page += 1
        observations.sort(key=lambda o: json.dumps(o["dimensions"], sort_keys=True))
        dossier.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=dossier, suffix=".part", delete=False, encoding="utf-8"
        ) as sortie:
            json.dump({"jeu": self.jeu, "observations": observations}, sortie, sort_keys=True)
        return Path(sortie.name)

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        try:
            contenu = json.loads(chemin.read_text(encoding="utf-8"))
            observations = contenu["observations"]
        except (ValueError, KeyError, TypeError) as erreur:
            raise FichierIllisible(f"JSON illisible : {erreur}") from erreur
        if not observations:
            raise FichierIllisible("Aucune observation")
        for obs in observations:
            try:
                dim = obs["dimensions"]
                valeur = Decimal(str(obs["measures"]["OBS_VALUE_NIVEAU"]["value"]))
            except (KeyError, TypeError, ArithmeticError) as erreur:
                raise FichierIllisible(f"Observation illisible : {obs}") from erreur
            if dim.get("EMPSTA_ENQ") not in _STATUTS or dim.get("AGE") not in _AGES:
                continue  # sous-catégories plus fines non retenues
            if dim.get("SEX") != "_T" or dim.get("EDUC") != "_T" or dim.get("RP_MEASURE") != "POP":
                raise FichierIllisible(f"Dimensions inattendues : {dim}")
            territoire = self._territoire(dim.get("GEO", ""))
            if territoire is None:
                continue
            age_min, age_max = _AGES[dim["AGE"]]
            statut = _STATUTS[dim["EMPSTA_ENQ"]]
            yield Ligne(
                indicateur="POP_RP",
                niveau=territoire[0],
                code=territoire[1],
                periode=date(int(dim["TIME_PERIOD"]), 1, 1),
                periode_type="RP",
                sexe="T",
                age_min=age_min,
                age_max=age_max,
                valeur=valeur,
                statut="DEFINITIF",
                modalite=("statut_activite", statut) if statut else None,
            )

    @staticmethod
    def _territoire(geo: str) -> tuple[str, str] | None:
        """« 2026-DEP-75 » -> ("DEP", "75") ; « 2026-FRANCE-F » -> ("FRANCE", "FR")."""
        morceaux = geo.split("-", 2)
        if len(morceaux) != 3:
            raise FichierIllisible(f"Code géographique inattendu : {geo}")
        _millesime, niveau, code = morceaux
        if niveau == "FRANCE":
            return ("FRANCE", _FRANCE[code]) if code in _FRANCE else None
        if niveau in ("REG", "DEP"):
            return (niveau, code)
        return None


RECENSEMENT = RecensementActivite()
