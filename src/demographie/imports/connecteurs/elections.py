"""Résultats des élections (ministère de l'Intérieur), rubrique VOTES.

Dossier de conception de l'appli « Que pensent et votent les Français ? », étapes 2, 5 et 6.

data.gouv.fr publie, à partir des fichiers du ministère de l'Intérieur, deux fichiers
Parquet qui harmonisent toutes les élections depuis 1999, bureau de vote par bureau de
vote : « Résultats généraux » (inscrits, abstentions, votants, blancs, nuls, exprimés) et
« Résultats par candidat » (voix de chaque candidat ou liste, avec sa nuance). Ils sont mis
à jour quelques semaines après chaque élection.

Le connecteur lit seulement les colonnes utiles des 20 tours retenus (``SCRUTINS``) et
additionne les bureaux par département. Il ne garde aucun nom de bureau ni de commune.

Territoires :
- départements : codes du COG ; les anciens codes du ministère pour l'outre-mer
  (ZA Guadeloupe, ZB Martinique, ZC Guyane, ZD La Réunion, ZM Mayotte) sont convertis ;
- ``HORS_DEP/ZZ`` : Français de l'étranger ;
- ``HORS_DEP/COM`` : collectivités d'outre-mer (Saint-Pierre-et-Miquelon, Saint-Barthélemy,
  Saint-Martin, Wallis-et-Futuna, Polynésie française, Nouvelle-Calédonie) ;
- France métropolitaine = départements métropolitains ; France = tout. Pour 2002 et 2007,
  le fichier ne contient ni les Français de l'étranger ni les collectivités d'outre-mer :
  la France entière n'est pas publiée pour ces deux années, seulement la France
  métropolitaine et les départements.

Ce que l'électeur a choisi (dimension ``choix``) : un candidat à la présidentielle, une liste
aux européennes, une nuance aux législatives (les candidats changent d'une circonscription à
l'autre ; leur nuance, attribuée par le ministère, s'additionne). Libellés officiels tels
quels, sans regroupement en blocs. Municipales : participation seulement.

Avant 2014, les votes blancs étaient comptés avec les nuls : on publie toujours
``BLANCS_ET_NULS``, et ``BLANCS`` et ``NULS`` séparément seulement quand le fichier les
distingue.

Contrôles propres (l'import est rejeté sinon) : pour chaque scrutin et chaque territoire,
inscrits = abstentions + votants et votants = blancs + nuls + exprimés ; aux premiers tours,
les 101 départements (sauf Mayotte en 2002). La somme des voix n'est pas comparée aux
exprimés : aux législatives de 2024, le fichier source a des écarts d'une ou deux voix
dans quelques bureaux.
"""

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from demographie.imports import telechargement
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

JEU = "https://www.data.gouv.fr/api/1/datasets/6481e741d4cf002ec0efec9d/"


@dataclass(frozen=True)
class Scrutin:
    code: str  # modalité de la dimension « scrutin » (migration 032)
    jour: date
    type_choix: str | None  # CANDIDAT, LISTE, NUANCE ; None : participation seulement
    # Le fichier contient les Français de l'étranger et les collectivités d'outre-mer.
    complet: bool = True


