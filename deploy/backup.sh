#!/usr/bin/env bash
# Nightly backup of the SQLite database and uploads: ./deploy/backup.sh /path/to/data /path/to/backups
set -euo pipefail
data=${1:-./data}; out=${2:-./backups}; mkdir -p "$out"
stamp=$(date +%Y%m%d-%H%M)
sqlite3 "$data/club.db" ".backup '$out/club-$stamp.db'"
tar czf "$out/uploads-$stamp.tgz" -C "$data" uploads
find "$out" -name 'club-*.db' -mtime +30 -delete; find "$out" -name 'uploads-*.tgz' -mtime +30 -delete
echo "backed up to $out/club-$stamp.db"
