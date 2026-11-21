"""Carte de choix du territoire : métropole sur la carte, outre-mer en boutons."""

from demographie.web.carte import choix_territoire, contours

TERRITOIRES = [
    {"niveau": "FRANCE", "code": "FR", "libelle": "France"},
    {"niveau": "REG", "code": "75", "libelle": "Nouvelle-Aquitaine"},
    {"niveau": "REG", "code": "04", "libelle": "La Réunion"},
    {"niveau": "DEP", "code": "23", "libelle": "Creuse"},
    {"niveau": "DEP", "code": "75", "libelle": "Paris"},
    {"niveau": "DEP", "code": "2A", "libelle": "Corse-du-Sud"},
    {"niveau": "DEP", "code": "974", "libelle": "La Réunion"},
]


def test_contours_de_la_metropole():
    traces = contours()
    assert len(traces["DEP"]) == 96 and len(traces["REG"]) == 13
    assert "2A" in traces["DEP"] and "971" not in traces["DEP"]
    assert set(traces["encart"]["territoires"]) == {"75", "92", "93", "94"}
    assert all(t["d"].startswith("M") for t in traces["DEP"].values())


def test_outre_mer_hors_carte():
    choix = choix_territoire(TERRITOIRES, ("REG", "DEP"), "/territoire/{niveau}/{code}")
    reg, dep = choix["vues"]
    assert [t["code"] for t in reg["sur_carte"]] == ["75"]
    assert reg["outre_mer"] == [
        {"code": "04", "libelle": "La Réunion", "lien": "/territoire/REG/04"}
    ]
    assert reg["encart"] == []
    assert [t["code"] for t in dep["sur_carte"]] == ["23", "75", "2A"]
    assert [t["lien"] for t in dep["outre_mer"]] == ["/territoire/DEP/974"]
    assert [t["code"] for t in dep["encart"]] == ["75"]


def test_lien_d_une_autre_rubrique():
    choix = choix_territoire(TERRITOIRES, ("DEP",), "/besoins/DEP/{code}")
    assert choix["vues"][0]["sur_carte"][0]["lien"] == "/besoins/DEP/23"
