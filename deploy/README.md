# Déploiement en production

Cible : un VPS Debian 13 (2 vCPU, 4 Go), un nom de domaine, un stockage de sauvegarde
chez un autre fournisseur. Budget visé : moins de 10 € par mois.

## Ce que fait `installer.sh`

| Étape | Détail |
| --- | --- |
| Système | PostgreSQL 17, Caddy, rclone, mises à jour de sécurité automatiques |
| Pare-feu | Seuls SSH, 80 et 443 sont ouverts ; PostgreSQL n'écoute que sur la machine locale |
| Application | Utilisateur `demographie` sans shell, code dans `/opt/demographie/app`, dépendances verrouillées |
| Base | Rôles `demo_*` avec mots de passe aléatoires dans `/etc/demographie/env` (lisible par l'application seulement), migrations |
| Accès | HTTPS automatique, identifiant et mot de passe par personne (Caddy) |
| Sauvegarde | Chaque nuit à 3 h 30 : base chiffrée (AES-256) + fichiers bruts, 30 jours de rétention |
| Restauration | Le 1er de chaque mois : la dernière sauvegarde est restaurée dans une base temporaire et vérifiée |

## Avant de lancer l'installation

1. Commander le VPS (Debian 13) et faire pointer le domaine vers son adresse IP.
2. Se connecter en SSH **par clé**, puis désactiver la connexion par mot de passe
   (`PasswordAuthentication no` dans `/etc/ssh/sshd_config`).
3. Configurer la destination des sauvegardes avec rclone, dans le fichier attendu :

   ```bash
   apt-get install -y rclone
   mkdir -p /etc/demographie
   rclone config --config /etc/demographie/rclone.conf   # créer un « remote », ex. « sauvegardes »
   ```

## Installation

```bash
git clone https://github.com/muthuarun3/onepluche.git /tmp/onepluche
/tmp/onepluche/deploy/installer.sh demo.exemple.fr https://github.com/muthuarun3/onepluche.git sauvegardes:demographie
```

Le script demande le premier identifiant autorisé et son mot de passe.

**Important :** il affiche l'emplacement de la phrase de chiffrement des sauvegardes.
Copiez-la dans votre gestionnaire de mots de passe : sans elle, une sauvegarde est
illisible si le serveur est perdu.

Puis validez le jalon de la phase 0 :

```bash
systemctl start demographie-sauvegarde
systemctl start demographie-restauration
journalctl -u demographie-restauration -n 20    # doit finir par « Restauration … réussie »
```

## Exploitation courante

| Besoin | Commande |
| --- | --- |
| Ajouter un utilisateur | `echo "nom $(caddy hash-password)" >> /etc/caddy/demographie-utilisateurs && systemctl reload caddy` |
| Importer maintenant | `systemctl start demographie-import` (sinon chaque lundi à 6 h 15) ; journal : `demo imports` |
| Mettre à jour l'application | `cd /opt/demographie/app && sudo -u demographie git pull && sudo -u demographie uv sync --frozen --no-dev`, puis `demo migrer` et `systemctl restart demographie-web` |
| Journaux | `journalctl -u demographie-web`, `journalctl -u demographie-sauvegarde` |
| Prochaines exécutions | `systemctl list-timers 'demographie-*'` |

Les commandes `demo` s'exécutent ainsi :
`sudo -u demographie bash -c 'set -a; source /etc/demographie/env; set +a; /opt/demographie/app/.venv/bin/demo etat'`

## Reconstruire après la perte du serveur

1. Nouveau VPS, mêmes étapes « Avant de lancer l'installation » (avec le même `rclone.conf`).
2. Recopier la phrase de chiffrement dans `/etc/demographie/sauvegarde.phrase` (droits 600).
3. Lancer `installer.sh`, puis restaurer la dernière sauvegarde dans la base `demographie` :

   ```bash
   rclone --config /etc/demographie/rclone.conf lsf sauvegardes:demographie/base/ | sort | tail -1
   rclone --config /etc/demographie/rclone.conf copy sauvegardes:demographie/base/<fichier> /tmp/
   gpg --batch --pinentry-mode loopback --passphrase-file /etc/demographie/sauvegarde.phrase \
       --decrypt --output /tmp/base.dump /tmp/<fichier>
   chmod 644 /tmp/base.dump
   sudo -u postgres pg_restore --clean --if-exists --dbname=demographie /tmp/base.dump
   rclone --config /etc/demographie/rclone.conf copy sauvegardes:demographie/brut/ /var/lib/demographie/brut/
   ```

## Alertes (facultatif)

Créer deux contrôles gratuits sur Healthchecks.io (sauvegarde quotidienne, restauration
mensuelle) et coller leurs URL dans `/etc/demographie/sauvegarde.conf`. Vous êtes prévenu
par courriel si une tâche échoue ou ne s'exécute plus.

Veille des programmes présidentiels (`demographie-veille-programmes.timer`, lundi 7 h 15) :
un troisième contrôle, dont l'URL va dans `DEMO_PING_PROGRAMMES` de `/etc/demographie/env`,
prévient par courriel quand un programme suivi a changé ou n'a pas pu être relevé.