# id_election du fichier -> scrutin retenu (dossier de conception, étape 1).
SCRUTINS = {
    "2002_pres_t1": Scrutin("PRES_2002_T1", date(2002, 4, 21), "CANDIDAT", complet=False),
    "2002_pres_t2": Scrutin("PRES_2002_T2", date(2002, 5, 5), "CANDIDAT", complet=False),
    "2007_pres_t1": Scrutin("PRES_2007_T1", date(2007, 4, 22), "CANDIDAT", complet=False),
    "2007_pres_t2": Scrutin("PRES_2007_T2", date(2007, 5, 6), "CANDIDAT", complet=False),
    "2012_pres_t1": Scrutin("PRES_2012_T1", date(2012, 4, 22), "CANDIDAT"),
    "2012_pres_t2": Scrutin("PRES_2012_T2", date(2012, 5, 6), "CANDIDAT"),
    "2017_pres_t1": Scrutin("PRES_2017_T1", date(2017, 4, 23), "CANDIDAT"),
    "2017_pres_t2": Scrutin("PRES_2017_T2", date(2017, 5, 7), "CANDIDAT"),
    "2019_euro_t1": Scrutin("EURO_2019_T1", date(2019, 5, 26), "LISTE"),
    "2020_muni_t1": Scrutin("MUNI_2020_T1", date(2020, 3, 15), None),
    "2020_muni_t2": Scrutin("MUNI_2020_T2", date(2020, 6, 28), None),
    "2022_pres_t1": Scrutin("PRES_2022_T1", date(2022, 4, 10), "CANDIDAT"),
    "2022_pres_t2": Scrutin("PRES_2022_T2", date(2022, 4, 24), "CANDIDAT"),
    "2022_legi_t1": Scrutin("LEGI_2022_T1", date(2022, 6, 12), "NUANCE"),
    "2022_legi_t2": Scrutin("LEGI_2022_T2", date(2022, 6, 19), "NUANCE"),
    "2024_euro_t1": Scrutin("EURO_2024_T1", date(2024, 6, 9), "LISTE"),
    "2024_legi_t1": Scrutin("LEGI_2024_T1", date(2024, 6, 30), "NUANCE"),
    "2024_legi_t2": Scrutin("LEGI_2024_T2", date(2024, 7, 7), "NUANCE"),
    "2026_muni_t1": Scrutin("MUNI_2026_T1", date(2026, 3, 15), None),
    "2026_muni_t2": Scrutin("MUNI_2026_T2", date(2026, 3, 22), None),
}

# Nuances des candidats aux législatives, libellés des grilles du ministère de l'Intérieur
# (circulaires de 2022 et de 2024). Une nuance absente arrête l'import.
NUANCES = {
    "LEGI_2022": {
        "DXG": "Divers extrême gauche",
        "RDG": "Parti radical de gauche",
        "NUP": "Nouvelle union populaire écologique et sociale",
        "DVG": "Divers gauche",
        "ECO": "Écologistes",
        "DIV": "Divers",
        "REG": "Régionalistes",
        "ENS": "Ensemble ! (majorité présidentielle)",
        "DVC": "Divers centre",
        "UDI": "Union des démocrates et indépendants",
        "LR": "Les Républicains",
        "DVD": "Divers droite",
        "DSV": "Droite souverainiste",
        "REC": "Reconquête !",
        "RN": "Rassemblement national",
        "DXD": "Divers extrême droite",
    },
    "LEGI_2024": {
        "EXG": "Extrême gauche",
        "COM": "Parti communiste français",
        "FI": "La France insoumise",
        "SOC": "Parti socialiste",
        "RDG": "Parti radical de gauche",
        "VEC": "Les Écologistes",
        "DVG": "Divers gauche",
        "UG": "Union de la gauche",
        "ECO": "Écologistes",
        "REG": "Régionalistes",
        "DIV": "Divers",
        "REN": "Renaissance",
        "MDM": "Modem",
        "HOR": "Horizons",
        "ENS": "Ensemble ! (majorité présidentielle)",
        "DVC": "Divers centre",
        "UDI": "Union des démocrates et indépendants",
        "LR": "Les Républicains",
        "DVD": "Divers droite",
        "DSV": "Droite souverainiste",
        "REC": "Reconquête !",
        "RN": "Rassemblement national",
        "UXD": "Union de l'extrême droite",
        "EXD": "Extrême droite",
    },
}

# Anciens codes du ministère pour l'outre-mer.
DEPARTEMENTS_OUTRE_MER = {"ZA": "971", "ZB": "972", "ZC": "973", "ZD": "974", "ZM": "976"}
COLLECTIVITES = frozenset({"ZS", "ZN", "ZP", "ZW", "ZX", "975", "977", "978", "986", "987", "988"})
DEPARTEMENTS_METROPOLE = frozenset({f"{n:02d}" for n in range(1, 96) if n != 20} | {"2A", "2B"})
DEPARTEMENTS = DEPARTEMENTS_METROPOLE | {"971", "972", "973", "974", "976"}

