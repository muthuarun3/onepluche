# PRD — Document d'exigences produit

**Produit :** On épluche (dépôt `onepluche`, paquet Python `demographie`)
**En ligne :** <https://onepluche.duckdns.org> (accès protégé) · vitrine publique :
<https://onepluche.neocities.org>
**Responsable :** Muthu · **État au :** 21 novembre 2026

## 1. Le problème

Muthu a 30 ans et la prochaine élection présidentielle approche. Avant de choisir, il veut
comprendre le pays sur des faits, pas sur des impressions. Les chiffres existent (INSEE,
DREES, Assurance maladie, ministères…), mais ils sont dispersés, publiés dans des formats
hétérogènes, avec des définitions qui se contredisent (deux « chômages », deux « retraités »)
et des millésimes qui ne se comparent pas toujours.

On épluche rassemble ces données publiques officielles, les met à jour seul, et répond à
une série de grandes questions, une application par question, en citant toujours la source.

## 2. Les utilisateurs

| Qui | Usage | Conséquence |
| --- | --- | --- |
| Muthu et un petit cercle de proches | Consulter, comprendre, comparer des départements, souvent sur téléphone | Accès protégé par identifiant (pas d'inscription), interface pensée d'abord pour le téléphone |
| Les visiteurs de la vitrine Neocities | Découvrir le projet | Page statique publique, sans données en direct |
| Les futures applications de l'écosystème | Lire les mêmes chiffres | API JSON versionnée `/api/v1`, documentée en OpenAPI |

Pas de grand public au MVP, pas de comptes, pas de favoris.

## 3. La valeur ajoutée

- **Des chiffres sûrs.** Uniquement des sources officielles sous Licence Ouverte ; chaque
  chiffre affiché indique sa source, son millésime et son statut (provisoire ou définitif).
- **Des définitions explicites.** Quand deux sources donnent deux chiffres légitimes, les
  deux sont libellés différemment et jamais mélangés (chômage BIT contre chômage déclaré,
  pensionnés DREES contre retraités déclarés au recensement).
- **Des phrases, pas seulement des tableaux.** Chaque bloc commence par une phrase lisible
  (« 28,5 % des Français ont 60 ans ou plus… ») construite par le code à partir des données.
- **Toujours à jour, sans effort.** Les imports tournent seuls chaque lundi, avec contrôles
  et alertes ; une donnée douteuse n'est jamais publiée sans validation.
- **Sobre.** Moins de 10 € par mois, aucun service payant à l'usage, aucun modèle de langage.

## 4. Les applications (une question = une application)

L'accueil présente le texte de Muthu puis une carte par question, avec un lien vers
l'application qui y répond. Une barre latérale permet de passer de l'une à l'autre.

### Appli 1 — « Qui sont les Français ? » (`/francais`, en service)

Combien, quel âge, quel travail, quelles études, quelle santé.

| Bloc | Contenu | Source |
| --- | --- | --- |
| Combien | Population au 1er janvier, naissances, décès, évolution depuis 1975 | INSEE estimations, état civil |
| Âge | Moins de 20 ans, 60 ans et plus, 75 ans et plus, pyramide des âges | INSEE estimations |
| Activité | En emploi, chômage, retraités, étudiants ; taux de chômage BIT | INSEE recensement, chômage localisé |
| Métiers | Catégories socioprofessionnelles, secteurs d'activité | INSEE recensement |
| Études | Étudiants par type de formation et par discipline | Ministère de l'Enseignement supérieur |
| Santé | Personnes prises en charge par groupe de pathologies | Assurance maladie |
| Retraites | Pensionnés (France), minimum vieillesse (département) | DREES |

Plus une **fiche territoire** (France, région, département) : chiffres clés, pyramide des
âges par année, évolution de la population, territoires rattachés.

### Appli 2 — « De quoi les Français ont besoin ? » (`/besoins`, en construction)

Pour chaque département : ce qui existe (**accès**), ce que ça coûte (**coût**) et qui en
manque (**manque**). Huit thèmes prévus : logement, énergie, eau, alimentation, transports,
accès aux soins, numérique, garde d'enfants. **MVP : logement, énergie, accès aux soins**
(25 indicateurs), puis transports et courses (prix des carburants, trajets, dépenses par
ménage ; demande du 21/11/2026). Les coûts sont rapportés au revenu local (niveau de vie Filosofi), avec
une mise en avant des 18-39 ans.

Écrans du MVP : vue d'ensemble (budget des ménages, évolution des prix), fiche département
par thème (Accès / Coût / Manque, comparé à la France), page thème (carte et classement).
Six questions guidées, par exemple « Combien d'années de niveau de vie faut-il pour acheter
60 m² dans mon département ? ».

### Appli 5 — « Quel avenir pour les Français ? » (`/avenir`, en construction)

Ce qui attend les Français d'ici 2070-2100, par département, toujours avec une fourchette :
combien d'habitants et de quel âge (INSEE : scénario central, population basse, population
haute), quel climat (scénarios du GIEC, RCP 2.6, 4.5 et 8.5, par DRIAS-2020 de Météo-France)
et quels risques naturels (Géorisques). Sept thèmes : population, climat, risques naturels,
eau, agriculture, santé future, emploi futur ; **MVP : population, climat, risques**.
Les projections ne sont pas des prévisions : chaque page le dit. Les projections nationales
de 2026 servent pour la France ; celles par département (Omphale 2022) sont plus anciennes
et la France y est la somme des départements.

