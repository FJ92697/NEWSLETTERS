#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/newsletters"
cd "$APP_DIR"

# Runtime issues live in /var/lib/newsletters, so the checkout stays clean.
git restore -- site/issues/index.json
git fetch --quiet origin main
git merge --ff-only origin/main
/usr/bin/python3 -m py_compile "$APP_DIR/newsletter.py"
nginx -t
systemctl reload nginx

