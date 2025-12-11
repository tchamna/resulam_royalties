# 📋 RESULAM DEPLOYMENT - SETUP CHECKLIST

## Pre-Deployment Checklist

Before running the deployment script, ensure you have completed all steps below:

### ✅ 1. AWS Setup

- [ ] **Create AWS Account** (if not already done)
  - Visit: https://aws.amazon.com/
  - Sign up with your email

- [ ] **Create EC2 Instance**
  - Instance Type: t2.medium or better (for good performance)
  - Operating System: Amazon Linux 2
  - Storage: 20GB (General Purpose SSD)
  - Security Group: Create with SSH access (port 22)
  - Allocate Elastic IP (recommended) so IP doesn't change

- [ ] **Create IAM User for CI/CD (optional but recommended)**
  - Console: AWS → IAM → Users → Add user
  - Permissions: Attach policy `EC2FullAccess`
  - Create Access Key (for AWS CLI)

- [ ] **Get EC2 SSH Key**
  - Download .pem file from AWS Console
  - Store in: `~/.ssh/ec2-key.pem`
  - Set permissions: `chmod 400 ~/.ssh/ec2-key.pem`

### ✅ 2. Local Machine Setup

#### Windows Setup

- [ ] **Install AWS CLI v2**
  - Download: https://aws.amazon.com/cli/
  - Run installer
  - Verify: `aws --version`

- [ ] **Configure AWS CLI**
  ```powershell
  aws configure
  ```
  Enter:
  - AWS Access Key ID: [from IAM user or root account]
  - AWS Secret Access Key: [from IAM user or root account]
  - Default region: `us-east-1` (or your preferred region)
  - Default output: `json`

- [ ] **Install Git**
  - Download: https://git-scm.com/downloads
  - Run installer
  - Verify: `git --version`

- [ ] **Install SSH (Windows 10+)**
  - Usually built-in
  - Verify: `ssh -V`
  - If missing, install via Windows 10 Optional Features

- [ ] **Install GitHub CLI (recommended)**
  - Download: https://cli.github.com/
  - Run installer
  - Login: `gh auth login`

- [ ] **Configure SSH Key**
  - Place EC2 key at: `$env:USERPROFILE\.ssh\ec2-key.pem`
  - Set permissions (Windows):
    ```powershell
    icacls "C:\Users\YourUsername\.ssh\ec2-key.pem" /inheritance:r /grant:r "%username%:F"
    ```

#### macOS/Linux Setup

- [ ] **Install Homebrew (macOS)**
  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```

- [ ] **Install AWS CLI v2**
  ```bash
  # macOS
  brew install awscli
  
  # Or download from https://aws.amazon.com/cli/
  ```
  Verify: `aws --version`

- [ ] **Configure AWS CLI**
  ```bash
  aws configure
  ```

- [ ] **Install Git**
  ```bash
  # macOS
  brew install git
  ```
  Verify: `git --version`

- [ ] **Install GitHub CLI (recommended)**
  ```bash
  # macOS
  brew install gh
  ```

- [ ] **Configure SSH Key**
  ```bash
  mkdir -p ~/.ssh
  # Copy your .pem file to ~/.ssh/ec2-key.pem
  chmod 400 ~/.ssh/ec2-key.pem
  ```

### ✅ 3. Repository Setup

- [ ] **Clone Repository** (if you haven't already)
  ```bash
  git clone https://github.com/tchamna/resulam_royalties.git
  cd resulam_royalties
  ```

- [ ] **Verify Deployment Scripts Exist**
  ```bash
  # Windows
  dir deploy.ps1
  
  # macOS/Linux
  ls -la deploy.sh
  ```

- [ ] **Verify requirements.txt Exists**
  ```bash
  cat requirements.txt
  ```

### ✅ 4. GitHub Setup (for CI/CD with Actions)

- [ ] **Create GitHub SSH Key**
  ```bash
  ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github-actions -N ""
  ```

- [ ] **Add SSH Key to GitHub Account**
  - GitHub Settings → SSH and GPG keys
  - Add the public key from `~/.ssh/github-actions.pub`

- [ ] **Set GitHub Secrets** (for automated deployments)
  - Repository → Settings → Secrets and variables → Actions
  - Add secrets:
    - `AWS_ACCESS_KEY_ID`: Your AWS access key
    - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
    - `AWS_DEFAULT_REGION`: `us-east-1`
    - `EC2_HOST`: Your EC2 public IP
    - `EC2_SSH_KEY`: Contents of `~/.ssh/github-actions` (private key)
    - `DEPLOY_PORT`: `8050` (or port from deployment)

### ✅ 5. Security Configuration

- [ ] **AWS Security Group**
  - Inbound Rule: SSH (port 22) - from your IP or 0.0.0.0/0
  - Inbound Rule: HTTP (port 80) - from 0.0.0.0/0
  - Inbound Rule: HTTPS (port 443) - from 0.0.0.0/0
  - Outbound Rule: All (default)

- [ ] **SSH Key Permissions**
  ```bash
  # Should be readable only by owner
  chmod 400 ~/.ssh/ec2-key.pem
  ls -la ~/.ssh/ec2-key.pem
  # Output should show: -r-------- (400)
  ```

- [ ] **Test SSH Connection**
  ```powershell
  # Windows
  ssh -i "$env:USERPROFILE\.ssh\ec2-key.pem" ec2-user@YOUR_EC2_IP
  
  # macOS/Linux
  ssh -i ~/.ssh/ec2-key.pem ec2-user@YOUR_EC2_IP
  ```

## Step-by-Step Deployment

### Step 1: Verify Prerequisites

```powershell
# Windows
aws --version
git --version
ssh -V
gh --version  # Optional

