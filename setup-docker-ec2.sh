#!/bin/bash
# EC2 Docker Deployment Script for Resulam Royalties Dashboard
# This script sets up Docker and Docker Compose on EC2 if not already installed

set -e

echo "🚀 Setting up Docker environment on EC2..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "📦 Installing Docker..."
    sudo yum update -y
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    echo "✅ Docker installed"
else
    echo "✅ Docker already installed"
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "📦 Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose installed"
else
    echo "✅ Docker Compose already installed"
fi

# Verify installations
echo ""
echo "📋 Installed versions:"
docker --version
docker-compose --version

echo ""
echo "✅ Docker setup complete!"
echo ""
echo "Next steps:"
echo "1. Clone your repository to ~/apps/resulam-royalties"
echo "2. Add your CSV files to ~/apps/resulam-royalties/data/"
echo "3. Run: cd ~/apps/resulam-royalties && docker-compose up -d"