Écrans : vue France (projections nationales, choix du département, thèmes), fiche
département, page thème (carte et classement). Six questions guidées. Dossier de conception
validé le 22/11/2026 : <https://claude.ai/artifact/FTnrnv9wfVht4xEcUs5hnE>.
### Appli 4 — « Les Français sont-ils en sécurité ? » (`/securite`)

Les faits de délinquance enregistrés par la police et la gendarmerie (SSMSI, 16 atteintes
en cinq familles : personnes, vols, biens, stupéfiants ; nombre et taux par département
depuis 2016), les victimes de la route (ONISR : tués et blessés hospitalisés, tués par
million d'habitants) et, après les faits, le sentiment d'insécurité (enquêtes CVS puis VRS,
France métropolitaine). Pas de total par famille (unités différentes). Chaque chiffre
rappelle qu'un fait enregistré n'est pas un fait commis.

Écrans : vue France (une carte par famille avec sa phrase et sa courbe, « la délinquance
augmente-t-elle ? », violences sexuelles, ressenti), fiche département (taux, valeur France,
rang ; bandeau pour Paris et les départements très touristiques), carte par famille. Six
questions guidées. Taux de plainte reportés (rapports VRS en PDF seulement).

### Autres questions

D'autres applications pourront s'ajouter, chacune avec sa question sur l'accueil. Aucune
n'est décidée à ce jour.

## 5. Fonctionnalités clés

| # | Fonctionnalité | État |
| --- | --- | --- |
| F1 | Accueil : texte de présentation + une carte par question | PR #21 ouverte |
| F2 | Barre latérale de navigation entre applications (en haut sur téléphone) | PR #21 ouverte |
| F3 | Résumé « Qui sont les Français ? » en six blocs, France entière | En service |
| F4 | Fiche territoire : chiffres clés, pyramide, évolution, territoires rattachés | En service |
| F5 | Page Sources : état du dernier import de chaque fichier, licence, lien | En service |
| F6 | API JSON `/api/v1` documentée sur `/api/docs` | En service |
| F7 | Imports automatiques hebdomadaires, contrôles, validation manuelle, alertes | En service |
| F8 | Sauvegarde chiffrée quotidienne, test de restauration mensuel | En service |
| F9 | Rubrique `/besoins` : vue d'ensemble, fiche département, page thème | Prévu (appli 2, phase D) |
| F10 | Carte des départements, construite une fois pour les deux applis | Choix du territoire par la carte en service ; carte colorée par indicateur prévue (D4) |
| F11 | Questions guidées (réponse = phrase + graphique + source) | Prévu |
| F12 | Comparer 2 à 4 territoires, export CSV sous chaque graphique | Prévu (appli 1, interface MVP) |
| F14 | Rubrique `/avenir` : projections de population (vue France, fiche département) ; climat et risques ensuite | Population en PR (appli 5, phase A) |
| F15 | Rubrique `/securite` : vue France, fiche département, carte par famille, six questions guidées | En service (appli 4, S3) |
| F13 | Vitrine Neocities à jour, même direction artistique que l'appli | PR #22 ouverte |

Le détail et l'ordre de livraison sont dans [TASKS.md](TASKS.md).

## 6. Exigences fermes

1. Données officielles uniquement, sous Licence Ouverte ; source, millésime et statut à côté
   de chaque chiffre ; licence citée.
2. Maille la plus fine : **le département**. France, France métropolitaine, 18 régions,
   101 départements. Pas de communes en base.
3. Pas de comparaison trompeuse : une règle de comparabilité par indicateur (par exemple
   recensement : millésimes séparés d'au moins 5 ans).
4. Pas de « score » composite qui noterait les départements : on montre, on ne classe pas
   par une note inventée.
5. Un calcul propre à On épluche (exemple : années de niveau de vie pour 60 m²) est signalé
   comme tel, avec sa formule.
6. Lisible sur téléphone sans défilement horizontal ; page chargée en moins d'une seconde.
7. Budget : moins de 10 € par mois, tout compris.
8. Aucun modèle de langage, ni externe ni local : les « questions guidées » remplacent les
   questions en langage naturel.

## 7. Hors périmètre (ne pas ajouter sans accord)

| Élément | Pourquoi |
| --- | --- |
| Questions en langage naturel, LLM | Budget et dépendance externe refusés le 19/11/2026 |
| Comptes utilisateurs, inscription, favoris | Petit cercle : l'accès par identifiant du proxy suffit |
| Détail par commune | Volume × 300 et fusions de communes ; maille département retenue |
| Comparaisons européennes (Eurostat) | Hors du besoin principal |
| Application mobile, mode hors ligne | Le site adaptatif suffit |
| Historique des révisions | Les révisions INSEE remplacent les valeurs ; le brut archivé suffit |
| Microservices, conteneurs en production | Un seul serveur, un seul déploiement |

## 8. Indicateurs de réussite

- Les imports du lundi passent sans intervention, alertes comprises.
- Les valeurs de contrôle (`demo verifier`) sont identiques aux publications des producteurs.
- Une restauration complète depuis la sauvegarde réussit chaque mois.
- Le coût mensuel constaté reste sous 10 €.
- Muthu trouve la réponse à chacune de ses questions en moins de trois clics depuis l'accueil.
