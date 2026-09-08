#!/bin/bash
# STRIKE RESET: Clears all Docker containers, volumes, and temporary caches.

echo "🛡️  Initiating Strike Reset..."

# 1. Force-stop and prune all Docker containers/volumes
echo "Stopping and pruning all Docker services and volumes..."
docker-compose down -v --remove-orphans
echo "Pruning Docker system..."
docker system prune -af

# 2. Recursively delete cache and temporary directories
echo "Recursively deleting __pycache__, .next, and node_modules directories..."
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type d -name ".next" -exec rm -rf {} +
find . -type d -name "node_modules" -exec rm -rf {} +

echo "✅ Strike Reset complete. The environment is clean."
echo "Run 'docker-compose up -d --build' to restart the system."