PARTICIPATION = ("inscrits", "abstentions", "votants", "blancs", "nuls", "exprimes")


def territoire(code_departement: str) -> tuple[str, str]:
    """(niveau, code) d'un bureau de vote à partir du code département du fichier."""
    code = DEPARTEMENTS_OUTRE_MER.get(code_departement, code_departement)
    if code in DEPARTEMENTS:
        return ("DEP", code)
    if code in COLLECTIVITES:
        return ("HORS_DEP", "COM")
    if code == "ZZ":
        return ("HORS_DEP", "ZZ")
    raise FichierIllisible(f"Code de département inconnu : {code_departement!r}")


def _territoires_agreges(code: tuple[str, str], scrutin: Scrutin) -> list[tuple[str, str]]:
    """Le territoire du bureau, puis la France métropolitaine et la France entière qui
    l'additionnent."""
    cibles = [code]
    if code[0] == "DEP" and code[1] in DEPARTEMENTS_METROPOLE:
        cibles.append(("FRANCE", "FM"))
    if scrutin.complet:
        cibles.append(("FRANCE", "FR"))
    return cibles


def _ressource(titre: str) -> Fichier:
    jeu = telechargement.lire_json(JEU)
    ressources = jeu.get("resources", []) if isinstance(jeu, dict) else []
    retenues = [
        r
        for r in ressources
        if r.get("title") == titre and str(r.get("format", "")).lower() == "parquet"
    ]
    if len(retenues) != 1:
        raise FichierIllisible(f"Ressource Parquet « {titre} » introuvable ou en double")
    r = retenues[0]
    return Fichier(
        url=r["url"],
        nom=Path(r["url"]).name,
        # Date de mise à jour de data.gouv.fr : inchangée, rien n'est téléchargé.
        millesime=str(r.get("last_modified", ""))[:19] or None,
    )


