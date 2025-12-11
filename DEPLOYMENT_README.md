# 🚀 RESULAM ROYALTIES - EC2 DEPLOYMENT SYSTEM

Complete, automated deployment system for deploying your Resulam Royalties Dashboard to AWS EC2.

## 📁 What's Included

### Deployment Scripts
- **`deploy.ps1`** - PowerShell deployment script for Windows
- **`deploy.sh`** - Bash deployment script for macOS/Linux
- **`ec2-manage.sh`** - Management script for post-deployment operations

### Documentation
- **`SETUP_CHECKLIST.md`** - Pre-deployment setup checklist
- **`DEPLOYMENT.md`** - Comprehensive deployment documentation
- **`DEPLOYMENT_QUICK_REF.md`** - Quick reference card
- **`requirements.txt`** - Python dependencies

### CI/CD
- **`.github/workflows/deploy.yml`** - GitHub Actions workflow for automated deployments

## 🎯 Quick Start (60 seconds)

### Prerequisites
1. AWS account with EC2 instance running Amazon Linux 2
2. AWS CLI installed and configured
3. SSH key (.pem file) downloaded from AWS
4. Git installed

### Deploy in 3 Commands

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

**Wait 2-3 minutes, then visit:**
```
http://YOUR_EC2_IP
```

## 🔧 What Gets Deployed

```
Your EC2 Instance
├── Application (Resulam Royalties Dashboard)
├── Nginx (Reverse Proxy on port 80)
├── Python Virtual Environment
├── Systemd Service (auto-restart on boot)
└── Automatic Logs with Journalctl
```

### Automatic Setup
✅ System packages installed (Python, Nginx, etc.)
✅ Repository cloned/updated from GitHub
✅ Virtual environment created
✅ Dependencies installed
✅ Nginx configured
✅ Systemd service created
✅ Application started
✅ Security group updated
✅ GitHub secrets updated

## 📊 Architecture

```
┌─────────────────────────────────────────┐
│  Browser at http://YOUR_EC2_IP          │
└────────────────┬────────────────────────┘
                 │ HTTP (Port 80)
                 ▼
┌─────────────────────────────────────────┐
│  Nginx Reverse Proxy                    │
│  - Load balancing                       │
│  - SSL/TLS termination (optional)       │
│  - Static file serving                  │
└────────────────┬────────────────────────┘
                 │ Proxy Pass (Port 8050+)
                 ▼
┌─────────────────────────────────────────┐
│  Dash Application                       │
│  - Resulam Royalties Dashboard          │
│  - Python/Dash Framework                │
│  - WebSocket support                    │
└─────────────────────────────────────────┘
```

## 🚀 Deployment Methods

### Method 1: Local Deployment (Recommended for First Deploy)

**Pros:**
- ✅ Full control over process
- ✅ Can see all logs in real-time
- ✅ Easy to troubleshoot
- ✅ Works offline

**Steps:**
```powershell
# Windows
.\deploy.ps1 -EC2_IP "18.208.117.82" -KeyPath "C:\path\to\key.pem"

# macOS/Linux
./deploy.sh 18.208.117.82 ~/.ssh/ec2-key.pem
```

### Method 2: GitHub Actions (Automated)

**Pros:**
- ✅ Automatic deployment on git push
- ✅ No manual steps needed
- ✅ Automatic rollback on failure
- ✅ Version history

**Setup:**
1. Add secrets to GitHub (see SETUP_CHECKLIST.md)
2. Push to main branch
3. GitHub Actions automatically deploys

**Files:**
- `.github/workflows/deploy.yml` - Workflow definition

## 🔑 Key Features

### 🤖 Fully Automated
- Single command deployment
- No manual EC2 configuration needed
- Automatic port discovery
- Automatic security group updates
- Automatic service configuration

### 🛡️ Production-Ready
- Nginx reverse proxy
- Systemd service management
- Automatic restart on failure
- 120-second timeouts for long operations
- Full logging with journalctl

