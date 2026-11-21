"""Appli 2, phase A : catalogue étendu, lecture de fichiers, agrégation communale, contrôles."""

import gzip
import zipfile
from datetime import date
from decimal import Decimal

import openpyxl
import psycopg
import pytest

from demographie import config, db
from demographie.imports import pipeline
from demographie.imports.connecteurs import communes, fichier
from demographie.imports.modele import Fichier, FichierIllisible, Ligne, Referentiel

# --- Agrégation commune -> département -------------------------------------------------


@pytest.mark.parametrize(
    ("commune", "departement"),
    [
        ("23096", "23"),
        ("2A004", "2A"),
        ("2B033", "2B"),
        ("97101", "971"),
        ("97611", "976"),
        ("75112", "75"),
        ("69381", "69"),
        ("13201", "13"),
        ("1001", "01"),
    ],
)
def test_departement_de(commune, departement):
    assert communes.departement_de(commune) == departement


def test_sommer():
    resultat = communes.sommer([("23096", Decimal(10)), ("23001", Decimal(5)), ("75112", 7)])
    assert resultat["23"] == communes.Agregat(Decimal(15), 2)
    assert resultat["75"].valeur == 7


def test_moyenne_ponderee():
    poids = {"23096": Decimal(3), "23001": Decimal(1)}
    resultat = communes.moyenne_ponderee(
        [("23096", Decimal(10)), ("23001", Decimal(6)), ("23002", Decimal(100))], poids
    )
    # (10 × 3 + 6 × 1) / 4 ; la commune sans poids est ignorée mais comptée.
    assert resultat["23"] == communes.Agregat(Decimal(9), 2, 1)


def test_moyenne_ponderee_sans_poids_refusee():
    with pytest.raises(FichierIllisible, match="Poids communaux absents"):
        communes.moyenne_ponderee([("23096", Decimal(1))], {})


def test_poids_de_l_annee_la_plus_recente():
    referentiel = Referentiel(
        identifiants={},
        poids_communes={
            ("RP_LOUEES", 2017): {"23096": Decimal(1)},
            ("RP_LOUEES", 2023): {"23096": Decimal(2)},
            ("POPULATION", 2023): {"23096": Decimal(9)},
        },
    )
    assert referentiel.poids("RP_LOUEES") == {"23096": Decimal(2)}
    assert referentiel.poids("RP_LOUEES", 2020) == {"23096": Decimal(1)}
    assert referentiel.poids("RP_LOUEES", 2010) == {}
    assert referentiel.poids("INCONNUE") == {}


# --- Lecture de fichiers ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("9,7576", Decimal("9.7576")),
        ("1 234,5", Decimal("1234.5")),
        ("12 000", Decimal(12000)),
        ("", None),
        ("s", None),
        (None, None),
        (3, Decimal(3)),
        (2.5, Decimal("2.5")),
    ],
)
def test_nombre(texte, attendu):
    assert fichier.nombre(texte) == attendu


def test_nombre_illisible():
    with pytest.raises(FichierIllisible):
        fichier.nombre("douze")


CSV_LOYERS = '"INSEE_C";"LIBGEO";"DEP";"loypredm2"\n"23096";"Guéret";"23";9,75\n'


def test_lire_csv_latin1(tmp_path):
    chemin = tmp_path / "loyers.csv"
    chemin.write_bytes(CSV_LOYERS.encode("latin-1"))
    fmt = fichier.FormatCSV(encodage="latin-1")
    lignes = list(fichier.lire_csv(chemin, fmt, frozenset({"INSEE_C", "loypredm2"})))
    assert lignes == [{"INSEE_C": "23096", "LIBGEO": "Guéret", "DEP": "23", "loypredm2": "9,75"}]


def test_lire_csv_colonne_absente(tmp_path):
    chemin = tmp_path / "loyers.csv"
    chemin.write_text(CSV_LOYERS, encoding="utf-8")
    with pytest.raises(FichierIllisible, match="Colonnes absentes : nbobs"):
        list(fichier.lire_csv(chemin, fichier.FormatCSV(), frozenset({"nbobs"})))


def test_lire_csv_gz_et_zip(tmp_path):
    texte = "code_departement,valeur\n23,1.5\n"
    gz = tmp_path / "f.csv.gz"
    gz.write_bytes(gzip.compress(texte.encode()))
    archive = tmp_path / "f.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("lisez-moi.txt", "rien")
        z.writestr("donnees/f.csv", texte)
    fmt = fichier.FormatCSV(separateur=",", decimale=".")
    attendu = [{"code_departement": "23", "valeur": "1.5"}]
    assert list(fichier.lire_csv(gz, fmt)) == attendu
    assert list(fichier.lire_csv(archive, fmt)) == attendu


def test_lire_xlsx(tmp_path):
    classeur = openpyxl.Workbook()
    onglet = classeur.active
    onglet.title = "APL"
    onglet.append(["Accessibilité aux médecins généralistes"])
    onglet.append(["Code commune", "APL", "Population"])
    onglet.append(["23096", 3.1, 12500])
    onglet.append([None, None, None])
    chemin = tmp_path / "apl.xlsx"
    classeur.save(chemin)
    lignes = list(fichier.lire_xlsx(chemin, "APL", 2, frozenset({"Code commune", "APL"})))
    assert lignes == [{"Code commune": "23096", "APL": 3.1, "Population": 12500}]
    with pytest.raises(FichierIllisible, match="Feuille absente"):
        list(fichier.lire_xlsx(chemin, "Autre", 2))


