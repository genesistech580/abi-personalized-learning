#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /home/genesistech1/abi-learning
exec 9>.deployment-lock
flock -n 9 || { echo "Another deployment is running"; exit 1; }
source .hosting-env
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup="$HOME/abi-backups/$stamp"
mkdir -p "$backup"
if [ -f db.sqlite3 ]; then
    .venv/bin/python - "$backup/db.sqlite3" <<'PY'
import sqlite3
import sys
with sqlite3.connect("db.sqlite3") as source, sqlite3.connect(sys.argv[1]) as target:
    source.backup(target)
PY
fi
tar --exclude='./.venv' --exclude='./media' --exclude='./staticfiles'     --exclude='./db.sqlite3*' --exclude='./.hosting-env' --exclude='./.deployment-lock'     -czf "$backup/source.tar.gz" .
tar -xzf "$HOME/abi-release.tar.gz" -C .
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py check --settings=config.hosting
.venv/bin/python manage.py migrate --noinput --settings=config.hosting
.venv/bin/python manage.py collectstatic --noinput --settings=config.hosting
# Alwaysdata site restart requires a separate account API key.
if [ -z "${ALWAYSDATA_API_KEY:-}" ]; then
    echo "Set ALWAYSDATA_API_KEY in .hosting-env to permit site restarts."
    exit 1
fi
curl --fail --silent --show-error --user "$ALWAYSDATA_API_KEY:"     --request POST https://api.alwaysdata.com/v1/site/1107454/restart/
curl --fail --silent --show-error --retry 5 --retry-all-errors --retry-delay 3     https://genesistech1.alwaysdata.net/abitech/accounts/login/ > /dev/null
echo "Deployment verified. Backup: $backup"
