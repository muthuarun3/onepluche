"""Pipeline commun à toutes les sources : télécharger, lire, contrôler, publier.

Chaque fichier donne une ligne dans ingest.import :
- EN_COURS   : lecture en cours (ou interrompue : un nouvel essai la reprend) ;
- REJETE     : fichier illisible, territoire inconnu ou incohérence ; rien n'est publié ;
- EN_ATTENTE : contrôles passés mais un total varie de plus de 3 % (ou du seuil propre à
               l'indicateur : prix, médianes) par rapport à la valeur déjà publiée ;
               publication après « demo valider <n° d'import> » ;
- PUBLIE     : valeurs écrites dans stat.observation, vues recalculées.
Un connecteur de poids communaux (`poids_communaux`) remplace à la place les poids de
ingest.poids_commune pour chaque dimension et année du fichier.
Le fichier brut est conservé sous son empreinte SHA-256 dans le dossier des bruts.
"""

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg

from demographie.db import charger_sql
from demographie.imports import projections, telechargement
from demographie.imports.modele import Connecteur, Fichier, FichierIllisible, Poids, Referentiel

_SQL = Path(__file__).parent / "sql"
TOLERANCE_SOMMES = 0.005
SEUIL_VARIATION = 0.03
COMMUNES_MIN = 30_000  # poids communaux : en deçà, le fichier est incomplet
_VERROU = 7_204_011  # verrou consultatif : un seul import à la fois


@dataclass(frozen=True)
class Resultat:
    fichier: str
    statut: str  # PUBLIE, EN_ATTENTE, REJETE ou DEJA_IMPORTE
    import_id: int | None = None
    message: str = ""


class ImportImpossible(RuntimeError):
    """Action refusée (import inconnu, déjà publié, autre import en cours…)."""


def charger_referentiel(conn: psycopg.Connection) -> Referentiel:
    lignes = conn.execute(
        """SELECT t.territoire_id, t.niveau, t.code, t.libelle, p.code AS parent_code
           FROM ref.territoire t LEFT JOIN ref.territoire p ON p.territoire_id = t.parent_id"""
    )
    identifiants, regions, region_du_departement, departements = {}, {}, {}, {}
    for t in lignes.fetchall():
        identifiants[(t["niveau"], t["code"])] = t["territoire_id"]
        if t["niveau"] == "REG":
            regions[t["code"]] = t["libelle"]
        elif t["niveau"] == "DEP":
            region_du_departement[t["code"]] = t["parent_code"]
            departements[t["code"]] = t["libelle"]
    poids: dict[tuple[str, int], dict] = {}
    for p in conn.execute("SELECT dimension, annee, commune, poids FROM ingest.poids_commune"):
        poids.setdefault((p["dimension"], p["annee"]), {})[p["commune"]] = p["poids"]
    return Referentiel(identifiants, regions, region_du_departement, poids, departements)


def importer(
    conn: psycopg.Connection,
    connecteur: Connecteur,
    fichier: Fichier,
    dossier_brut: Path,
    chemin_local: Path | None = None,
    seuil_variation: float = SEUIL_VARIATION,
) -> Resultat:
    """Importe un fichier, téléchargé depuis fichier.url ou lu depuis chemin_local."""
    if not conn.execute("SELECT pg_try_advisory_lock(%s) AS ok", (_VERROU,)).fetchone()["ok"]:
        raise ImportImpossible("Un autre import est en cours")
    try:
        return _importer(conn, connecteur, fichier, dossier_brut, chemin_local, seuil_variation)
    finally:
        conn.rollback()
        conn.execute("SELECT pg_advisory_unlock(%s)", (_VERROU,))
        conn.commit()


