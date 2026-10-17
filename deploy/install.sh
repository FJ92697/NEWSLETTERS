#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/fanjin92697-rgb/NEWSLETTERS.git"
APP_DIR="/opt/newsletters"
WEB_ROOT="/var/www/newsletters"
HOSTNAME="161-35-103-204.sslip.io"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y nginx python3 python3-venv git cron certbot python3-certbot-nginx ca-certificates

if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi

mkdir -p "$APP_DIR/drafts" "$APP_DIR/logs" "$APP_DIR/site/issues" /var/www
if [ -e "$WEB_ROOT" ] && [ ! -L "$WEB_ROOT" ]; then
  echo "$WEB_ROOT exists and is not a symlink; refusing to replace it." >&2
  exit 1
fi
ln -sfn "$APP_DIR/site" "$WEB_ROOT"
install -m 0644 "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/newsletters
ln -sfn /etc/nginx/sites-available/newsletters /etc/nginx/sites-enabled/newsletters
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx cron
systemctl reload nginx

cat > /etc/cron.d/newsletters <<'CRON'
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
CRON_TZ=America/New_York
0 6 * * * root cd /opt/newsletters && /usr/bin/python3 /opt/newsletters/newsletter.py --draft --publish-public >> /var/log/newsletters-daily.log 2>&1
CRON
chmod 0644 /etc/cron.d/newsletters

# Publish the first edition from the configured source feeds. A failed fetch
# leaves the public issue index unchanged and is visible in the run log.
cd "$APP_DIR"
/usr/bin/python3 newsletter.py --draft --publish-public || true

# Use the IP-derived hostname for HTTPS without changing a domain the user owns.
if getent ahostsv4 "$HOSTNAME" >/dev/null 2>&1; then
  sed -i "s/server_name _;/server_name $HOSTNAME _;/" /etc/nginx/sites-available/newsletters
  nginx -t && systemctl reload nginx
  certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email --redirect -d "$HOSTNAME" || true
fi

systemctl is-active --quiet nginx
echo "Newsletter site installed. HTTP: http://161.35.103.204/"
echo "Certificate request attempted for https://$HOSTNAME/ when DNS resolved; verify HTTPS separately."
echo "Daily source-linked issue scheduled for 06:00 America/New_York."