# macOS/Linux
aws --version
git --version
ssh -V
gh --version  # Optional
```

All should return version numbers.

### Step 2: Test AWS Credentials

```powershell
# Windows / macOS / Linux
aws sts get-caller-identity
```

Should show your AWS Account ID and User ARN.

### Step 3: Test SSH Connection

```powershell
# Windows
ssh -i "$env:USERPROFILE\.ssh\ec2-key.pem" ec2-user@YOUR_EC2_IP "echo 'SSH connection successful!'"

# macOS/Linux
ssh -i ~/.ssh/ec2-key.pem ec2-user@YOUR_EC2_IP "echo 'SSH connection successful!'"
```

### Step 4: Run Deployment Script

**Windows:**
```powershell
cd C:\Users\tcham\Wokspace\resulam_royalties
.\deploy.ps1
```

**macOS/Linux:**
```bash
cd ~/resulam_royalties
chmod +x deploy.sh
./deploy.sh
```

### Step 5: Monitor Deployment

The script will output progress. Wait until you see:
```
╔════════════════════════════════════════════════════════════════════╗
║                  ✅ DEPLOYMENT SUCCESSFUL!                         ║
╚════════════════════════════════════════════════════════════════════╝
```

### Step 6: Verify Application

```bash
# After deployment completes, visit:
http://YOUR_EC2_IP

# Should see Resulam Royalties Dashboard
```

## Troubleshooting Setup Issues

### AWS CLI Issues

**Problem:** `aws: command not found`
- Solution: Reinstall AWS CLI from https://aws.amazon.com/cli/

**Problem:** `Unable to locate credentials`
- Solution: Run `aws configure` and enter your credentials

**Problem:** `InvalidUserID.Malformed` error
- Solution: Verify your AWS Access Key ID is correct

### SSH Issues

**Problem:** `Permission denied (publickey)`
- Solution: Check SSH key permissions: `chmod 400 ~/.ssh/ec2-key.pem`
- Also verify the key corresponds to your EC2 instance

**Problem:** `Could not resolve hostname`
- Solution: Verify EC2 IP address is correct
- Check EC2 instance is running in AWS Console

**Problem:** `ssh: command not found`
- Solution:
  - Windows: Install OpenSSH or use Git Bash
  - macOS: Usually pre-installed, update with Homebrew
  - Linux: `sudo apt-get install openssh-client`

### PowerShell Execution Policy

**Problem:** `File cannot be loaded because running scripts is disabled`
- Solution:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

### Git Issues

**Problem:** `git: command not found`
- Solution: Install Git from https://git-scm.com/downloads

**Problem:** `fatal: not a git repository`
- Solution: Make sure you're in the project directory with `.git` folder

## Deployment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `EC2_IP` | 18.208.117.82 | EC2 instance public IP |
| `EC2_USER` | ec2-user | SSH username |
| `KeyPath` | Auto-detect | Path to SSH key (.pem) |
| `StartPort` | 8050 | Starting port (script auto-finds free port) |
| `Repository` | tchamna/resulam_royalties | GitHub repository |

## Post-Deployment Steps

### 1. Update DNS (if using domain)

```bash
# Add CNAME or A record pointing to your EC2 IP
# In your domain registrar's DNS settings:
# example.com  A  18.208.117.82
```

### 2. Enable HTTPS with Let's Encrypt

```bash
# SSH to instance
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82

# Install Certbot
sudo yum install -y certbot python3-certbot-nginx

# Get certificate (replace with your domain)
sudo certbot --nginx -d yourdomain.com
```

### 3. Monitor Application

```bash
# View logs
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo journalctl -u resulam-royalties -f'

# Monitor system resources
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'watch -n 2 "free -h && echo '---' && df -h"'
```

## Quick Reference Commands

```powershell
# Windows PowerShell

# Connect to AWS
aws configure

# Deploy to EC2
cd C:\Users\tcham\Wokspace\resulam_royalties
.\deploy.ps1

# SSH to instance
ssh -i "$env:USERPROFILE\.ssh\ec2-key.pem" ec2-user@18.208.117.82

# View application logs
ssh -i "$env:USERPROFILE\.ssh\ec2-key.pem" ec2-user@18.208.117.82 `
  'sudo journalctl -u resulam-royalties -f'

# Restart application
ssh -i "$env:USERPROFILE\.ssh\ec2-key.pem" ec2-user@18.208.117.82 `
  'sudo systemctl restart resulam-royalties'
```

```bash
# macOS/Linux

# Connect to AWS
aws configure

# Deploy to EC2
cd ~/resulam_royalties
chmod +x deploy.sh
./deploy.sh

# SSH to instance
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82

# View application logs
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo journalctl -u resulam-royalties -f'

# Restart application
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo systemctl restart resulam-royalties'
```

---

**Getting Help?**
1. Check DEPLOYMENT.md for detailed documentation
2. View DEPLOYMENT_QUICK_REF.md for quick commands
3. Check application logs for errors
4. Verify AWS security group settings
5. Ensure SSH key has correct permissions

**Last Updated:** December 10, 2024