def _importer(conn, connecteur, fichier, dossier_brut, chemin_local, seuil_variation):
    dossier_brut.mkdir(parents=True, exist_ok=True)
    temporaire = None
    if chemin_local is None:
        # Un connecteur qui assemble plusieurs requêtes fournit son propre téléchargement.
        telecharger = getattr(connecteur, "telecharger", None)
        if telecharger is not None:
            temporaire = chemin = telecharger(fichier, dossier_brut)
        else:
            temporaire = chemin = telechargement.telecharger(fichier.url, dossier_brut)
    else:
        chemin = chemin_local
    try:
        sha256 = telechargement.empreinte(chemin)
        source_id = conn.execute(
            "SELECT source_id FROM ref.source WHERE code = %s", (connecteur.source,)
        ).fetchone()["source_id"]
        existant = conn.execute(
            "SELECT import_id, statut FROM ingest.import WHERE source_id = %s AND sha256 = %s",
            (source_id, sha256),
        ).fetchone()
        if existant and existant["statut"] in ("PUBLIE", "EN_ATTENTE"):
            return Resultat(
                fichier.nom,
                "DEJA_IMPORTE",
                existant["import_id"],
                f"Fichier déjà importé (import n° {existant['import_id']}, {existant['statut']})",
            )
        brut = dossier_brut / f"{sha256}{Path(fichier.nom).suffix.lower()}"
        if not brut.exists():
            shutil.copyfile(chemin, brut)
            brut.chmod(0o440)
    finally:
        if temporaire is not None:
            temporaire.unlink(missing_ok=True)

    taille = brut.stat().st_size
    if existant:
        # Un essai précédent a été rejeté ou interrompu : on reprend la même ligne de journal.
        import_id = existant["import_id"]
        conn.execute("DELETE FROM ingest.ligne WHERE import_id = %s", (import_id,))
        conn.execute("DELETE FROM ingest.ligne_projection WHERE import_id = %s", (import_id,))
        conn.execute(
            """UPDATE ingest.import SET statut = 'EN_COURS', debut = now(), fin = NULL,
                 url = %s, fichier_nom = %s, millesime = %s, message = NULL,
                 lignes_lues = NULL, lignes_chargees = NULL
               WHERE import_id = %s""",
            (fichier.url, fichier.nom, fichier.millesime, import_id),
        )
    else:
        import_id = conn.execute(
            """INSERT INTO ingest.import (source_id, url, fichier_nom, sha256, taille_octets,
                                          millesime)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING import_id""",
            (source_id, fichier.url, fichier.nom, sha256, taille, fichier.millesime),
        ).fetchone()["import_id"]
    conn.commit()

    if getattr(connecteur, "poids_communaux", False):
        return _importer_poids(conn, import_id, connecteur, brut, fichier)
    if getattr(connecteur, "projections", False):
        with _sous_son_nom(brut, fichier, getattr(connecteur, "lit_le_nom", False)) as chemin:
            return projections.importer(
                conn, import_id, connecteur, chemin, fichier, seuil_variation
            )

    try:
        with _sous_son_nom(brut, fichier, getattr(connecteur, "lit_le_nom", False)) as chemin:
            lues, inconnus = _charger(conn, import_id, connecteur, chemin)
    except FichierIllisible as erreur:
        conn.rollback()
        return _rejeter(conn, import_id, fichier, f"Fichier illisible : {erreur}")
    if inconnus:
        liste = ", ".join(f"{n}/{c}" for n, c in sorted(inconnus)[:10])
        return _rejeter(conn, import_id, fichier, f"Territoires inconnus : {liste}", lues)

    tolerance = getattr(connecteur, "tolerance_sommes", TOLERANCE_SOMMES)
    erreurs = _controler(conn, import_id, tolerance)
    if getattr(connecteur, "controle_couverture", False):
        absents = sorted(getattr(connecteur, "departements_absents", frozenset()))
        erreurs += _controler_couverture(conn, import_id, absents)
    if erreurs:
        return _rejeter(conn, import_id, fichier, "\n".join(erreurs), lues)

    variations = conn.execute(
        charger_sql(_SQL, "controle_variations"), {"import_id": import_id, "seuil": seuil_variation}
    ).fetchall()
    if variations:
        detail = "; ".join(
            f"{v['niveau']} {v['code']} {v['periode']:%Y} : {v['ancienne']} → {v['nouvelle']}"
            for v in variations[:5]
        )
        message = f"Variation de plus de {seuil_variation:.0%} sur des totaux publiés : {detail}"
        _terminer(conn, import_id, "EN_ATTENTE", message, lues=lues)
        return Resultat(fichier.nom, "EN_ATTENTE", import_id, message)

    chargees = publier(conn, import_id)
    return Resultat(fichier.nom, "PUBLIE", import_id, f"{chargees} valeurs publiées")


@contextmanager
def _sous_son_nom(brut: Path, fichier: Fichier, actif: bool) -> Iterator[Path]:
    """Le brut archivé, vu sous le nom d'origine du fichier quand le connecteur en a besoin
    (le nom porte l'année ou le contenu du fichier : Carte des loyers…)."""
    if not actif:
        yield brut
        return
    with tempfile.TemporaryDirectory() as dossier:
        lien = Path(dossier) / Path(fichier.nom).name
        lien.symlink_to(brut.resolve())
        yield lien


