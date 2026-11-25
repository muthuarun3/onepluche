"""Fiches des programmes : la grille réelle, les fiches réelles et les règles de l'étape 5."""

import re
import shutil
from pathlib import Path

import pytest

from demographie.donnees import programmes

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_2027 = RACINE / "programmes" / "2027"
FIXTURES = Path(__file__).parent / "fixtures" / "programmes"
MIGRATIONS = RACINE / "sql" / "migrations"


@pytest.fixture
def dossier(tmp_path: Path) -> Path:
    """La vraie grille 2027 et les deux fiches fictives."""
    shutil.copy(DOSSIER_2027 / "sujets.toml", tmp_path)
    for fiche in FIXTURES.glob("*.toml"):
        shutil.copy(fiche, tmp_path)
    return tmp_path


def _codes_indicateurs_connus() -> set[str]:
    texte = "\n".join(p.read_text(encoding="utf-8") for p in MIGRATIONS.glob("*.sql"))
    return set(re.findall(r"'([A-Z][A-Z0-9_]+)'", texte))


def test_le_depot_se_lit_sans_erreur():
    lus = programmes.charger(DOSSIER_2027)
    assert len(lus.grille.sujets) == 12
    assert lus.grille.election.premier_tour.isoformat() == "2027-04-18"
    assert {e.code for e in lus.grille.echelles} >= {"AGE_LEGAL_RETRAITE", "TVA_TAUX_NORMAL"}


def test_indicateurs_cites_existent_dans_donnees():
    lus = programmes.charger(DOSSIER_2027)
    cites = {c for s in lus.grille.sujets for c in s.indicateurs}
    cites |= {c for f in lus.fiches for m in f.mesures for c in m.indicateurs}
    inconnus = cites - _codes_indicateurs_connus()
    assert not inconnus, f"codes d'indicateurs absents des migrations : {sorted(inconnus)}"


def test_fiches_fictives(dossier):
    lus = programmes.charger(dossier)
    assert [f.candidat.nom_complet for f in lus.candidats] == ["Camille Alpha", "Dominique Bravo"]
    alpha = lus.fiche("alpha-camille")
    assert alpha.derniere_version.id == "v2"
    assert [m.id for m in alpha.mesures_en_vigueur] == ["retraites-age-legal", "sante-centres"]
    assert alpha.mesures[0].chiffrages[0].montant == 7_000_000_000


def test_comparer_deduit_pas_de_proposition(dossier):
    lus = programmes.charger(dossier)
    retraites = {
        f.candidat.id: [m.echelle.valeur for m in ms] for f, ms in lus.comparer("retraites")
    }
    assert retraites == {"alpha-camille": [63], "bravo-dominique": [65]}
    # La mesure logement d'Alpha a été retirée dans la v2 : plus personne n'en propose.
    assert all(not ms for _, ms in lus.comparer("logement"))
    with pytest.raises(KeyError):
        lus.comparer("sujet-inconnu")


def test_ordre_officiel_puis_retires(dossier):
    alpha = dossier / "alpha-camille.toml"
    bravo = dossier / "bravo-dominique.toml"
    alpha.write_text(alpha.read_text().replace('statut = "declare"', 'statut = "retire"'))
    bravo.write_text(
        bravo.read_text().replace('statut = "declare"', 'statut = "officiel"\nordre_officiel = 1')
    )
    lus = programmes.charger(dossier)
    assert [f.candidat.id for f in lus.candidats] == ["bravo-dominique", "alpha-camille"]
    # Un candidat retiré sort de la comparaison mais garde sa fiche.
    assert [f.candidat.id for f, _ in lus.comparer("retraites")] == ["bravo-dominique"]
    assert lus.fiche("alpha-camille") is not None


@pytest.mark.parametrize(
    ("avant", "apres", "message"),
    [
        ('sujet = "sante"', 'sujet = "loisirs"', "sujet inconnu"),
        ('version = "v2"\nancre', 'version = "v9"\nancre', "version inconnue"),
        ('ancre = "#sante"', "", "page ou ancre obligatoire"),
        ('retiree_dans = "v2"', 'retiree_dans = "v1"', "retirée avant"),
        ("Un centre de santé par canton", "Un centre de santé ambitieux par canton", "jugement"),
        ('code = "LOGEMENTS_CONSTRUITS_AN"', 'code = "AGE_LEGAL_RETRAITE"', "hors du sujet"),
        ('id = "alpha-camille"', 'id = "autre-nom"', "l'id du candidat"),
        ('statut = "declare"', 'statut = "favori"', "statut"),
        ("[[versions]]", "[[version]]", "version"),
    ],
)
def test_fiche_cassee_refusee(dossier, avant, apres, message):
    alpha = dossier / "alpha-camille.toml"
    texte = alpha.read_text()
    assert avant in texte
    alpha.write_text(texte.replace(avant, apres, 1))
    with pytest.raises(programmes.FicheInvalide, match="alpha-camille.toml") as erreur:
        programmes.charger(dossier)
    assert message in str(erreur.value)


def test_citation_trop_longue_refusee(dossier):
    alpha = dossier / "alpha-camille.toml"
    longue = "mot " * 120
    alpha.write_text(alpha.read_text().replace("Chaque canton aura son centre de santé.", longue))
    with pytest.raises(programmes.FicheInvalide, match="400"):
        programmes.charger(dossier)


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("Âge légal de départ fixé à 63 ans", []),
        ("Une réforme IRRÉALISTE et démagogique", ["demagogique", "irrealiste"]),
        ("Des mesures radicales", ["radicale"]),
        ("Un phare dans la nuit", ["phare"]),
    ],
)
def test_mots_de_jugement(texte, attendu):
    assert programmes.mots_de_jugement(texte) == attendu


def test_suivis_du_depot_designent_des_fiches():
    """Chaque adresse suivie est celle d'une version publiée d'une fiche du dépôt."""
    from demographie.imports import veille_programmes

    lus = programmes.charger(DOSSIER_2027)
    versions = {(f.candidat.id, v.id): v.url for f in lus.fiches for v in f.versions}
    for suivi in veille_programmes.lire_suivis(DOSSIER_2027):
        assert versions.get((suivi.candidat, suivi.version)) == suivi.url, suivi
