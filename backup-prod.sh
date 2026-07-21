#!/bin/bash
# Backup production database from Docker volume
# Run this before any container updates

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CONTAINER="moclo-library-tool"

mkdir -p "$BACKUP_DIR"

echo "Backing up production databases..."
docker cp "$CONTAINER:/data/moclo.db" "$BACKUP_DIR/moclo_${TIMESTAMP}.db" 2>/dev/null && \
  echo "  ✓ moclo.db backed up" || echo "  ✗ moclo.db not found"

docker cp "$CONTAINER:/data/parts.db" "$BACKUP_DIR/parts_${TIMESTAMP}.db" 2>/dev/null && \
  echo "  ✓ parts.db backed up" || echo "  ✗ parts.db not found"

echo "Backups saved to $BACKUP_DIR/"
ls -la "$BACKUP_DIR"/*_${TIMESTAMP}.db 2>/dev/null
