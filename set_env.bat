@echo off
REM Batch file to set deployment environment variables on Windows
REM Usage: run this file or source its variables

setlocal enabledelayedexpansion

REM EC2 Instance Configuration
set "EC2_IP=18.208.117.82"
set "EC2_USER=ec2-user"
set "SSH_KEY_PATH=C:\Users\tcham\Downloads\test-rag.pem"

REM GitHub Repository
set "GIT_REPO=https://github.com/tchamna/resulam_royalties.git"

REM Application Configuration
set "APP_PORT=8050"
set "APP_DIR=/home/ec2-user/apps/resulam-royalties"
set "DOMAIN_NAME=resulam-royalties.tchamna.com"

REM AWS Configuration
set "AWS_REGION=us-east-1"
set "AWS_ACCESS_KEY_ID=your_aws_access_key"
set "AWS_SECRET_ACCESS_KEY=your_aws_secret_key"
set "S3_BUCKET=resulam-royalties"

REM Optional: S3 data files (pipe-separated)
REM set "S3_DATA_FILES=file1.csv|file2.xlsx"

REM Optional: Python packages (pipe-separated)
REM set "PYTHON_PACKAGES=package1==1.0|package2==2.0"

echo.
echo ================================
echo Environment Variables Set
echo ================================
echo.
echo EC2_IP: %EC2_IP%
echo EC2_USER: %EC2_USER%
echo SSH_KEY_PATH: %SSH_KEY_PATH%
echo GIT_REPO: %GIT_REPO%
echo APP_PORT: %APP_PORT%
echo DOMAIN_NAME: %DOMAIN_NAME%
echo AWS_REGION: %AWS_REGION%
echo.
echo Run deployment with:
echo   python deploy.py
echo.
