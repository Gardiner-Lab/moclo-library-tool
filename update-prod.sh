#!/bin/bash
# Safely update the production container (backs up first, preserves data)

set -e

echo "=== Production Update ==="
echo ""

# Step 1: Backup
echo "Step 1: Backing up databases..."
./backup-prod.sh
echo ""

# Step 2: Build new image
echo "Step 2: Building new image..."
docker build -t ghcr.io/gardiner-lab/moclo-library-tool:latest .
echo ""

# Step 3: Restart container (volume preserved)
echo "Step 3: Restarting container (data preserved)..."
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d
echo ""

# Step 4: Verify
echo "Step 4: Waiting for health check..."
sleep 5
if curl -s http://localhost:5000/health | grep -q "healthy"; then
  echo "  ✓ Production updated successfully!"
else
  echo "  ✗ Health check failed - check logs with: docker logs moclo-library-tool"
fi
