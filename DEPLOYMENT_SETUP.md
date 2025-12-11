# Deployment Setup Guide

This guide will help you configure your GitHub CI/CD pipeline for automatic deployments to EC2.

## Prerequisites

1. **GitHub CLI** installed and authenticated
   - Download: https://cli.github.com/
   - Verify: `gh auth status`

2. **AWS Credentials** (optional, only if using S3 for data files)
   - AWS Access Key ID
   - AWS Secret Access Key

3. **EC2 Instance Details**
   - Instance IP address
   - SSH private key (.pem file)

## Quick Setup

### On Windows (PowerShell):

```powershell
.\setup_deploy.ps1
```

### On macOS/Linux (Bash):

```bash
chmod +x setup_deploy.sh
./setup_deploy.sh
```

## What Gets Configured

The setup script will prompt you for and configure these GitHub Secrets:

| Secret Name | Description | Example |
|---|---|---|
| `EC2_HOST` | EC2 instance IP address | `18.208.117.82` |
| `EC2_SSH_KEY` | SSH private key contents (.pem file) | `-----BEGIN RSA PRIVATE KEY-----...` |
| `AWS_ACCESS_KEY_ID` | AWS access key (optional) | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key (optional) | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_DEFAULT_REGION` | AWS region for S3 (optional) | `us-east-1` |
| `DEPLOY_PORT` | Port for the deployed app | `8050` |

## How Deployment Works

Once configured, the CI/CD pipeline will automatically:

1. **Trigger on every push to `main` branch**
2. **Clone your latest code** on EC2
3. **Update dependencies** from `requirements.txt`
4. **Restart the service** to apply changes
5. **Verify the deployment** with health checks

## Manual Deployment

You can also trigger a manual deployment from GitHub:

1. Go to: https://github.com/YOUR_USERNAME/resulam_royalties/actions
2. Click "Deploy to EC2" workflow
3. Click "Run workflow" button
4. Select environment: `production` or `staging`
5. Click "Run workflow"

## View Deployment Logs

Check deployment status:

```bash
# View all configured secrets
gh secret list -R tchamna/resulam_royalties

# Trigger workflow manually
gh workflow run deploy.yml -R tchamna/resulam_royalties

# View workflow runs
gh run list -R tchamna/resulam_royalties
```

## Troubleshooting

### "GitHub CLI is not authenticated"
```bash
gh auth login
```

### "SSH key file not found"
Make sure the path to your `.pem` file is correct

### Deployment fails in CI/CD
1. Check GitHub Actions logs: https://github.com/YOUR_USERNAME/resulam_royalties/actions
2. SSH to EC2 and check service logs:
   ```bash
   ssh -i your-key.pem ec2-user@18.208.117.82
   sudo journalctl -u resulam-royalties -f
   ```

## Next Steps

1. Run the setup script: `setup_deploy.ps1` (Windows) or `setup_deploy.sh` (macOS/Linux)
2. Push your code to main branch
3. Watch the deployment in GitHub Actions
4. Verify your app is live at your EC2 domain

---

For more details on manual EC2 deployment, see `deploy.py`
