# Setup GitHub Secrets from .env file
# Prerequisites: gh CLI must be installed and authenticated
# Run: .\setup_github_secrets.ps1

# Load .env file
$envFile = ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "❌ .env file not found!" -ForegroundColor Red
    exit 1
}

Write-Host "📋 Loading secrets from .env..." -ForegroundColor Cyan

# Parse .env file
$secrets = @{}
Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
        $key, $value = $line -split "=", 2
        if ($key -and $value) {
            $secrets[$key.Trim()] = $value.Trim()
        }
    }
}

# Map .env variables to GitHub secrets
$githubSecrets = @{
    "EC2_HOST" = $secrets["EC2_IP"]
    "EC2_USER" = $secrets["EC2_USER"]
    "EC2_SSH_KEY" = $secrets["SSH_KEY_PATH"]
    "AWS_ACCESS_KEY_ID" = $secrets["AWS_ACCESS_KEY_ID"]
    "AWS_SECRET_ACCESS_KEY" = $secrets["AWS_SECRET_ACCESS_KEY"]
    "DOMAIN_NAME" = $secrets["DOMAIN_NAME"]
    "S3_BUCKET" = $secrets["S3_BUCKET"]
    "APP_DIR" = $secrets["APP_DIR"]
    "AWS_DEFAULT_REGION" = $secrets["AWS_REGION"]
}

# Check if EC2_SSH_KEY is a file path and load its contents
if ($secrets["SSH_KEY_PATH"]) {
    $keyPath = $secrets["SSH_KEY_PATH"]
    if (Test-Path $keyPath) {
        Write-Host "📁 Loading SSH key from: $keyPath" -ForegroundColor Yellow
        $sshKeyContent = Get-Content $keyPath -Raw
        $githubSecrets["EC2_SSH_KEY"] = $sshKeyContent
    } else {
        Write-Host "⚠️  SSH key file not found at: $keyPath" -ForegroundColor Yellow
        $githubSecrets["EC2_SSH_KEY"] = $secrets["SSH_KEY_PATH"]
    }
}

# Get repository info
$repo = (git config --get remote.origin.url) -replace ".*/" -replace ".git$"
$owner = (git config --get remote.origin.url) -replace ".*:" -replace "/.*"

Write-Host "`n🚀 Setting GitHub Secrets for: $owner/$repo" -ForegroundColor Cyan
Write-Host "=" * 70

# Set each secret
$successCount = 0
$failCount = 0

foreach ($secretName in $githubSecrets.Keys) {
    $secretValue = $githubSecrets[$secretName]
    
    if ([string]::IsNullOrEmpty($secretValue)) {
        Write-Host "⏭️  Skipping $secretName (empty value)" -ForegroundColor Gray
        continue
    }
    
    Write-Host "`n📝 Setting: $secretName" -ForegroundColor Yellow
    
    # Use echo with gh CLI to set secret
    $secretValue | gh secret set $secretName --repo "$owner/$repo" 2>&1 | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ Success" -ForegroundColor Green
        $successCount++
    } else {
        Write-Host "   ❌ Failed" -ForegroundColor Red
        $failCount++
    }
}

Write-Host "`n" + "=" * 70
Write-Host "✅ Secrets configured!" -ForegroundColor Green
Write-Host "   Successful: $successCount" -ForegroundColor Green
Write-Host "   Failed: $failCount" -ForegroundColor $(if ($failCount -gt 0) { "Red" } else { "Green" })

Write-Host "`n📋 To verify, run:" -ForegroundColor Cyan
Write-Host "   gh secret list --repo $owner/$repo" -ForegroundColor White
