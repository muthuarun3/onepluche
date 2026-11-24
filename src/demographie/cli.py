"""Commandes d'administration : demo <commande>."""

import argparse
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from demographie import alertes, config, db, migrations
from demographie.catalogue.references import REFERENCES_INSEE
from demographie.donnees import series
from demographie.imports import pipeline, veille_programmes
from demographie.imports.connecteurs import CONNECTEURS
from demographie.imports.modele import Fichier


def _migrer(_args: argparse.Namespace) -> int:
    with db.connexion("proprietaire") as conn:
        appliquees = migrations.appliquer(conn)
    if appliquees:
        print("Migrations appliquées :")
        for nom in appliquees:
            print(f"  {nom}")
    else:
        print("Base à jour, aucune migration à appliquer.")
    return 0


def _etat(_args: argparse.Namespace) -> int:
    with db.connexion("proprietaire") as conn:
        derniere = conn.execute(
            "SELECT nom, appliquee_le FROM admin.migration ORDER BY nom DESC LIMIT 1"
        ).fetchone()
        comptes = conn.execute(
            "SELECT niveau, count(*) AS n FROM ref.territoire GROUP BY niveau ORDER BY niveau"
        ).fetchall()
    print(f"Dernière migration : {derniere['nom']} ({derniere['appliquee_le']:%Y-%m-%d %H:%M})")
    for ligne in comptes:
        print(f"Territoires {ligne['niveau']} : {ligne['n']}")
    return 0


def _importer(args: argparse.Namespace) -> int:
    """Importe une source, ou toutes (« tout ») ; une source en échec n'arrête pas les autres."""
    configuration = config.charger()
    alertes.signaler(configuration.ping_import, "debut")
    journal: list[str] = []

    def dire(texte: str) -> None:
        print(texte, flush=True)
        journal.append(texte)

    code_retour = _importer_sources(args, configuration, dire)
    etat = "succes" if code_retour == 0 else "echec"
    alertes.signaler(configuration.ping_import, etat, "\n".join(journal))
    return code_retour


def _importer_sources(args: argparse.Namespace, configuration: config.Config, dire) -> int:
    noms = list(CONNECTEURS) if args.source == "tout" else [args.source]
    connecteurs = [c for nom in noms for c in CONNECTEURS[nom]]
    dossier_brut = configuration.donnees_brutes
    code_retour = 0
    travaux: list[tuple] = []
    if args.fichier:
        for chemin in map(Path, args.fichier):
            retenus = [c for c in connecteurs if c.accepte(chemin.name)]
            if not retenus:
                dire(f"{chemin.name} : nom de fichier non reconnu pour « {args.source} »")
                return 2
            fichier = Fichier(url=chemin.resolve().as_uri(), nom=chemin.name)
            travaux.append((retenus[0], fichier, chemin))
    else:
        for connecteur in connecteurs:
            try:
                travaux += [(connecteur, f, None) for f in connecteur.fichiers()]
            except Exception as erreur:  # réseau, page modifiée… : on signale et on continue
                dire(f"{connecteur.source} : fichiers introuvables ({erreur})")
                code_retour = 1
    with db.connexion("import") as conn:
        for connecteur, fichier, chemin in travaux:
            dire(f"{fichier.nom} …")
            try:
                resultat = pipeline.importer(
                    conn, connecteur, fichier, dossier_brut, chemin, args.seuil / 100
                )
            except Exception as erreur:
                conn.rollback()
                dire(f"  ÉCHEC {type(erreur).__name__} : {erreur}")
                code_retour = 1
                continue
            dire(f"  {resultat.statut} (import n° {resultat.import_id}) {resultat.message}")
            if resultat.statut in ("REJETE", "EN_ATTENTE"):
                code_retour = 1
    return code_retour


def _imports(_args: argparse.Namespace) -> int:
    with db.connexion("import") as conn:
        for i in pipeline.journal(conn):
            print(
                f"{i['import_id']:>4}  {i['debut']:%Y-%m-%d %H:%M}  {i['statut']:<10}  "
                f"{i['source']:<10}  {i['fichier_nom']}"
            )
            if i["message"] and i["statut"] != "PUBLIE":
                print("      " + i["message"].replace("\n", "\n      "))
    return 0


