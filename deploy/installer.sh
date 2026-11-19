#!/usr/bin/env bash
# Installation complète sur un VPS Debian 13 neuf, en root.
#
#   ./installer.sh <domaine> <url-du-depot-git> <destination-rclone>
#   ex. ./installer.sh demo.exemple.fr https://github.com/muthuarun3/onepluche.git sauvegardes:demographie
#
# Prérequis : le domaine pointe vers le serveur ; un « remote » rclone nommé dans la
# destination est déjà configuré dans /etc/demographie/rclone.conf (voir deploy/README.md).
# Le script est relançable : il ne recrée pas ce qui existe déjà.
set -euo pipefail

DOMAINE="${1:?domaine manquant}"
DEPOT="${2:?url du dépôt manquante}"
DEST_SAUVEGARDE="${3:?destination rclone manquante}"
VERSION_UV="0.11.32"

APP_DIR=/opt/demographie/app
CONF_DIR=/etc/demographie
DONNEES_DIR=/var/lib/demographie
BASE=demographie

[[ $EUID -eq 0 ]] || { echo "À lancer en root." >&2; exit 1; }

echo "== Paquets système"
apt-get update -q
apt-get install -y -q postgresql caddy rclone gnupg curl git ufw unattended-upgrades
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== Pare-feu : SSH, HTTP, HTTPS uniquement"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "== Utilisateur système et dossiers"
id demographie >/dev/null 2>&1 || useradd --system --home /opt/demographie --shell /usr/sbin/nologin demographie
install -d -o demographie -g demographie -m 750 /opt/demographie "$DONNEES_DIR" "$DONNEES_DIR/brut"
install -d -o root -g demographie -m 750 "$CONF_DIR"

echo "== uv $VERSION_UV"
if ! command -v uv >/dev/null || [[ "$(uv --version | cut -d' ' -f2)" != "$VERSION_UV" ]]; then
  curl -LsSf "https://astral.sh/uv/$VERSION_UV/install.sh" | env UV_INSTALL_DIR=/usr/local/bin sh
fi

echo "== Code de l'application"
if [[ -d "$APP_DIR/.git" ]]; then
  runuser -u demographie -- git -C "$APP_DIR" pull --ff-only
else
  runuser -u demographie -- git clone "$DEPOT" "$APP_DIR"
fi
runuser -u demographie -- env -C "$APP_DIR" uv sync --frozen --no-dev

echo "== PostgreSQL : rôles, mots de passe, base"
runuser -u postgres -- psql -q -v ON_ERROR_STOP=1 -f "$APP_DIR/sql/roles.sql"
if [[ ! -f "$CONF_DIR/env" ]]; then
  declare -A mdp
  for role in proprietaire import lecture; do
    mdp[$role]="$(openssl rand -hex 24)"
    runuser -u postgres -- psql -q -v ON_ERROR_STOP=1 \
      -c "ALTER ROLE demo_${role} PASSWORD '${mdp[$role]}'"
  done
  umask 027
  cat > "$CONF_DIR/env" <<EOF
DEMO_DB_PROPRIETAIRE_URL=postgresql://demo_proprietaire:${mdp[proprietaire]}@localhost:5432/$BASE
DEMO_DB_IMPORT_URL=postgresql://demo_import:${mdp[import]}@localhost:5432/$BASE
DEMO_DB_LECTURE_URL=postgresql://demo_lecture:${mdp[lecture]}@localhost:5432/$BASE
DEMO_DONNEES_BRUTES=$DONNEES_DIR/brut
EOF
  chown root:demographie "$CONF_DIR/env"
  chmod 640 "$CONF_DIR/env"
  umask 022
fi
runuser -u postgres -- psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$BASE'" | grep -q 1 \
  || runuser -u postgres -- createdb -O demo_proprietaire "$BASE"

echo "== Migrations"
runuser -u demographie -- bash -c "set -a; source $CONF_DIR/env; set +a; cd $APP_DIR && .venv/bin/demo migrer"

echo "== Sauvegardes"
if [[ ! -f "$CONF_DIR/sauvegarde.phrase" ]]; then
  ( umask 077; openssl rand -base64 48 > "$CONF_DIR/sauvegarde.phrase" )
  echo
  echo "!! Phrase de chiffrement des sauvegardes créée dans $CONF_DIR/sauvegarde.phrase"
  echo "!! Copiez-la MAINTENANT dans votre gestionnaire de mots de passe :"
  echo "!! sans elle, les sauvegardes sont illisibles si le serveur est perdu."
  echo
fi
[[ -f "$CONF_DIR/sauvegarde.conf" ]] || cat > "$CONF_DIR/sauvegarde.conf" <<EOF
DEMO_RCLONE_DEST=$DEST_SAUVEGARDE
# Facultatif : URL de « battement » Healthchecks.io, une par tâche
DEMO_PING_SAUVEGARDE=
DEMO_PING_RESTAURATION=
EOF
install -m 750 "$APP_DIR/deploy/sauvegarde.sh" /usr/local/sbin/demographie-sauvegarde
install -m 750 "$APP_DIR/deploy/test-restauration.sh" /usr/local/sbin/demographie-test-restauration

echo "== Caddy : HTTPS automatique et accès protégé"
if [[ ! -f /etc/caddy/demographie-utilisateurs ]]; then
  read -r -p "Premier utilisateur autorisé (identifiant) : " utilisateur
  empreinte="$(caddy hash-password)"
  echo "$utilisateur $empreinte" > /etc/caddy/demographie-utilisateurs
  chmod 640 /etc/caddy/demographie-utilisateurs
  chown root:caddy /etc/caddy/demographie-utilisateurs
fi
sed "s/__DOMAINE__/$DOMAINE/" "$APP_DIR/deploy/Caddyfile" > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

echo "== Services systemd"
install -m 644 "$APP_DIR"/deploy/systemd/*.service "$APP_DIR"/deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now demographie-web.service
systemctl enable --now demographie-sauvegarde.timer demographie-restauration.timer
systemctl reload caddy

echo "== Terminé. Vérifiez : https://$DOMAINE/sante"
echo "   Puis lancez une première sauvegarde et un test de restauration :"
echo "   systemctl start demographie-sauvegarde && systemctl start demographie-restauration"
