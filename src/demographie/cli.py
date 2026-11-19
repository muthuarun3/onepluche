"""Commandes d'administration : demo <commande>."""

import argparse
import sys

from demographie import db, migrations


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


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="demo", description="Administration de Démographie")
    sous = parseur.add_subparsers(dest="commande", required=True)
    sous.add_parser("migrer", help="appliquer les migrations SQL manquantes").set_defaults(
        action=_migrer
    )
    sous.add_parser("etat", help="afficher l'état de la base").set_defaults(action=_etat)
    args = parseur.parse_args(argv)
    return args.action(args)


if __name__ == "__main__":
    sys.exit(main())
