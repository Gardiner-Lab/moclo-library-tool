#!/bin/bash
# Restore production database from a backup
# Usage: ./restore-prod.sh backups/parts_20260624_120000.db backups/moclo_20260624_120000.db

CONTAINER="moclo-library-tool"

if [ -z "$1" ]; then
  echo "Usage: ./restore-prod.sh <parts_backup.db> [moclo_backup.db]"
  echo ""
  echo "Available backups:"
  ls -la backups/*.db 2>/dev/null || echo "  No backups found"
  exit 1
fi

echo "Stopping container..."
docker-compose -f docker-compose.prod.yml down

echo "Restoring databases..."
if [ -n "$1" ] && [ -f "$1" ]; then
  docker run --rm -v moclolibrarytool_moclo-data:/data -v "$(pwd)/$1:/restore.db" alpine cp /restore.db /data/parts.db
  echo "  ✓ Restored parts.db from $1"
fi

if [ -n "$2" ] && [ -f "$2" ]; then
  docker run --rm -v moclolibrarytool_moclo-data:/data -v "$(pwd)/$2:/restore.db" alpine cp /restore.db /data/moclo.db
  echo "  ✓ Restored moclo.db from $2"
fi

echo "Starting container..."
docker-compose -f docker-compose.prod.yml up -d
echo "Done!"
