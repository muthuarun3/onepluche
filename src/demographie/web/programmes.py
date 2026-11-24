"""Pages de la macro-catégorie « Programmes » : candidats, fiche d'un candidat, comparaison.

Dossier de conception, étape 8 : une seule couleur, des citations sourcées, aucun
classement ni note. Les fiches viennent de `programmes/<élection>/` (donnees.programmes).
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi import Path as Chemin
from fastapi.responses import HTMLResponse

from demographie.donnees import programmes
from demographie.web.pages import Connexion, _decimal_fr, gabarits
from demographie.web.securite import chiffre

routeur = APIRouter(include_in_schema=False)

STATUTS = {
    "declare": "Candidature déclarée",
    "officiel": "Candidature officielle",
    "non_retenu": "Candidature non retenue",
    "retire": "Candidature retirée",
}
MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def date_fr(jour) -> str:
    """2026-11-20 -> « 20 novembre 2026 »."""
    premier = "1er" if jour.day == 1 else str(jour.day)
    return f"{premier} {MOIS[jour.month - 1]} {jour.year}"


def montant(valeur: float, unite: str) -> str:
    """12e9, EUR_PAR_AN -> « 12 milliards d'euros par an »."""
    v = abs(valeur)
    if v >= 1e9:
        texte = f"{_decimal_fr(valeur / 1e9, 0 if valeur % 1e9 == 0 else 1)} milliards d'euros"
    elif v >= 1e6:
        texte = f"{_decimal_fr(valeur / 1e6, 0 if valeur % 1e6 == 0 else 1)} millions d'euros"
    else:
        texte = f"{_decimal_fr(valeur, 0)} euros"
    return texte + (" par an" if unite == "EUR_PAR_AN" else "")


def valeur_echelle(valeur: float, unite: str) -> str:
    entier = valeur == int(valeur)
    nombre = _decimal_fr(valeur, 0 if entier else 1)
    return f"{nombre} %" if unite == "%" else f"{nombre} {unite}"


gabarits.env.filters.update(date_fr=date_fr, montant=montant, valeur_echelle=valeur_echelle)
gabarits.env.globals["statuts_candidature"] = STATUTS


def _election() -> programmes.Programmes:
    return programmes.election()


def _contexte(conn, codes: set[str]) -> dict[str, dict]:
    lignes = programmes.contexte_france(conn, sorted(codes))
    for ligne in lignes.values():
        ligne["texte"] = (
            None if ligne["valeur"] is None else chiffre(ligne["valeur"], ligne["unite"])
        )
    return lignes


@routeur.get("/programmes", response_class=HTMLResponse)
def candidats(request: Request) -> HTMLResponse:
    prog = _election()
    nb_sujets = len(prog.grille.sujets)
    cartes = [
        {
            "fiche": f,
            "mesures": len(f.mesures_en_vigueur),
            "sujets": len({m.sujet for m in f.mesures_en_vigueur}),
        }
        for f in prog.candidats
    ]
    en_course = [c for c in cartes if c["fiche"].candidat.statut in ("declare", "officiel")]
    contexte = {
        "election": prog.grille.election,
        "cartes": cartes,
        "en_course": len(en_course),
        "nb_sujets": nb_sujets,
    }
    return gabarits.TemplateResponse(request, "programmes.html", contexte)


@routeur.get("/programmes/comparer", response_class=HTMLResponse)
def comparer(
    request: Request,
    conn: Connexion,
    sujet: Annotated[str | None, Query(pattern=r"^[a-z0-9-]+$")] = None,
) -> HTMLResponse:
    prog = _election()
    choisi = prog.sujet(sujet) if sujet else prog.grille.sujets[0]
    if choisi is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sujet inconnu")
    lignes = prog.comparer(choisi.id)
    echelles = []
    for echelle in (e for e in prog.grille.echelles if e.sujet == choisi.id):
        valeurs = [
            (f.candidat.nom_complet, m.echelle.valeur)
            for f, mesures in lignes
            for m in mesures
            if m.echelle is not None and m.echelle.code == echelle.code
        ]
        if not valeurs:
            continue
        reperes = valeurs + (
            [("En vigueur", echelle.valeur_actuelle)] if echelle.valeur_actuelle is not None else []
        )
        plus_grande = max(v for _, v in reperes) or 1
        echelles.append(
            {
                "echelle": echelle,
                "barres": [
                    {"libelle": nom, "valeur": v, "largeur": 100 * v / plus_grande}
                    for nom, v in reperes
                ],
            }
        )
    contexte = {
        "election": prog.grille.election,
        "sujets": prog.grille.sujets,
        "sujet": choisi,
        "lignes": lignes,
        "echelles": echelles,
        "indicateurs": _contexte(conn, set(choisi.indicateurs)),
    }
    return gabarits.TemplateResponse(request, "programmes_comparer.html", contexte)


@routeur.get("/programmes/{candidat}", response_class=HTMLResponse)
def fiche(
    request: Request,
    conn: Connexion,
    candidat: Annotated[str, Chemin(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")],
) -> HTMLResponse:
    prog = _election()
    lue = prog.fiche(candidat)
    if lue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidat inconnu")
    groupes = []
    codes: set[str] = set()
    for sujet in prog.grille.sujets:
        mesures = [m for m in lue.mesures if m.sujet == sujet.id]
        blocs = []
        for m in mesures:
            indicateurs = m.indicateurs or sujet.indicateurs
            codes.update(indicateurs)
            blocs.append({"mesure": m, "indicateurs": indicateurs})
        en_vigueur = sum(m.retiree_dans is None for m in mesures)
        groupes.append({"sujet": sujet, "blocs": blocs, "en_vigueur": en_vigueur})
    versions = sorted(lue.versions, key=lambda v: (v.publie_le, v.releve_le), reverse=True)
    contexte = {
        "election": prog.grille.election,
        "fiche": lue,
        "versions": versions,
        "groupes": groupes,
        "indicateurs": _contexte(conn, codes),
    }
    return gabarits.TemplateResponse(request, "programmes_candidat.html", contexte)