### 📈 Scalable
- Easy to update application code
- One-command redeployment
- Automatic dependency updates
- Git-based version control

### 🔍 Easy to Monitor
- Real-time logs
- Health checks
- Status monitoring
- Resource usage tracking
- Error logs and debugging

## 💻 Command Reference

### Deployment

```powershell
# Windows - Deploy with custom port
.\deploy.ps1 -EC2_IP "18.208.117.82" -StartPort 8050
```

```bash
# macOS/Linux - Deploy with custom repository
./deploy.sh 18.208.117.82 ~/.ssh/ec2-key.pem 8050
```

### Post-Deployment Management

```bash
# Check status
./ec2-manage.sh status

# View logs (follow mode)
./ec2-manage.sh logs

# Restart application
./ec2-manage.sh restart

# Update application
./ec2-manage.sh update

# Rollback to previous version
./ec2-manage.sh rollback

# Health check
./ec2-manage.sh health

# SSH to instance
./ec2-manage.sh ssh
```

### SSH Direct Commands

```bash
# View logs
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo journalctl -u resulam-royalties -f'

# Restart service
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo systemctl restart resulam-royalties'

# Check service status
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo systemctl status resulam-royalties'

# Check disk usage
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 'df -h'

# Check memory usage
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 'free -h'
```

## 🚨 Troubleshooting

### Application Won't Start

```bash
# Check logs
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo journalctl -u resulam-royalties -n 50'

# Check if port is in use
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo netstat -tuln | grep 8050'

# Restart service
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo systemctl restart resulam-royalties'
```

### 502 Bad Gateway Error

```bash
# Verify Dash is running on its port
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'curl http://127.0.0.1:8050'

# Check Nginx error log
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo tail -f /var/log/nginx/error.log'

# Verify Nginx configuration
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 \
  'sudo nginx -t'
```

### SSH Connection Issues

```powershell
# Verify key permissions (Windows)
icacls "C:\Users\YourUsername\.ssh\ec2-key.pem"

# Verify key permissions (macOS/Linux)
ls -la ~/.ssh/ec2-key.pem  # Should show: -r-------- (400)

# Fix permissions if needed
chmod 400 ~/.ssh/ec2-key.pem

# Test connection with verbose output
ssh -vvv -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82 'echo success'
```

## 🔐 Security

### AWS Security Group
The script automatically configures:
- SSH (port 22) - for management
- HTTP (port 80) - for web access
- HTTPS (port 443) - for encrypted access

### Best Practices
1. ✅ SSH keys stored locally (never committed to git)
2. ✅ GitHub secrets used for CI/CD
3. ✅ AWS credentials not hardcoded
4. ✅ Systemd service runs as non-root user
5. ✅ Nginx runs as restricted user

### Enable HTTPS with Let's Encrypt

```bash
# SSH to instance
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82

# Install Certbot
sudo yum install -y certbot python3-certbot-nginx

# Get certificate (replace with your domain)
sudo certbot --nginx -d yourdomain.com

# Certificate auto-renews
```

## 📝 Configuration Files

### On EC2 Instance

**Application Service:**
```
/etc/systemd/system/resulam-royalties.service
```

**Nginx Configuration:**
```
/etc/nginx/conf.d/resulam-royalties.conf
```

**Application Directory:**
```
/home/ec2-user/resulam-royalties/
```

**Logs:**
```
sudo journalctl -u resulam-royalties -f  # Application logs
sudo tail -f /var/log/nginx/error.log     # Nginx error logs
sudo tail -f /var/log/nginx/access.log    # Nginx access logs
```

## 🔄 Update and Redeploy

### Method 1: Using Management Script

```bash
./ec2-manage.sh update
```

### Method 2: Using Deployment Script

```powershell
# Windows
.\deploy.ps1

# macOS/Linux
./deploy.sh
```

### Method 3: Manual via SSH

```bash
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82
cd /home/ec2-user/resulam-royalties
git pull origin main
sudo systemctl restart resulam-royalties
```

## ↩️ Rollback

### Using Management Script

