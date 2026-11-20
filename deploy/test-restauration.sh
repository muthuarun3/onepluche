#!/usr/bin/env bash
# Test de restauration mensuel : récupère la dernière sauvegarde hors site, la déchiffre,
# la restaure dans une base temporaire et vérifie son contenu. Échec = alerte.
set -euo pipefail

CONF_DIR=/etc/demographie
# shellcheck source=/dev/null
source "$CONF_DIR/sauvegarde.conf"
RCLONE=(rclone --config "$CONF_DIR/rclone.conf")
BASE_TEST=demo_restauration_test
AGE_MAX_HEURES=36

ping() {
  [[ -n "${DEMO_PING_RESTAURATION:-}" ]] && curl -fsS -m 10 --retry 3 "${DEMO_PING_RESTAURATION}$1" >/dev/null || true
}
echec() { echo "ÉCHEC : $*" >&2; ping /fail; exit 1; }
trap 'ping /fail' ERR
ping /start

tmp="$(mktemp -d)"
chmod 755 "$tmp"
trap 'rm -rf "$tmp"; runuser -u postgres -- dropdb --if-exists "$BASE_TEST"' EXIT
# ProtectHome=yes rend /root inaccessible : gpg travaille dans un dossier temporaire.
export GNUPGHOME="$tmp/gnupg"
install -d -m 700 "$GNUPGHOME"

dernier="$("${RCLONE[@]}" lsf "$DEMO_RCLONE_DEST/base/" | sort | tail -n 1)"
[[ -n "$dernier" ]] || echec "aucune sauvegarde trouvée dans $DEMO_RCLONE_DEST/base/"

# Fraîcheur : la dernière sauvegarde doit dater de moins de AGE_MAX_HEURES.
date_sauvegarde="$(sed -E 's/.*-([0-9]{8})T([0-9]{2})([0-9]{2}).*/\1 \2:\3/' <<<"$dernier")"
age_heures=$(( ( $(date -u +%s) - $(date -u -d "$date_sauvegarde" +%s) ) / 3600 ))
(( age_heures <= AGE_MAX_HEURES )) || echec "dernière sauvegarde vieille de $age_heures h ($dernier)"

"${RCLONE[@]}" copy "$DEMO_RCLONE_DEST/base/$dernier" "$tmp/"
gpg --batch --quiet --pinentry-mode loopback \
  --passphrase-file "$CONF_DIR/sauvegarde.phrase" \
  --decrypt --output "$tmp/base.dump" "$tmp/$dernier"
chmod 644 "$tmp/base.dump"

runuser -u postgres -- dropdb --if-exists "$BASE_TEST"
runuser -u postgres -- createdb "$BASE_TEST"
runuser -u postgres -- pg_restore --no-owner --no-privileges --exit-on-error \
  --dbname="$BASE_TEST" "$tmp/base.dump"

requete() { runuser -u postgres -- psql -tAX -d "$BASE_TEST" -c "$1"; }
territoires="$(requete "SELECT count(*) FROM ref.territoire")"
migrations="$(requete "SELECT count(*) FROM admin.migration")"
observations="$(requete "SELECT count(*) FROM stat.observation")"
(( territoires >= 121 )) || echec "référentiel incomplet ($territoires territoires)"
(( migrations >= 1 )) || echec "journal des migrations vide"

echo "Restauration de $dernier réussie : $territoires territoires, $migrations migrations, $observations observations."
ping ""
