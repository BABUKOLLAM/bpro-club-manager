#!/usr/bin/env bash
# One-command install on a fresh Ubuntu / Debian VPS (Hostinger KVM or any other):
#
#   curl -fsSL https://raw.githubusercontent.com/BABUKOLLAM/bpro-club-manager/main/deploy/vps-install.sh | sudo bash -s -- club.example.org admin@example.org
#
# Installs Docker and Caddy, clones the repository to /opt/club, writes /opt/club/.env (admin login and a generated
# password), starts the app on 127.0.0.1:8810 behind Caddy with automatic HTTPS, and schedules a nightly backup.
# Point the domain's A record at this server before running it, so Caddy can obtain the certificate.
# Re-running it is safe: it updates the checkout, rebuilds the image and keeps .env and the data.
set -euo pipefail
DOMAIN=${1:-}; ADMIN=${2:-}; REPO=${REPO:-https://github.com/BABUKOLLAM/bpro-club-manager.git}; DIR=/opt/club
if [ -z "$DOMAIN" ] || [ -z "$ADMIN" ]; then echo "usage: vps-install.sh DOMAIN ADMIN_LOGIN"; exit 1; fi
if [ "$(id -u)" -ne 0 ]; then echo "run as root (sudo)"; exit 1; fi

echo "== packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ca-certificates curl git gnupg sqlite3 ufw
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sh; fi
systemctl enable --now docker
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q && apt-get install -y -q caddy
fi

echo "== code"
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull -q --ff-only; else git clone -q "$REPO" "$DIR"; fi
mkdir -p "$DIR/data" "$DIR/backups"

echo "== configuration"
if [ ! -f "$DIR/.env" ]; then
  PW=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 14)
  cat > "$DIR/.env" <<ENV
CLUB_ADMIN_LOGIN=$ADMIN
CLUB_ADMIN_PASSWORD=$PW
CLUB_ADMIN_NAME=Secretary
CLUB_PUBLIC_URL=https://$DOMAIN
# WhatsApp / SMS / e-mail: see .env.example, then: docker compose -f $DIR/docker-compose.yml up -d
ENV
  chmod 600 "$DIR/.env"
  echo "   first administrator: $ADMIN  password: $PW   (change it after the first sign-in)"
fi

echo "== app"
docker compose -f "$DIR/docker-compose.yml" up -d --build
for i in $(seq 1 30); do curl -fs http://127.0.0.1:8810/healthz >/dev/null 2>&1 && break; sleep 2; done
curl -fs http://127.0.0.1:8810/healthz >/dev/null || { echo "app did not start - docker compose -f $DIR/docker-compose.yml logs"; exit 1; }

echo "== caddy (HTTPS for $DOMAIN)"
cat > /etc/caddy/Caddyfile <<CADDY
$DOMAIN {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8810
}
CADDY
systemctl enable --now caddy && systemctl reload caddy

echo "== firewall and backups"
ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw --force enable >/dev/null
cat > /etc/cron.d/club-backup <<CRON
15 2 * * * root $DIR/deploy/backup.sh $DIR/data $DIR/backups >> /var/log/club-backup.log 2>&1
CRON
chmod +x "$DIR/deploy/backup.sh"

echo
echo "done: https://$DOMAIN  (certificate is issued on the first visit; data in $DIR/data, backups in $DIR/backups)"
echo "update later: sudo bash $DIR/deploy/vps-install.sh $DOMAIN $ADMIN"