```bash
./ec2-manage.sh rollback
```

### Manual Rollback

```bash
ssh -i ~/.ssh/ec2-key.pem ec2-user@18.208.117.82
cd /home/ec2-user/resulam-royalties
git log --oneline -5        # See recent commits
git reset --hard HEAD~1     # Rollback one commit
sudo systemctl restart resulam-royalties
```

## 📊 Monitoring

### Application Health

```bash
# Check service running
./ec2-manage.sh status

# Perform health check
./ec2-manage.sh health

# View logs
./ec2-manage.sh logs
```

### System Resources

```bash
# Disk usage
./ec2-manage.sh disk

# Memory usage
./ec2-manage.sh memory

# Port usage
./ec2-manage.sh ports
```

### Nginx Status

```bash
# Nginx service
./ec2-manage.sh nginx-status

# Nginx error logs
./ec2-manage.sh nginx-logs
```

## 🚀 CI/CD with GitHub Actions

### Setup GitHub Secrets

```bash
# In GitHub repository settings:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_DEFAULT_REGION
- EC2_HOST
- EC2_SSH_KEY (private key content)
```

### Automatic Deployment on Push

```bash
git push origin main  # Automatically triggers GitHub Actions
```

### View Deployment Status

- GitHub → Actions → deploy.yml
- See real-time logs
- Automatic rollback on failure

## 🛠️ Advanced Usage

### Custom Port

```powershell
# Windows
.\deploy.ps1 -StartPort 9000

# macOS/Linux
./deploy.sh YOUR_EC2_IP ~/.ssh/ec2-key.pem 9000
```

### Custom Repository

```powershell
# Windows
.\deploy.ps1 -Repository "your-username/your-repo"

# macOS/Linux
./deploy.sh YOUR_EC2_IP ~/.ssh/ec2-key.pem 8050
```

### Custom EC2 Settings

```powershell
# Windows
.\deploy.ps1 -EC2_IP "1.2.3.4" -EC2_User "ubuntu" -KeyPath "C:\keys\aws.pem"

# macOS/Linux
./deploy.sh 1.2.3.4 ~/.ssh/ubuntu.pem 8050
```

## 📚 Documentation

For detailed information, see:

1. **SETUP_CHECKLIST.md** - Complete setup guide
2. **DEPLOYMENT.md** - Detailed deployment documentation
3. **DEPLOYMENT_QUICK_REF.md** - Quick reference card

## ⚡ Performance Tips

1. **Use t2.medium or larger** for good performance
2. **Enable Gzip compression** in Nginx
3. **Monitor resource usage** regularly
4. **Update dependencies** monthly
5. **Use CloudWatch** for monitoring
6. **Set up alarms** for critical metrics

## 🆘 Getting Help

1. Check troubleshooting section above
2. Review `DEPLOYMENT.md` for detailed help
3. Check application logs: `./ec2-manage.sh logs`
4. Check Nginx logs: `./ec2-manage.sh nginx-logs`
5. Test connectivity: `curl -v http://YOUR_EC2_IP`

## 📋 Requirements

### Local Machine
- Windows 10+ or macOS 10.15+ or Linux
- AWS CLI v2
- Git
- SSH client
- PowerShell 5.1+ (Windows) or Bash (macOS/Linux)

### AWS
- AWS account
- EC2 instance (t2.medium or larger)
- 20GB+ storage
- Security group with SSH access
- IAM user with EC2 permissions

### GitHub (optional)
- GitHub account
- Repository with proper secrets

## 📄 License

This deployment system is part of the Resulam Royalties Dashboard project.

## 🎉 What's Next?

1. Follow SETUP_CHECKLIST.md to prepare your environment
2. Run the deployment script
3. Access your dashboard at `http://YOUR_EC2_IP`
4. Use `ec2-manage.sh` for ongoing management
5. Set up GitHub Actions for automated deployments

---

**Version:** 1.0.0
**Last Updated:** December 10, 2024
**Support:** See DEPLOYMENT.md for comprehensive documentation