def _charger(conn, import_id, connecteur, chemin) -> tuple[int, set[tuple[str, str]]]:
    """Lit le fichier dans ingest.ligne. Renvoie le nombre de valeurs lues et les inconnus."""
    referentiel = charger_referentiel(conn)
    indicateurs = dict(
        (i["code"], i["indicateur_id"])
        for i in conn.execute("SELECT code, indicateur_id FROM ref.indicateur").fetchall()
    )
    modalites = {
        (m["dimension"], m["code"]): m["modalite_id"]
        for m in conn.execute("SELECT dimension, code, modalite_id FROM ref.modalite").fetchall()
    }
    lues, inconnus = 0, set()
    with conn.cursor().copy(
        """COPY ingest.ligne (import_id, indicateur_id, territoire_id, periode, periode_type,
                              sexe, age_min, age_max, modalite_id, valeur, statut,
                              a_publier)
           FROM STDIN"""
    ) as copie:
        for ligne in connecteur.lire(chemin, referentiel):
            lues += 1
            territoire_id = referentiel.identifiants.get((ligne.niveau, ligne.code))
            if territoire_id is None:
                inconnus.add((ligne.niveau, ligne.code))
                continue
            if ligne.indicateur not in indicateurs:
                raise FichierIllisible(f"Indicateur inconnu : {ligne.indicateur}")
            if ligne.modalite is not None and ligne.modalite not in modalites:
                raise FichierIllisible(f"Modalité inconnue : {ligne.modalite}")
            copie.write_row(
                (
                    import_id,
                    indicateurs[ligne.indicateur],
                    territoire_id,
                    ligne.periode,
                    ligne.periode_type,
                    ligne.sexe,
                    ligne.age_min,
                    ligne.age_max,
                    modalites[ligne.modalite] if ligne.modalite else None,
                    ligne.valeur,
                    ligne.statut,
                    ligne.niveau in connecteur.niveaux_publies,
                )
            )
    if lues == 0:
        raise FichierIllisible("Aucune valeur lue")
    conn.commit()
    return lues, inconnus


def _importer_poids(conn, import_id, connecteur, chemin, fichier) -> Resultat:
    """Remplace les poids communaux des dimensions et années lues dans le fichier."""
    minimum = getattr(connecteur, "communes_min", COMMUNES_MIN)
    try:
        poids: list[Poids] = list(connecteur.lire(chemin, Referentiel(identifiants={})))
    except FichierIllisible as erreur:
        return _rejeter(conn, import_id, fichier, f"Fichier illisible : {erreur}")
    erreurs = []
    vus: dict[tuple[str, int], set[str]] = {}
    for p in poids:
        communes = vus.setdefault((p.dimension, p.annee), set())
        if p.commune in communes:
            erreurs.append(f"Poids en double : {p.dimension} {p.annee} {p.commune}")
        communes.add(p.commune)
        if p.poids < 0:
            erreurs.append(f"Poids négatif : {p.dimension} {p.annee} {p.commune}")
    if not vus:
        erreurs.append("Aucun poids lu")
    for (dimension, annee), communes in sorted(vus.items()):
        if len(communes) < minimum:
            erreurs.append(f"{dimension} {annee} : {len(communes)} communes (minimum {minimum})")
    if erreurs:
        return _rejeter(conn, import_id, fichier, "\n".join(erreurs[:5]), len(poids))
    try:
        for dimension, annee in vus:
            conn.execute(
                "DELETE FROM ingest.poids_commune WHERE dimension = %s AND annee = %s",
                (dimension, annee),
            )
        with conn.cursor().copy(
            "COPY ingest.poids_commune (dimension, annee, commune, poids, import_id) FROM STDIN"
        ) as copie:
            for p in poids:
                copie.write_row((p.dimension, p.annee, p.commune, p.poids, import_id))
        _terminer(conn, import_id, "PUBLIE", None, lues=len(poids), chargees=len(poids))
    except Exception:
        conn.rollback()
        raise
    annees = ", ".join(f"{d} {a}" for d, a in sorted(vus))
    return Resultat(fichier.nom, "PUBLIE", import_id, f"{len(poids)} poids communaux ({annees})")


