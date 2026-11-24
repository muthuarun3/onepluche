"""Surendettement des ménages : enquête typologique annuelle de la Banque de France.

La Banque de France publie chaque février, pour l'année écoulée, treize classeurs XLSX
régionaux (« SUREN-AAAA_<Région>.xlsx »), avec un onglet par département : dossiers
traités et endettement médian par grande famille de dettes. Le nom des fichiers, leur
dossier (`/system/files/AAAA-MM/`) et l'adresse de la page changent chaque année : on
cherche la page de l'année écoulée, puis de l'année d'avant, et on y lit les liens.

Les treize classeurs sont assemblés dans une archive ZIP, archivée comme brut. Outre-mer :
hors champ (l'IEDOM publie à part) et déclaré absent. La France métropolitaine est la somme
des départements pour les dossiers ; l'endettement médian n'a pas de valeur nationale.

Réutilisation libre en citant la Banque de France et la date de mise à jour (informations
légales du site).
"""

import re
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import zipfile
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

SITE = "https://www.banque-france.fr"
# Adresses connues de la page annuelle (elle a changé entre 2024 et 2025).
PAGES = (
    "/fr/publications-et-statistiques/publications/typologie-du-surendettement-des-menages-{annee}",
    "/fr/publications-et-statistiques/statistiques/"
    "enquete-typologique-sur-le-surendettement-des-menages-en-{annee}",
)
CLASSEURS_ATTENDUS = 13  # régions métropolitaines

# Ligne du tableau départemental -> modalité de l'endettement médian (None : toutes dettes).
_FAMILLES = {
    "endettement global": None,
    "endettement (hors dettes immobilieres)": "HORS_IMMOBILIER",
    "dettes immobilieres": "IMMOBILIER",
    "dettes a la consommation": "CONSOMMATION",
    "dettes de charges courantes": "CHARGES_COURANTES",
}


def _normaliser(texte: object) -> str:
    sans_accents = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore")
    return re.sub(r"\s+", " ", sans_accents.decode().lower()).strip()


def _cle_departement(texte: str) -> str:
    return re.sub(r"[^a-z]", "", _normaliser(texte))


