# Setup script to configure deployment environment variables
# Run this once to set GitHub secrets for CI/CD

Write-Host "================================" -ForegroundColor Cyan
Write-Host "GitHub Secrets Configuration Setup" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check GitHub CLI
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "❌ GitHub CLI (gh) is not installed" -ForegroundColor Red
    Write-Host "Download from: https://cli.github.com/" -ForegroundColor Yellow
    exit 1
}

# Check authentication
$authCheck = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ GitHub CLI is not authenticated" -ForegroundColor Red
    Write-Host "Run: gh auth login" -ForegroundColor Yellow
    exit 1
}

# Repository info
$REPO_OWNER = $env:GITHUB_REPO_OWNER ?? "tchamna"
$REPO_NAME = $env:GITHUB_REPO_NAME ?? "resulam_royalties"
$FULL_REPO = "$REPO_OWNER/$REPO_NAME"

Write-Host "Repository: $FULL_REPO" -ForegroundColor Green
Write-Host ""
Write-Host "🔐 Configuring GitHub Secrets..." -ForegroundColor Cyan
Write-Host ""

# Function to set GitHub secret
function Set-GitHubSecret {
    param(
        [string]$SecretName,
        [string]$SecretValue
    )
    
    if ([string]::IsNullOrEmpty($SecretValue)) {
        Write-Host "❌ Error: $SecretName is empty" -ForegroundColor Red
        return $false
    }
    
    $SecretValue | gh secret set $SecretName --body -
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ $SecretName configured" -ForegroundColor Green
        return $true
    } else {
        Write-Host "❌ Failed to set $SecretName" -ForegroundColor Red
        return $false
    }
}

# EC2_HOST
Write-Host "EC2 Host (IP address) [18.208.117.82]: " -NoNewline
$EC2_HOST = Read-Host
if ([string]::IsNullOrEmpty($EC2_HOST)) { $EC2_HOST = "18.208.117.82" }
Set-GitHubSecret -SecretName "EC2_HOST" -SecretValue $EC2_HOST | Out-Null

# EC2_SSH_KEY
Write-Host ""
Write-Host "EC2_SSH_KEY: Paste the contents of your .pem file" -ForegroundColor Yellow
Write-Host "Path to .pem file: " -NoNewline
$SSH_KEY_PATH = Read-Host
if (-not (Test-Path $SSH_KEY_PATH)) {
    Write-Host "❌ SSH key file not found: $SSH_KEY_PATH" -ForegroundColor Red
    exit 1
}
$SSH_KEY_CONTENT = Get-Content -Path $SSH_KEY_PATH -Raw
Set-GitHubSecret -SecretName "EC2_SSH_KEY" -SecretValue $SSH_KEY_CONTENT | Out-Null

# AWS_ACCESS_KEY_ID
Write-Host ""
Write-Host "AWS Access Key ID: " -NoNewline
$AWS_ACCESS_KEY_ID = Read-Host
if (-not [string]::IsNullOrEmpty($AWS_ACCESS_KEY_ID)) {
    Set-GitHubSecret -SecretName "AWS_ACCESS_KEY_ID" -SecretValue $AWS_ACCESS_KEY_ID | Out-Null
} else {
    Write-Host "⚠️  Skipping AWS_ACCESS_KEY_ID" -ForegroundColor Yellow
}

# AWS_SECRET_ACCESS_KEY
Write-Host ""
Write-Host "AWS Secret Access Key: " -NoNewline
$AWS_SECRET_ACCESS_KEY = Read-Host -AsSecureString
$AWS_SECRET_ACCESS_KEY_PLAIN = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToCoTaskMemUnicode($AWS_SECRET_ACCESS_KEY))
if (-not [string]::IsNullOrEmpty($AWS_SECRET_ACCESS_KEY_PLAIN)) {
    Set-GitHubSecret -SecretName "AWS_SECRET_ACCESS_KEY" -SecretValue $AWS_SECRET_ACCESS_KEY_PLAIN | Out-Null
} else {
    Write-Host "⚠️  Skipping AWS_SECRET_ACCESS_KEY" -ForegroundColor Yellow
}

# AWS_DEFAULT_REGION
Write-Host ""
Write-Host "AWS Region [us-east-1]: " -NoNewline
$AWS_DEFAULT_REGION = Read-Host
if ([string]::IsNullOrEmpty($AWS_DEFAULT_REGION)) { $AWS_DEFAULT_REGION = "us-east-1" }
Set-GitHubSecret -SecretName "AWS_DEFAULT_REGION" -SecretValue $AWS_DEFAULT_REGION | Out-Null

# DEPLOY_PORT
Write-Host ""
Write-Host "Deployment Port [8050]: " -NoNewline
$DEPLOY_PORT = Read-Host
if ([string]::IsNullOrEmpty($DEPLOY_PORT)) { $DEPLOY_PORT = "8050" }
Set-GitHubSecret -SecretName "DEPLOY_PORT" -SecretValue $DEPLOY_PORT | Out-Null

Write-Host ""
Write-Host "================================" -ForegroundColor Green
Write-Host "✅ All GitHub Secrets Configured!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""
Write-Host "Your CI/CD pipeline is now ready to deploy automatically on push to main" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view configured secrets:" -ForegroundColor Yellow
Write-Host "  gh secret list -R $FULL_REPO"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Push changes to main branch"
Write-Host "2. Check GitHub Actions to verify deployment"
Write-Host "   https://github.com/$FULL_REPO/actions"
