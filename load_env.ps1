# Load environment variables from .env file
# Usage: . .\load_env.ps1 (note the dot for sourcing)

$envFile = ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "❌ Error: .env file not found" -ForegroundColor Red
    Write-Host "Please create .env file first (copy from .env.example)" -ForegroundColor Yellow
    return
}

Write-Host "📋 Loading environment variables from .env..." -ForegroundColor Cyan

$lineCount = 0
$loadedCount = 0

Get-Content $envFile | ForEach-Object {
    $lineCount++
    $line = $_.Trim()
    
    # Skip empty lines and comments
    if ([string]::IsNullOrEmpty($line) -or $line.StartsWith("#")) {
        return
    }
    
    # Parse KEY=VALUE
    if ($line -match '^\s*([^=]+)=(.*)$') {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        
        # Remove surrounding quotes if present
        if ($value.StartsWith('"') -and $value.EndsWith('"')) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        
        # Set environment variable
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
        Write-Host "  ✅ $key" -ForegroundColor Green
        $loadedCount++
    }
}

Write-Host ""
Write-Host "✅ Loaded $loadedCount environment variables from $envFile" -ForegroundColor Green
Write-Host ""
Write-Host "Ready to run deployment:" -ForegroundColor Cyan
Write-Host "  python deploy.py" -ForegroundColor Yellow
