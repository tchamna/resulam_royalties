# PowerShell script to set deployment environment variables
# Usage: . .\set_env.ps1 (note the dot for sourcing)

# EC2 Instance Configuration
$env:EC2_IP = "18.208.117.82"
$env:EC2_USER = "ec2-user"
$env:SSH_KEY_PATH = "C:\Users\tcham\Downloads\test-rag.pem"

# GitHub Repository
$env:GIT_REPO = "https://github.com/tchamna/resulam_royalties.git"

# Application Configuration
$env:APP_PORT = "8050"
$env:APP_DIR = "/home/ec2-user/apps/resulam-royalties"
$env:DOMAIN_NAME = "resulam-royalties.tchamna.com"

# AWS Configuration
$env:AWS_REGION = "us-east-1"
$env:AWS_ACCESS_KEY_ID = "your_aws_access_key"
$env:AWS_SECRET_ACCESS_KEY = "your_aws_secret_key"
$env:S3_BUCKET = "resulam-royalties"

# Optional: S3 data files (pipe-separated)
# $env:S3_DATA_FILES = "file1.csv|file2.xlsx"

# Optional: Python packages (pipe-separated)
# $env:PYTHON_PACKAGES = "package1==1.0|package2==2.0"

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Environment Variables Set" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "EC2_IP:      $($env:EC2_IP)" -ForegroundColor Green
Write-Host "EC2_USER:    $($env:EC2_USER)" -ForegroundColor Green
Write-Host "SSH_KEY_PATH: $($env:SSH_KEY_PATH)" -ForegroundColor Green
Write-Host "GIT_REPO:    $($env:GIT_REPO)" -ForegroundColor Green
Write-Host "APP_PORT:    $($env:APP_PORT)" -ForegroundColor Green
Write-Host "DOMAIN_NAME: $($env:DOMAIN_NAME)" -ForegroundColor Green
Write-Host "AWS_REGION:  $($env:AWS_REGION)" -ForegroundColor Green
Write-Host ""
Write-Host "Run deployment with:" -ForegroundColor Yellow
Write-Host "  python deploy.py"
Write-Host ""
