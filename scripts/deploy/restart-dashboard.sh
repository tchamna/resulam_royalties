#!/bin/bash
# Quick restart script for EC2 Docker deployment with S3 auto-sync
# Usage: ./restart-dashboard.sh

set -e

echo "🔄 Updating Resulam Royalties Dashboard..."

# Pull latest changes
echo "📥 Pulling latest code..."
git pull origin main

# Build the image
echo "🏗️ Building Docker image..."
docker build -t resulam-royalties:latest .

echo "🔄 Restarting container..."

# Stop and remove existing container
docker stop resulam-royalties 2>/dev/null || true
docker rm resulam-royalties 2>/dev/null || true

# Start new container with S3 auto-sync and restart policy
docker run -d \
  --restart unless-stopped \
  --name resulam-royalties \
  -p 8050:8050 \
  -v ~/.aws:/root/.aws:ro \
  -e USE_S3_DATA=true \
  -e S3_BUCKET=resulam-royalties \
  -e AWS_DEFAULT_REGION=us-east-1 \
  -e AUTO_SYNC_INTERVAL=300 \
  resulam-royalties:latest

echo "✅ Dashboard restarted with S3 auto-sync enabled (checking every 5 mins)"
echo "📊 Logs: docker logs -f resulam-royalties"
  resulam-royalties:latest

echo "✅ Container started!"
echo "📊 Dashboard will be available at http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8050"
echo ""
echo "📡 Data files are automatically downloaded from S3 on startup"
echo "🔍 Check logs with: docker logs resulam-royalties"
