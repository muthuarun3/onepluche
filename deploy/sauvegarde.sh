#!/usr/bin/env bash
# Sauvegarde quotidienne : base chiffrée + fichiers bruts, copiées hors site avec rclone.
# Rétention de la base : 30 jours. Fichiers bruts : jamais supprimés (immuables).
set -euo pipefail

CONF_DIR=/etc/demographie
# shellcheck source=/dev/null
source "$CONF_DIR/sauvegarde.conf"
RCLONE=(rclone --config "$CONF_DIR/rclone.conf")
BASE=demographie

ping() {
  [[ -n "${DEMO_PING_SAUVEGARDE:-}" ]] && curl -fsS -m 10 --retry 3 "${DEMO_PING_SAUVEGARDE}$1" >/dev/null || true
}
trap 'ping /fail' ERR
ping /start

horodatage="$(date -u +%Y%m%dT%H%M%SZ)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
# ProtectHome=yes rend /root inaccessible : gpg travaille dans un dossier temporaire.
export GNUPGHOME="$tmp/gnupg"
install -d -m 700 "$GNUPGHOME"

runuser -u postgres -- pg_dump --format=custom --dbname="$BASE" > "$tmp/base.dump"
gpg --batch --yes --quiet --pinentry-mode loopback \
  --passphrase-file "$CONF_DIR/sauvegarde.phrase" \
  --symmetric --cipher-algo AES256 \
  --output "$tmp/$BASE-$horodatage.dump.gpg" "$tmp/base.dump"

"${RCLONE[@]}" copy "$tmp/$BASE-$horodatage.dump.gpg" "$DEMO_RCLONE_DEST/base/"
"${RCLONE[@]}" copy --immutable /var/lib/demographie/brut "$DEMO_RCLONE_DEST/brut/"
"${RCLONE[@]}" delete --min-age 30d "$DEMO_RCLONE_DEST/base/"

echo "Sauvegarde $BASE-$horodatage envoyée vers $DEMO_RCLONE_DEST"
ping ""