def _valider(args: argparse.Namespace) -> int:
    with db.connexion("import") as conn:
        chargees = pipeline.valider(conn, args.import_id)
    print(f"Import n° {args.import_id} publié : {chargees} valeurs.")
    return 0


def _arrondi(valeur: Decimal | None) -> Decimal | None:
    return None if valeur is None else valeur.quantize(Decimal("0.1"), ROUND_HALF_UP)


def _verifier(_args: argparse.Namespace) -> int:
    """Compare les chiffres servis par l'application aux valeurs publiées par l'INSEE."""
    ecarts = 0
    with db.connexion("lecture") as conn:
        for ref in REFERENCES_INSEE:
            valeurs = {}
            for indicateur in ("POP", "PART_60_PLUS"):
                serie = series.serie(conn, indicateur, ref.niveau, ref.code, ref.annee, ref.annee)
                valeurs[indicateur] = serie[0]["valeur"] if serie else None
            population, part = valeurs["POP"], _arrondi(valeurs["PART_60_PLUS"])
            attendu = Decimal(str(ref.part_60_plus))
            ok = population == ref.population and part == attendu
            ecarts += not ok
            print(
                f"{'OK ' if ok else 'ÉCART'}  {ref.libelle:<22} {ref.annee}  "
                f"population {population} (INSEE {ref.population})  "
                f"60 ans et plus {part} % (INSEE {attendu} %)"
            )
    return 1 if ecarts else 0


def _veiller(args: argparse.Namespace) -> int:
    """Relève les programmes suivis ; alerte (battement en échec) si un texte a changé ou
    n'a pas pu être téléchargé, pour qu'une fiche soit mise à jour par PR."""
    configuration = config.charger()
    alertes.signaler(configuration.ping_programmes, "debut")
    dossier = configuration.programmes / args.election
    with db.connexion("import") as conn:
        releves = veille_programmes.veiller(
            conn, dossier, configuration.donnees_brutes / "programmes"
        )
    lignes = [r.ligne() for r in releves] or ["Aucun programme suivi pour l'instant."]
    for ligne in lignes:
        print(ligne, flush=True)
    a_voir = [r for r in releves if r.change or r.en_erreur]
    etat = "echec" if a_voir else "succes"
    alertes.signaler(configuration.ping_programmes, etat, "\n".join(lignes))
    return 1 if any(r.en_erreur for r in releves) else 0


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="demo", description="Administration de Démographie")
    sous = parseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("migrer", help="appliquer les migrations SQL manquantes").set_defaults(
        action=_migrer
    )
    sous.add_parser("etat", help="afficher l'état de la base").set_defaults(action=_etat)
    imp = sous.add_parser("importer", help="importer les derniers fichiers d'une source")
    imp.add_argument("source", choices=[*CONNECTEURS, "tout"])
    imp.add_argument("--fichier", action="append", help="fichier local déjà téléchargé (répétable)")
    imp.add_argument(
        "--seuil",
        type=float,
        default=pipeline.SEUIL_VARIATION * 100,
        help="variation (en %%) au-delà de laquelle une validation est demandée",
    )
    imp.set_defaults(action=_importer)
    sous.add_parser("imports", help="journal des derniers imports").set_defaults(action=_imports)
    val = sous.add_parser("valider", help="publier un import en attente de validation")
    val.add_argument("import_id", type=int)
    val.set_defaults(action=_valider)
    sous.add_parser(
        "verifier", help="comparer les chiffres servis aux valeurs publiées par l'INSEE"
    ).set_defaults(action=_verifier)
    vei = sous.add_parser("veiller", help="relever les programmes présidentiels suivis")
    vei.add_argument("quoi", choices=["programmes"])
    vei.add_argument("--election", default="2027", help="dossier programmes/<élection>")
    vei.set_defaults(action=_veiller)
    args = parseur.parse_args(argv)
    return args.action(args)


if __name__ == "__main__":
    sys.exit(main())
