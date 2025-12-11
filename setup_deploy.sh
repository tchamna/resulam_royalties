#!/bin/bash
# Setup script to configure deployment environment variables
# Run this once to set GitHub secrets for CI/CD

set -e

echo "================================"
echo "GitHub Secrets Configuration Setup"
echo "================================"
echo ""

# Function to set a GitHub secret
set_github_secret() {
    local secret_name=$1
    local secret_value=$2
    
    if [ -z "$secret_value" ]; then
        echo "❌ Error: $secret_name is empty"
        return 1
    fi
    
    # Check if gh CLI is installed
    if ! command -v gh &> /dev/null; then
        echo "❌ GitHub CLI (gh) is not installed. Please install it: https://cli.github.com/"
        return 1
    fi
    
    # Set the secret
    echo "$secret_value" | gh secret set "$secret_name" --body -
    echo "✅ $secret_name configured"
}

# Get repository info
REPO_OWNER="${GITHUB_REPO_OWNER:-tchamna}"
REPO_NAME="${GITHUB_REPO_NAME:-resulam_royalties}"
FULL_REPO="$REPO_OWNER/$REPO_NAME"

echo "Repository: $FULL_REPO"
echo ""

# Check GitHub CLI authentication
if ! gh auth status > /dev/null 2>&1; then
    echo "❌ GitHub CLI is not authenticated"
    echo "Please run: gh auth login"
    exit 1
fi

echo "🔐 Configuring GitHub Secrets..."
echo ""

# EC2_HOST
read -p "EC2 Host (IP address) [18.208.117.82]: " EC2_HOST
EC2_HOST=${EC2_HOST:-18.208.117.82}
set_github_secret "EC2_HOST" "$EC2_HOST"

# EC2_SSH_KEY
echo ""
echo "EC2_SSH_KEY: Paste the contents of your .pem file"
read -p "Path to .pem file: " SSH_KEY_PATH
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "❌ SSH key file not found: $SSH_KEY_PATH"
    exit 1
fi
SSH_KEY_CONTENT=$(cat "$SSH_KEY_PATH")
set_github_secret "EC2_SSH_KEY" "$SSH_KEY_CONTENT"

# AWS credentials
echo ""
read -p "AWS Access Key ID: " AWS_ACCESS_KEY_ID
if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    echo "⚠️  Skipping AWS_ACCESS_KEY_ID"
else
    set_github_secret "AWS_ACCESS_KEY_ID" "$AWS_ACCESS_KEY_ID"
fi

echo ""
read -sp "AWS Secret Access Key: " AWS_SECRET_ACCESS_KEY
echo ""
if [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "⚠️  Skipping AWS_SECRET_ACCESS_KEY"
else
    set_github_secret "AWS_SECRET_ACCESS_KEY" "$AWS_SECRET_ACCESS_KEY"
fi

# AWS region
echo ""
read -p "AWS Region [us-east-1]: " AWS_DEFAULT_REGION
AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
set_github_secret "AWS_DEFAULT_REGION" "$AWS_DEFAULT_REGION"

# Deploy port
echo ""
read -p "Deployment Port [8050]: " DEPLOY_PORT
DEPLOY_PORT=${DEPLOY_PORT:-8050}
set_github_secret "DEPLOY_PORT" "$DEPLOY_PORT"

echo ""
echo "================================"
echo "✅ All GitHub Secrets Configured!"
echo "================================"
echo ""
echo "Your CI/CD pipeline is now ready to deploy automatically on push to main"
echo ""
echo "To view configured secrets:"
echo "  gh secret list -R $FULL_REPO"
echo ""
echo "Next steps:"
echo "1. Push changes to main branch"
echo "2. Check GitHub Actions to verify deployment"
echo "   https://github.com/$FULL_REPO/actions"