def _controler(conn, import_id: int, tolerance: float = TOLERANCE_SOMMES) -> list[str]:
    erreurs = []
    bilan = conn.execute(
        charger_sql(_SQL, "controle_doublons_negatifs"), {"import_id": import_id}
    ).fetchone()
    if bilan["negatifs"]:
        erreurs.append(f"{bilan['negatifs']} valeur(s) négative(s)")
    if bilan["hors_bornes"]:
        erreurs.append(f"{bilan['hors_bornes']} taux hors bornes (> 100 % ou > 1000 ‰)")
    if bilan["doublons"]:
        erreurs.append(f"{bilan['doublons']} valeur(s) en double")
    parametres = {"import_id": import_id, "tolerance": tolerance}
    for e in conn.execute(charger_sql(_SQL, "controle_sommes"), parametres).fetchall()[:5]:
        erreurs.append(
            f"{e['indicateur']} {e['code']} {e['periode']:%Y} sexe {e['sexe']} : "
            f"publié {e['publie']}, "
            f"somme des territoires {e['somme']}"
        )
    for e in conn.execute(charger_sql(_SQL, "controle_tranches"), parametres).fetchall()[:5]:
        erreurs.append(
            f"{e['indicateur']} {e['niveau']} {e['code']} {e['periode']:%Y} {e['controle']} : "
            f"total {e['publie']}, somme {e['somme']}"
        )
    hors_bornes = conn.execute(
        charger_sql(_SQL, "controle_bornes"), {"import_id": import_id}
    ).fetchall()
    for e in hors_bornes[:5]:
        erreurs.append(
            f"{e['indicateur']} {e['niveau']} {e['code']} {e['periode']:%Y-%m} : "
            f"{e['valeur']} hors des bornes [{e['borne_min']} ; {e['borne_max']}]"
        )
    return erreurs


def _controler_couverture(conn, import_id: int, absents: list[str]) -> list[str]:
    """Départements manquants à la dernière période, hors absences connues de la source."""
    manques = conn.execute(
        charger_sql(_SQL, "controle_couverture"), {"import_id": import_id, "absents": absents}
    ).fetchall()
    return [
        f"{m['indicateur']} {m['periode']:%Y-%m} : {len(m['manquants'])} département(s) "
        f"manquant(s) ({', '.join(m['manquants'][:10])})"
        for m in manques[:5]
    ]


def _terminer(conn, import_id, statut, message, lues=None, chargees=None) -> None:
    conn.execute(
        """UPDATE ingest.import
           SET statut = %s, message = %s, fin = now(),
               lignes_lues = coalesce(%s, lignes_lues), lignes_chargees = %s
           WHERE import_id = %s""",
        (statut, message, lues, chargees, import_id),
    )
    conn.commit()


def _rejeter(conn, import_id, fichier, message, lues=None) -> Resultat:
    conn.execute("DELETE FROM ingest.ligne WHERE import_id = %s", (import_id,))
    conn.execute("DELETE FROM ingest.ligne_projection WHERE import_id = %s", (import_id,))
    _terminer(conn, import_id, "REJETE", message, lues=lues)
    return Resultat(fichier.nom, "REJETE", import_id, message)


def publier(conn: psycopg.Connection, import_id: int) -> int:
    """Écrit les lignes préparées dans stat.observation, en une transaction."""
    try:
        chargees = conn.execute(charger_sql(_SQL, "publier"), {"import_id": import_id}).rowcount
        conn.execute("DELETE FROM ingest.ligne WHERE import_id = %s", (import_id,))
        _terminer(conn, import_id, "PUBLIE", None, chargees=chargees)
    except Exception:
        conn.rollback()
        raise
    conn.execute("SELECT stat.rafraichir_vues()")
    conn.commit()
    return chargees


def valider(conn: psycopg.Connection, import_id: int) -> int:
    """Publie un import EN_ATTENTE après vérification humaine."""
    ligne = conn.execute(
        "SELECT statut FROM ingest.import WHERE import_id = %s FOR UPDATE", (import_id,)
    ).fetchone()
    if ligne is None:
        raise ImportImpossible(f"Import n° {import_id} inconnu")
    if ligne["statut"] != "EN_ATTENTE":
        raise ImportImpossible(f"Import n° {import_id} : statut {ligne['statut']}, rien à valider")
    if conn.execute(
        "SELECT 1 FROM ingest.ligne_projection WHERE import_id = %s LIMIT 1", (import_id,)
    ).fetchone():
        return projections.publier(conn, import_id)
    return publier(conn, import_id)


def journal(conn: psycopg.Connection, nombre: int = 20) -> list[dict]:
    """Derniers imports, du plus récent au plus ancien."""
    return conn.execute(
        """SELECT i.import_id, s.code AS source, i.fichier_nom, i.statut, i.debut, i.fin,
                  i.lignes_lues, i.lignes_chargees, i.message
           FROM ingest.import i JOIN ref.source s USING (source_id)
           ORDER BY i.import_id DESC LIMIT %s""",
        (nombre,),
    ).fetchall()