def _lots(chemin: Path, colonnes: list[str]):
    """Lots de lignes des tours retenus, en ne lisant que les colonnes utiles."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    try:
        fichier = pq.ParquetFile(chemin)
    except Exception as erreur:  # pyarrow lève des types variés sur un fichier abîmé
        raise FichierIllisible(f"Parquet illisible : {erreur}") from erreur
    manquantes = set(colonnes) - set(fichier.schema_arrow.names)
    if manquantes:
        raise FichierIllisible(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
    retenus = list(SCRUTINS)
    for lot in fichier.iter_batches(batch_size=100_000, columns=colonnes):
        filtre = pc.is_in(lot.column("id_election"), value_set=_tableau(retenus))
        lot = lot.filter(filtre)
        if lot.num_rows:
            yield pa.Table.from_batches([lot])


def _tableau(valeurs: list[str]):
    import pyarrow as pa

    return pa.array(valeurs, pa.string())


def _verifier_couverture(vus: dict[str, set[str]]) -> None:
    for id_election, scrutin in SCRUTINS.items():
        if not scrutin.code.endswith("_T1"):
            continue  # un second tour n'a lieu que là où il est nécessaire
        if id_election not in vus:
            raise FichierIllisible(f"Scrutin absent du fichier : {id_election}")
        attendus = DEPARTEMENTS - ({"976"} if scrutin.jour.year == 2002 else set())
        manquants = attendus - vus[id_election]
        if manquants:
            raise FichierIllisible(
                f"{id_election} : départements absents ({', '.join(sorted(manquants))})"
            )


@lru_cache(maxsize=1)
def lire_participation(
    chemin: Path, couverture: bool = True
) -> dict[tuple[str, tuple[str, str]], list[int | None]]:
    """(id_election, territoire) -> [inscrits, abstentions, votants, blancs, nuls,
    exprimés] ; blancs None quand le fichier ne les distingue pas des nuls.

    ``couverture`` : exiger les 20 tours et tous les départements (fichier complet)."""
    colonnes = ["id_election", "code_departement", *PARTICIPATION]
    sommes: dict[tuple[str, tuple[str, str]], list[int | None]] = {}
    vus: dict[str, set[str]] = defaultdict(set)
    for lot in _lots(chemin, colonnes):
        groupes = lot.group_by(["id_election", "code_departement"]).aggregate(
            [(c, "sum") for c in PARTICIPATION] + [("blancs", "count")]
        )
        for g in groupes.to_pylist():
            scrutin = SCRUTINS[g["id_election"]]
            code = territoire(g["code_departement"])
            if code[0] == "DEP":
                vus[g["id_election"]].add(code[1])
            valeurs = [g[f"{c}_sum"] or 0 for c in PARTICIPATION]
            if g["blancs_count"] == 0:
                valeurs[3] = None  # blancs comptés avec les nuls (avant 2014)
            for cible in _territoires_agreges(code, scrutin):
                cle = (g["id_election"], cible)
                if cle not in sommes:
                    sommes[cle] = valeurs.copy()
                    continue
                cumul = sommes[cle]
                for i, v in enumerate(valeurs):
                    cumul[i] = None if cumul[i] is None or v is None else cumul[i] + v
    if couverture:
        _verifier_couverture(vus)
    for (id_election, (niveau, code)), (ins, abst, vot, bl, nuls, exp) in sommes.items():
        blancs_et_nuls = (bl or 0) + nuls
        if ins != abst + vot or vot != blancs_et_nuls + exp:
            raise FichierIllisible(
                f"{id_election} {niveau} {code} : inscrits {ins}, abstentions {abst}, "
                f"votants {vot}, blancs et nuls {blancs_et_nuls}, exprimés {exp} incohérents"
            )
    return sommes


def _nom_complet(prenom: str | None, nom: str | None) -> str:
    prenom = (prenom or "").strip()
    if prenom.isupper():  # « JACQUES » en 2002 : « Jacques »
        prenom = "-".join(p.capitalize() for p in prenom.split("-"))
    return f"{prenom} {(nom or '').strip()}".strip()


@dataclass(frozen=True)
class Choix:
    scrutin: str
    code: str
    libelle: str
    panneau: int | None = None
    nuance: str | None = None
    nuance_libelle: str | None = None
    sexe: str | None = None


def _choix(id_election: str, scrutin: Scrutin, ligne: dict) -> Choix:
    sexe = {"M": "H", "F": "F"}.get(ligne.get("sexe") or "")
    if scrutin.type_choix == "NUANCE":
        nuance = (ligne["nuance"] or "").strip()
        grille = NUANCES[scrutin.code[:9]]
        if nuance not in grille:
            raise FichierIllisible(f"{id_election} : nuance inconnue {nuance!r}")
        return Choix(
            scrutin.code,
            f"{scrutin.code}_{nuance}",
            grille[nuance],
            nuance=nuance,
            nuance_libelle=grille[nuance],
        )
    panneau = ligne["no_panneau"]
    if not panneau:
        raise FichierIllisible(f"{id_election} : candidat ou liste sans numéro de panneau")
    if scrutin.type_choix == "CANDIDAT":
        libelle = _nom_complet(ligne["prenom"], ligne["nom"])
        return Choix(scrutin.code, f"{scrutin.code}_P{panneau:02d}", libelle, panneau, sexe=sexe)
    libelle = (ligne["libelle_etendu_liste"] or ligne["libelle_abrege_liste"] or "").strip()
    tete = (ligne["nom_tete_liste"] or "").strip()
    if tete:
        libelle = f"{libelle} ({tete})"
    return Choix(scrutin.code, f"{scrutin.code}_L{panneau:02d}", libelle, panneau)


@lru_cache(maxsize=1)
def lire_voix(
    chemin: Path, couverture: bool = True
) -> tuple[dict[str, Choix], dict[tuple[str, tuple[str, str]], int]]:
    """Choix de chaque scrutin (par code) et voix par (code du choix, territoire)."""
    colonnes = [
        "id_election",
        "code_departement",
        "no_panneau",
        "voix",
        "nuance",
        "sexe",
        "nom",
        "prenom",
        "libelle_abrege_liste",
        "libelle_etendu_liste",
        "nom_tete_liste",
    ]
    choix: dict[str, Choix] = {}
    voix: dict[tuple[str, tuple[str, str]], int] = defaultdict(int)
    avec_choix = [i for i, s in SCRUTINS.items() if s.type_choix]
    cles = ["id_election", "code_departement", "no_panneau", "nuance", "sexe", "nom", "prenom",
            "libelle_abrege_liste", "libelle_etendu_liste", "nom_tete_liste"]  # fmt: skip
    for lot in _lots(chemin, colonnes):
        import pyarrow.compute as pc

        lot = lot.filter(pc.is_in(lot.column("id_election"), value_set=_tableau(avec_choix)))
        if not lot.num_rows:
            continue
        for g in lot.group_by(cles).aggregate([("voix", "sum")]).to_pylist():
            scrutin = SCRUTINS[g["id_election"]]
            c = _choix(g["id_election"], scrutin, g)
            connu = choix.setdefault(c.code, c)
            if connu.libelle != c.libelle and scrutin.type_choix != "NUANCE":
                raise FichierIllisible(
                    f"{c.code} : deux libellés pour le même panneau ({connu.libelle!r}, "
                    f"{c.libelle!r})"
                )
            for cible in _territoires_agreges(territoire(g["code_departement"]), scrutin):
                voix[(c.code, cible)] += g["voix_sum"] or 0
    for id_election, scrutin in SCRUTINS.items() if couverture else ():
        if scrutin.type_choix and not any(c.scrutin == scrutin.code for c in choix.values()):
            raise FichierIllisible(f"Scrutin absent du fichier : {id_election}")
    return choix, dict(voix)


class _Elections:
    source = "MI_ELECTIONS"
    niveaux_publies = frozenset({"FRANCE", "DEP", "HORS_DEP"})
    # France = départements + territoires hors département : contrôlé par le pipeline.
    tolerance_sommes = 0.0
    # La date de mise à jour de data.gouv.fr suffit à savoir si le fichier a changé.
    saute_si_millesime_connu = True
    titre = ""
    nom_attendu = ""
    # Fichier complet attendu (False pour un extrait de test).
    couverture = True

    def fichiers(self) -> list[Fichier]:
        return [_ressource(self.titre)]

    def accepte(self, nom_fichier: str) -> bool:
        return nom_fichier == self.nom_attendu


class ParticipationElections(_Elections):
    titre = "Résultats généraux"
    nom_attendu = "general_results.parquet"

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        for (id_election, (niveau, code)), valeurs in lire_participation(
            chemin, self.couverture
        ).items():
            scrutin = SCRUTINS[id_election]
            inscrits, abstentions, votants, blancs, nuls, exprimes = valeurs
            mesures = {
                "INSCRITS": inscrits,
                "ABSTENTIONS": abstentions,
                "VOTANTS": votants,
                "BLANCS_ET_NULS": (blancs or 0) + nuls,
                "EXPRIMES": exprimes,
            }
            if blancs is not None:
                mesures |= {"BLANCS": blancs, "NULS": nuls}
            for indicateur, valeur in mesures.items():
                yield Ligne(
                    indicateur, niveau, code, scrutin.jour, "SCRUTIN", "T", None, None,
                    valeur, "DEFINITIF",
                )  # fmt: skip


class VoixElections(_Elections):
    titre = "Résultats par candidat"
    nom_attendu = "candidats_results.parquet"

    def choix(self, chemin: Path) -> list[Choix]:
        """Choix à déclarer (ref.ajouter_choix) avant le chargement des voix."""
        return list(lire_voix(chemin, self.couverture)[0].values())

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        choix, voix = lire_voix(chemin, self.couverture)
        for (code_choix, (niveau, code)), valeur in voix.items():
            jour = next(s.jour for s in SCRUTINS.values() if s.code == choix[code_choix].scrutin)
            yield Ligne(
                "VOIX", niveau, code, jour, "SCRUTIN", "T", None, None, valeur, "DEFINITIF",
                modalite=("choix", code_choix),
            )  # fmt: skip


PARTICIPATION_ELECTIONS = ParticipationElections()
VOIX_ELECTIONS = VoixElections()