class Surendettement:
    source = "BDF_SUREN"
    niveaux_publies = frozenset({"FRANCE", "DEP"})
    controle_couverture = True
    departements_absents = frozenset({"971", "972", "973", "974", "976"})

    def accepte(self, nom_fichier: str) -> bool:
        return re.fullmatch(r"SUREN-\d{4}\.zip", nom_fichier) is not None

    @staticmethod
    def liens(page: str, annee: int) -> list[str]:
        """Liens des classeurs régionaux d'une année, sans les classeurs outre-mer,
        national, de comparaisons régionales ni les cahiers."""
        motif = rf'href="([^"]*/SUREN-{annee}_[^"/]+\.xlsx)"'
        liens = []
        for lien in dict.fromkeys(re.findall(motif, page)):
            nom = Path(urllib.parse.unquote(lien.rsplit("/", 1)[-1])).stem
            mots = nom.upper().split("_")
            if {"DOM", "NATIONAL"} & set(mots) or re.search("COMPARAISON|CAHIER", nom.upper()):
                continue
            liens.append(urllib.parse.urljoin(SITE, lien))
        return liens

    def _page(self, annee: int) -> tuple[str, list[str]] | None:
        for modele in PAGES:
            url = SITE + modele.format(annee=annee)
            try:
                page = telechargement.lire_page(url)
            except urllib.error.HTTPError:
                continue
            liens = self.liens(page, annee)
            if liens:
                return url, liens
        return None

    def fichiers(self) -> list[Fichier]:
        annee_courante = date.today().year
        for annee in (annee_courante - 1, annee_courante - 2):
            trouve = self._page(annee)
            if trouve is not None:
                url, liens = trouve
                if len(liens) != CLASSEURS_ATTENDUS:
                    raise FichierIllisible(
                        f"{len(liens)} classeurs régionaux publiés pour {annee} "
                        f"({CLASSEURS_ATTENDUS} attendus)"
                    )
                return [Fichier(url=url, nom=f"SUREN-{annee}.zip", millesime=str(annee))]
        raise FichierIllisible("Aucune page de l'enquête typologique trouvée")

    def telecharger(self, fichier: Fichier, dossier: Path) -> Path:
        """Télécharge les treize classeurs de la page et les range dans une archive ZIP."""
        annee = int(fichier.millesime)
        liens = self.liens(telechargement.lire_page(fichier.url), annee)
        if len(liens) != CLASSEURS_ATTENDUS:
            raise FichierIllisible(f"{len(liens)} classeurs régionaux trouvés")
        dossier.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dossier, suffix=".part", delete=False) as sortie:
            archive_chemin = Path(sortie.name)
        with zipfile.ZipFile(archive_chemin, "w", zipfile.ZIP_DEFLATED) as archive:
            for lien in sorted(liens):
                classeur = telechargement.telecharger(lien, dossier)
                try:
                    nom = urllib.parse.unquote(lien.rsplit("/", 1)[-1])
                    archive.write(classeur, nom)
                finally:
                    classeur.unlink(missing_ok=True)
        return archive_chemin

    def lire(self, chemin: Path, referentiel: Referentiel) -> Iterator[Ligne]:
        par_nom = {
            _cle_departement(libelle): code
            for code, libelle in referentiel.libelles_departements.items()
            if referentiel.region_du_departement.get(code) not in REGIONS_OUTRE_MER
        }
        try:
            archive = zipfile.ZipFile(chemin)
        except zipfile.BadZipFile as erreur:
            raise FichierIllisible(f"Archive illisible : {erreur}") from erreur
        lues: dict[str, dict[str | None, tuple[Decimal, Decimal]]] = {}
        annees = set()
        with archive:
            for membre in archive.namelist():
                annee = re.match(r"SUREN-(\d{4})_", membre)
                if annee is None or not membre.endswith(".xlsx"):
                    raise FichierIllisible(f"Fichier inattendu dans l'archive : {membre}")
                annees.add(int(annee[1]))
                with archive.open(membre) as flux:
                    lues.update(self._classeur(flux, par_nom, membre))
        if len(annees) != 1:
            raise FichierIllisible(f"Plusieurs années dans l'archive : {sorted(annees)}")
        manquants = sorted(set(par_nom.values()) - set(lues))
        if manquants:
            raise FichierIllisible(f"Onglets départementaux manquants : {', '.join(manquants)}")
        (annee,) = annees
        total = Decimal(0)
        for code, familles in sorted(lues.items()):
            dossiers, _ = familles[None]
            total += dossiers
            yield self._ligne("DOSSIERS_SURENDETTEMENT", annee, "DEP", code, None, dossiers)
            for modalite, (nombre, mediane) in familles.items():
                if nombre == 0:
                    continue  # aucune dette de cette famille : pas de médiane
                yield self._ligne("ENDETTEMENT_MEDIAN", annee, "DEP", code, modalite, mediane)
        yield self._ligne("DOSSIERS_SURENDETTEMENT", annee, "FRANCE", "FM", None, total)

    @staticmethod
    def _classeur(flux, par_nom: dict[str, str], membre: str) -> dict:
        try:
            classeur = load_workbook(flux, read_only=True, data_only=True)
        except Exception as erreur:  # zip invalide, XML interne mal formé…
            raise FichierIllisible(f"Classeur illisible ({membre}) : {erreur}") from erreur
        resultat = {}
        try:
            for nom in classeur.sheetnames:
                code = par_nom.get(_cle_departement(nom))
                if code is None:
                    continue  # onglets de la région, du sommaire, des comparaisons
                feuille = classeur[nom]
                feuille.reset_dimensions()
                resultat[code] = Surendettement._tableau(feuille, nom)
        finally:
            classeur.close()
        return resultat

    @staticmethod
    def _tableau(feuille, nom: str) -> dict[str | None, tuple[Decimal, Decimal]]:
        """{famille: (dossiers traités, endettement médian)} d'un onglet départemental."""
        colonnes = None
        familles = {}
        for rang in feuille.iter_rows(values_only=True):
            cellules = [_normaliser(c) for c in rang]
            if colonnes is None:
                if any(c.startswith("nombre de dossiers") for c in cellules):
                    colonnes = (
                        next(i for i, c in enumerate(cellules) if c.startswith("nombre de doss")),
                        next(i for i, c in enumerate(cellules) if c.startswith("endettement med")),
                    )
                continue
            libelle = next((c for c in cellules if c), "")
            if libelle not in _FAMILLES:
                continue
            try:
                dossiers, mediane = (Decimal(str(rang[i])) for i in colonnes)
            except (InvalidOperation, IndexError, TypeError) as erreur:
                raise FichierIllisible(f"Ligne illisible ({nom}) : {rang[:8]}") from erreur
            familles[_FAMILLES[libelle]] = (dossiers, mediane.quantize(Decimal(1)))
        if set(familles) != set(_FAMILLES.values()):
            raise FichierIllisible(f"Tableau incomplet dans l'onglet {nom}")
        return familles

    @staticmethod
    def _ligne(indicateur, annee, niveau, code, modalite, valeur) -> Ligne:
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
            modalite=("type_dette", modalite) if modalite else None,
        )


SURENDETTEMENT = Surendettement()
