from fastapi.testclient import TestClient

from demographie.app import app

client = TestClient(app)


def test_sante_sans_base():
    reponse = client.get("/sante")
    assert reponse.status_code == 200
    assert reponse.json()["statut"] == "ok"
    assert reponse.headers["X-Content-Type-Options"] == "nosniff"


def test_documentation_openapi():
    reponse = client.get("/api/openapi.json")
    assert reponse.status_code == 200
    assert "/api/v1/territoires" in reponse.json()["paths"]


def test_territoires(urls_db):
    reponse = client.get("/api/v1/territoires")
    assert reponse.status_code == 200
    donnees = reponse.json()
    assert len(donnees) == 123  # dont 2 territoires hors département (VOTES)
    assert donnees[0]["code"] == "FR"


def test_territoires_filtre_par_niveau(urls_db):
    deps = client.get("/api/v1/territoires", params={"niveau": "DEP"}).json()
    assert len(deps) == 101
    paris = next(d for d in deps if d["code"] == "75")
    assert paris["libelle"] == "Paris"
    assert (paris["parent_niveau"], paris["parent_code"]) == ("REG", "11")


def test_niveau_invalide_refuse(urls_db):
    reponse = client.get("/api/v1/territoires", params={"niveau": "COMMUNE"})
    assert reponse.status_code == 422