# --- Catalogue et contrôles du pipeline -------------------------------------------------


def test_catalogue_etendu(base_test):
    with psycopg.connect(base_test["proprietaire"]) as conn:
        # Les indicateurs de l'appli 1 restent dans la rubrique QUI, sans thème ni angle.
        qui = conn.execute(
            "SELECT DISTINCT theme, angle FROM ref.indicateur WHERE rubrique = 'QUI'"
        ).fetchall()
        assert qui == [(None, None)]
        assert conn.execute(
            "SELECT rubrique FROM ref.indicateur WHERE code = 'POP'"
        ).fetchone() == ("QUI",)
        colonnes = {
            r[0]
            for r in conn.execute(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema = 'api' AND table_name = 'indicateur'"""
            ).fetchall()
        }
        assert {"rubrique", "theme", "angle", "borne_min", "borne_max"} <= colonnes
        # Un indicateur « besoins » sans thème est refusé par la base.
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """INSERT INTO ref.indicateur
                     (code, libelle, definition, unite, nature, source_id, rubrique)
                   SELECT 'SANS_THEME', 'x', 'x', 'euros_m2', 'prix', source_id, 'BESOINS'
                   FROM ref.source WHERE code = 'INSEE_RP'"""
            )


class _PrixParDepartement:
    """Connecteur de test : un prix par département, lu dans un CSV « dep;valeur »."""

    source = "INSEE_RP"
    niveaux_publies = frozenset({"DEP"})
    controle_couverture = True
    departements_absents = frozenset({"976"})

    def fichiers(self):
        return []

    def accepte(self, nom_fichier):
        return True

    def lire(self, chemin, referentiel):
        for ligne in fichier.lire_csv(chemin, fichier.FormatCSV()):
            yield Ligne(
                indicateur="PRIX_TEST",
                niveau="DEP",
                code=ligne["dep"],
                periode=date(2025, 1, 1),
                periode_type="ANNEE",
                sexe="T",
                age_min=None,
                age_max=None,
                valeur=fichier.nombre(ligne["valeur"]),
                statut="DEFINITIF",
            )


@pytest.fixture
def prix_test(urls_module):
    with psycopg.connect(urls_module["proprietaire"]) as conn:
        conn.execute(
            """INSERT INTO ref.indicateur
                 (code, libelle, definition, unite, nature, source_id, rubrique, theme, angle,
                  borne_min, borne_max, seuil_variation)
               SELECT 'PRIX_TEST', 'Prix test', 'Prix test', 'euros_m2', 'prix', source_id,
                      'BESOINS', 'LOGEMENT', 'COUT', 3, 60, 0.15
               FROM ref.source WHERE code = 'INSEE_RP'
               ON CONFLICT (code) DO NOTHING"""
        )
        departements = [
            r[0]
            for r in conn.execute(
                "SELECT code FROM ref.territoire WHERE niveau = 'DEP' ORDER BY code"
            ).fetchall()
        ]
    return departements


def _importer_prix(tmp_path, nom, valeurs: dict[str, str]):
    chemin = tmp_path / nom
    lignes = "".join(f"{dep};{v}\n" for dep, v in valeurs.items())
    chemin.write_text("dep;valeur\n" + lignes, encoding="utf-8")
    with db.connexion("import") as conn:
        return pipeline.importer(
            conn,
            _PrixParDepartement(),
            Fichier(url=chemin.resolve().as_uri(), nom=nom),
            config.charger().donnees_brutes,
            chemin_local=chemin,
        )


def _tous(departements, valeur="10,0", **exceptions):
    return {d: exceptions.get(f"d{d}", valeur) for d in departements if d != "976"}


def test_valeur_hors_bornes_rejetee(prix_test, tmp_path):
    resultat = _importer_prix(tmp_path, "bornes.csv", _tous(prix_test, d23="95,0"))
    assert resultat.statut == "REJETE"
    assert "PRIX_TEST DEP 23 2025-01 : 95.0 hors des bornes [3 ; 60]" in resultat.message


def test_departement_manquant_rejete(prix_test, tmp_path):
    valeurs = _tous(prix_test)
    del valeurs["23"]
    resultat = _importer_prix(tmp_path, "couverture.csv", valeurs)
    assert resultat.statut == "REJETE"
    assert "1 département(s) manquant(s) (23)" in resultat.message


def test_seuil_de_variation_propre_aux_prix(prix_test, tmp_path):
    # Mayotte est déclarée absente de la source : sa place vide ne bloque pas l'import.
    assert _importer_prix(tmp_path, "v1.csv", _tous(prix_test)).statut == "PUBLIE"
    # +10 % : sous le seuil de 15 % de l'indicateur, publié sans validation.
    assert _importer_prix(tmp_path, "v2.csv", _tous(prix_test, "11,0")).statut == "PUBLIE"
    # +20 % sur un département : l'import attend une validation.
    resultat = _importer_prix(tmp_path, "v3.csv", _tous(prix_test, "11,0", d23="13,2"))
    assert resultat.statut == "EN_ATTENTE"
    assert "DEP 23 2025 : 11.0 → 13.2" in resultat.message
