"""Import des projections (population, climat…) : lecture, contrôles, publication dans
stat.projection. Même journal (ingest.import), même archivage et mêmes statuts que les
observations (voir pipeline.py), avec des contrôles propres aux projections :

- doublons, valeurs hors des bornes du catalogue, fourchette bas ≤ médiane ≤ haut ;
- couverture : au moins `departements_attendus` départements par indicateur et scénario ;
- point de départ : la population de la première année projetée est à moins de 1 % des
  estimations INSEE déjà publiées (si elles le sont) ;
- variation : une nouvelle édition qui change un total publié de plus du seuil attend
  « demo valider ».
Publier remplace toute la projection d'un indicateur dans chaque scénario du fichier.
"""

from pathlib import Path

import psycopg

from demographie.db import charger_sql
from demographie.imports.modele import Connecteur, Fichier, FichierIllisible, Projection

_SQL = Path(__file__).parent / "sql"
TOLERANCE_DEPART = 0.01


def importer(
    conn: psycopg.Connection,
    import_id: int,
    connecteur: Connecteur,
    chemin: Path,
    fichier: Fichier,
    seuil_variation: float,
):
    # Import différé : pipeline importe ce module.
    from demographie.imports import pipeline

    try:
        lues, inconnus = _charger(conn, import_id, connecteur, chemin)
    except FichierIllisible as erreur:
        conn.rollback()
        return pipeline._rejeter(conn, import_id, fichier, f"Fichier illisible : {erreur}")
    if inconnus:
        liste = ", ".join(sorted(inconnus)[:10])
        return pipeline._rejeter(conn, import_id, fichier, f"Inconnus : {liste}", lues)

    erreurs = _controler(conn, import_id, getattr(connecteur, "departements_attendus", 0))
    if erreurs:
        return pipeline._rejeter(conn, import_id, fichier, "\n".join(erreurs), lues)

    variations = conn.execute(
        charger_sql(_SQL, "controle_projection_variations"),
        {"import_id": import_id, "seuil": seuil_variation},
    ).fetchall()
    if variations:
        detail = "; ".join(
            f"{v['niveau']} {v['code']} {v['scenario']} {v['periode']:%Y} : "
            f"{v['ancienne']} → {v['nouvelle']}"
            for v in variations[:5]
        )
        message = (
            f"Variation de plus de {seuil_variation:.0%} sur des projections publiées : {detail}"
        )
        pipeline._terminer(conn, import_id, "EN_ATTENTE", message, lues=lues)
        return pipeline.Resultat(fichier.nom, "EN_ATTENTE", import_id, message)

    chargees = publier(conn, import_id)
    return pipeline.Resultat(fichier.nom, "PUBLIE", import_id, f"{chargees} valeurs publiées")


def _charger(conn, import_id, connecteur, chemin) -> tuple[int, set[str]]:
    from demographie.imports.pipeline import charger_referentiel

    referentiel = charger_referentiel(conn)
    indicateurs = {
        i["code"]: i["indicateur_id"]
        for i in conn.execute("SELECT code, indicateur_id FROM ref.indicateur").fetchall()
    }
    scenarios = {
        s["code"]: s["scenario_id"]
        for s in conn.execute("SELECT code, scenario_id FROM ref.scenario").fetchall()
    }
    lues, inconnus = 0, set()
    with conn.cursor().copy(
        """COPY ingest.ligne_projection (import_id, indicateur_id, territoire_id, scenario_id,
                                         periode, periode_fin, sexe, age_min, age_max,
                                         statistique, valeur)
           FROM STDIN"""
    ) as copie:
        for p in connecteur.lire(chemin, referentiel):
            if not isinstance(p, Projection):
                raise FichierIllisible(f"Valeur inattendue : {p!r}")
            lues += 1
            territoire_id = referentiel.identifiants.get((p.niveau, p.code))
            if territoire_id is None:
                inconnus.add(f"territoire {p.niveau}/{p.code}")
                continue
            if p.scenario not in scenarios:
                inconnus.add(f"scénario {p.scenario}")
                continue
            if p.indicateur not in indicateurs:
                raise FichierIllisible(f"Indicateur inconnu : {p.indicateur}")
            copie.write_row(
                (
                    import_id,
                    indicateurs[p.indicateur],
                    territoire_id,
                    scenarios[p.scenario],
                    p.periode,
                    p.periode_fin,
                    p.sexe,
                    p.age_min,
                    p.age_max,
                    p.statistique,
                    p.valeur,
                )
            )
    if lues == 0:
        raise FichierIllisible("Aucune valeur lue")
    conn.commit()
    return lues, inconnus


def _controler(conn, import_id: int, departements_attendus: int) -> list[str]:
    erreurs = []
    parametres = {"import_id": import_id}
    bilan = conn.execute(charger_sql(_SQL, "controle_projection"), parametres).fetchone()
    if bilan["doublons"]:
        erreurs.append(f"{bilan['doublons']} valeur(s) en double")
    if bilan["hors_bornes"]:
        erreurs.append(f"{bilan['hors_bornes']} valeur(s) hors des bornes du catalogue")
    if bilan["fourchettes"]:
        erreurs.append(f"{bilan['fourchettes']} fourchette(s) incohérente(s) (bas, médiane, haut)")
    if departements_attendus:
        manques = conn.execute(
            charger_sql(_SQL, "controle_projection_couverture"),
            {**parametres, "attendus": departements_attendus},
        ).fetchall()
        erreurs += [
            f"{m['indicateur']} {m['scenario']} : {m['departements']} département(s) "
            f"sur {departements_attendus} attendus"
            for m in manques[:5]
        ]
    ecarts = conn.execute(
        charger_sql(_SQL, "controle_projection_depart"),
        {**parametres, "tolerance": TOLERANCE_DEPART},
    ).fetchall()
    erreurs += [
        f"{e['niveau']} {e['code']} {e['periode']:%Y} : projection {e['projection']}, "
        f"estimation INSEE {e['estimation']} (écart de plus de {TOLERANCE_DEPART:.0%})"
        for e in ecarts[:5]
    ]
    return erreurs


def publier(conn: psycopg.Connection, import_id: int) -> int:
    """Remplace dans stat.projection les indicateurs et scénarios de l'import."""
    from demographie.imports.pipeline import _terminer

    try:
        conn.execute(charger_sql(_SQL, "remplacer_projection"), {"import_id": import_id})
        chargees = conn.execute(
            charger_sql(_SQL, "publier_projection"), {"import_id": import_id}
        ).rowcount
        conn.execute("DELETE FROM ingest.ligne_projection WHERE import_id = %s", (import_id,))
        _terminer(conn, import_id, "PUBLIE", None, chargees=chargees)
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return chargees
