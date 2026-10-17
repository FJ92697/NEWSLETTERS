#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/fanjin92697-rgb/NEWSLETTERS.git"
APP_DIR="/opt/newsletters"
WEB_ROOT="/var/www/newsletters"
DATA_DIR="/var/lib/newsletters"
PUBLIC_ISSUES="$DATA_DIR/issues"
HOSTNAME="161-35-103-204.sslip.io"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer as root on the dedicated newsletter Droplet." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y nginx python3 git cron logrotate certbot python3-certbot-nginx ca-certificates

if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi

if ! id newsletterd >/dev/null 2>&1; then
  useradd --system --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin newsletterd
fi

mkdir -p "$APP_DIR/drafts" "$APP_DIR/logs" "$APP_DIR/site/issues" "$PUBLIC_ISSUES" /var/www
# Preserve any issues made by the earlier build before detaching runtime data
# from the Git checkout. cp -n never replaces an issue already in data storage.
cp -an "$APP_DIR/site/issues/." "$PUBLIC_ISSUES/"
if [ -f "$APP_DIR/site/issues/index.json" ]; then
  git -C "$APP_DIR" restore -- site/issues/index.json
fi
find "$PUBLIC_ISSUES" -maxdepth 1 -type f \( -name 'index.json' -o -name 'issue-*.html' \) -exec chmod 0644 {} +
chown -R newsletterd:www-data "$APP_DIR/drafts" "$APP_DIR/logs" "$PUBLIC_ISSUES"
chmod 0755 "$APP_DIR/drafts" "$APP_DIR/logs" "$PUBLIC_ISSUES"

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

touch /var/log/newsletters-daily.log /var/log/newsletters-update.log
chown newsletterd:adm /var/log/newsletters-daily.log
chmod 0640 /var/log/newsletters-daily.log
chmod 0640 /var/log/newsletters-update.log
cat > /etc/logrotate.d/newsletters <<'LOGROTATE'
/var/log/newsletters-daily.log {
    weekly
    rotate 8
    maxsize 10M
    missingok
    notifempty
    compress
    delaycompress
    su newsletterd adm
    create 0640 newsletterd adm
}
/var/log/newsletters-update.log {
    weekly
    rotate 8
    maxsize 10M
    missingok
    notifempty
    compress
    delaycompress
    su root adm
    create 0640 root adm
}
LOGROTATE

cat > /etc/cron.d/newsletters <<'CRON'
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
CRON_TZ=America/New_York
NEWSLETTER_PUBLIC_ISSUES=/var/lib/newsletters/issues
50 5 * * * root /usr/bin/bash /opt/newsletters/deploy/update.sh >> /var/log/newsletters-update.log 2>&1
0 6 * * * newsletterd cd /opt/newsletters && /usr/bin/python3 /opt/newsletters/newsletter.py --draft --publish-public >> /var/log/newsletters-daily.log 2>&1
CRON
chmod 0644 /etc/cron.d/newsletters

# Publish the first edition from the configured source feeds. Failed sources
# are logged; a completely empty collection keeps the existing issue index.
runuser -u newsletterd -- env NEWSLETTER_PUBLIC_ISSUES="$PUBLIC_ISSUES" /usr/bin/python3 "$APP_DIR/newsletter.py" --draft --publish-public || true

if getent ahostsv4 "$HOSTNAME" >/dev/null 2>&1; then
  sed -i "s/server_name _;/server_name $HOSTNAME _;/" /etc/nginx/sites-available/newsletters
  nginx -t
  systemctl reload nginx
  certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email --redirect -d "$HOSTNAME" || true
fi

systemctl is-active --quiet nginx
systemctl is-active --quiet cron
echo "Newsletter site installed. HTTPS: https://$HOSTNAME/"
echo "Daily source collection is scheduled for 06:00 America/New_York."

