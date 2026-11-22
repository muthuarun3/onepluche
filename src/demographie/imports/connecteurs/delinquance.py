"""Délinquance enregistrée par la police et la gendarmerie (SSMSI, ministère de l'Intérieur).

Dossier de conception de l'appli « Les Français sont-ils en sécurité ? », étape 6.

Le SSMSI publie chaque année en juillet, sur data.gouv.fr, une base départementale : une
ligne par département, année (depuis 2016) et indicateur, avec le nombre de faits, le taux
pour 1 000 habitants (pour 1 000 logements pour les cambriolages) et la population ou le
nombre de logements utilisés. L'édition de juillet est définitive.

Le fichier n'a pas de ligne France : la France, la France métropolitaine et les régions
sont la somme des départements, et leur taux est rapporté à la somme des populations (ou
des logements). On garde le taux départemental du SSMSI tel quel.

Les colonnes et les libellés d'indicateurs sont lus par leur nom ; une colonne ou un
indicateur attendu qui disparaît, ou une unité de compte qui change, arrête l'import.
"""

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.connecteurs import fichier
from demographie.imports.connecteurs.communes import DROM
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

JEU = "https://www.data.gouv.fr/api/1/datasets/621df2954fa5a3b5a023e23c/"
RESSOURCE = "DEP - Base statistique départementale"
FORMAT = fichier.FormatCSV(encodage="utf-8-sig", separateur=";", decimale=",")
COLONNES = frozenset(
    {
        "Code_departement",
        "annee",
        "indicateur",
        "unite_de_compte",
        "nombre",
        "taux_pour_mille",
        "insee_pop",
        "insee_log",
    }
)
PREMIERE_ANNEE = 2016

# Libellé du SSMSI -> (code de l'atteinte, unité de compte attendue, base du taux).
ATTEINTES = {
    "Homicides": ("HOMICIDES", "Victime", "insee_pop"),
    "Tentatives d'homicide": ("TENTATIVES_HOMICIDE", "Victime", "insee_pop"),
    "Violences physiques intrafamiliales": ("VIOLENCES_INTRAFAMILIALES", "Victime", "insee_pop"),
    "Violences physiques hors cadre familial": ("VIOLENCES_HORS_FAMILLE", "Victime", "insee_pop"),
    "Violences sexuelles": ("VIOLENCES_SEXUELLES", "Victime", "insee_pop"),
    "Vols avec armes": ("VOLS_ARMES", "Infraction", "insee_pop"),
    "Vols violents sans arme": ("VOLS_VIOLENTS", "Infraction", "insee_pop"),
    "Vols sans violence contre des personnes": (
        "VOLS_SANS_VIOLENCE",
        "Victime entendue",
        "insee_pop",
    ),
    "Cambriolages de logement": ("CAMBRIOLAGES", "Infraction", "insee_log"),
    "Vols de véhicule": ("VOLS_VEHICULES", "Véhicule", "insee_pop"),
    "Vols dans les véhicules": ("VOLS_DANS_VEHICULES", "Véhicule", "insee_pop"),
    "Vols d'accessoires sur véhicules": ("VOLS_ACCESSOIRES", "Véhicule", "insee_pop"),
    "Destructions et dégradations volontaires": ("DEGRADATIONS", "Infraction", "insee_pop"),
    "Escroqueries et fraudes aux moyens de paiement": ("ESCROQUERIES", "Victime", "insee_pop"),
    "Usage de stupéfiants": ("USAGE_STUPEFIANTS", "Mis en cause", "insee_pop"),
    "Trafic de stupéfiants": ("TRAFIC_STUPEFIANTS", "Mis en cause", "insee_pop"),
}
# Déclinaisons de l'usage de stupéfiants (avec ou sans amende forfaitaire) : le total suffit.
IGNORES = frozenset({"Usage de stupéfiants (AFD)", "Usage de stupéfiants (hors AFD)"})
# Le SSMSI donne ses taux à 7 décimales ; on garde la même précision pour les sommes.
_PRECISION = Decimal("0.0000001")


@dataclass(frozen=True)
class DelinquanceEnregistree:
    source: str = "SSMSI_DELINQUANCE"
    nom_fichier: str = "delinquance-departements.csv"
    niveaux_publies: frozenset[str] = frozenset({"FRANCE", "REG", "DEP"})
    controle_couverture: bool = True

    def fichiers(self) -> list[Fichier]:
        jeu = telechargement.lire_json(JEU)
        ressources = jeu.get("resources", []) if isinstance(jeu, dict) else []
        retenues = [
            r
            for r in ressources
            if str(r.get("title", "")).startswith(RESSOURCE)
            and str(r.get("format", "")).lower() == "csv"
        ]
        if len(retenues) != 1:
            raise FichierIllisible(f"Ressource « {RESSOURCE} » introuvable ou en double")
        ressource = retenues[0]
        return [
            Fichier(
                url=ressource["url"],
                nom=self.nom_fichier,
                millesime=str(ressource.get("last_modified", ""))[:10] or None,
            )
        ]

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_fichier

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        # (atteinte, année, niveau, code) -> [nombre, base du taux]
        sommes: dict[tuple[str, int, str, str], list[Decimal]] = defaultdict(
            lambda: [Decimal(0), Decimal(0)]
        )
        vus: set[str] = set()
        for ligne in fichier.lire_csv(chemin, FORMAT, COLONNES):
            libelle = ligne["indicateur"]
            if libelle in IGNORES or libelle not in ATTEINTES:
                continue
            code, unite, base = ATTEINTES[libelle]
            if ligne["unite_de_compte"] != unite:
                raise FichierIllisible(
                    f"{libelle} : unité de compte « {ligne['unite_de_compte']} », "
                    f"« {unite} » attendue"
                )
            vus.add(libelle)
            departement = ligne["Code_departement"]
            annee = int(ligne["annee"])
            if annee < PREMIERE_ANNEE:
                continue
            nombre = fichier.nombre(ligne["nombre"])
            taux = fichier.nombre(ligne["taux_pour_mille"])
            denominateur = fichier.nombre(ligne[base])
            if nombre is None or taux is None or not denominateur:
                raise FichierIllisible(f"{libelle} {annee}, département {departement} : vide")
            yield from _lignes(code, annee, "DEP", departement, nombre, taux)
            territoires = [("FRANCE", "FR")]
            if departement not in DROM:
                territoires.append(("FRANCE", "FM"))
            region = referentiel.region_du_departement.get(departement)
            if region:
                territoires.append(("REG", region))
            for niveau, code_territoire in territoires:
                cumul = sommes[(code, annee, niveau, code_territoire)]
                cumul[0] += nombre
                cumul[1] += denominateur
        manquants = set(ATTEINTES) - vus
        if manquants:
            raise FichierIllisible(f"Indicateurs absents : {', '.join(sorted(manquants))}")
        for (code, annee, niveau, code_territoire), (nombre, base) in sorted(sommes.items()):
            taux = (1000 * nombre / base).quantize(_PRECISION)
            yield from _lignes(code, annee, niveau, code_territoire, nombre, taux)


def _lignes(
    atteinte: str, annee: int, niveau: str, code: str, nombre: Decimal, taux: Decimal
) -> Iterator[Ligne]:
    for indicateur, valeur in ((f"FAITS_{atteinte}", nombre), (f"TAUX_{atteinte}", taux)):
        yield Ligne(
            indicateur=indicateur,
            niveau=niveau,
            code=code,
            periode=date(annee, 1, 1),
            periode_type="ANNEE",
            sexe="T",
            age_min=None,
            age_max=None,
            valeur=int(valeur) if indicateur.startswith("FAITS_") else valeur,
            statut="DEFINITIF",
        )


DELINQUANCE = DelinquanceEnregistree()
