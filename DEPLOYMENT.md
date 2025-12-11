# 🚀 Resulam Royalties Dashboard - EC2 Deployment Guide

## Quick Start

### Prerequisites
Before deploying, ensure you have:

1. **AWS CLI v2** installed
   - Download: https://aws.amazon.com/cli/
   - Verify: `aws --version`

2. **AWS Credentials configured**
   - Run: `aws configure`
   - Requires AWS Access Key ID and Secret Access Key

3. **SSH Key (.pem file)**
   - Should be stored in `~/.ssh/` directory
   - Example: `~/.ssh/ec2-key.pem`
   - Permissions: `chmod 400 your-key.pem`

4. **Git installed**
   - Verify: `git --version`

5. **GitHub CLI (optional but recommended)**
   - Download: https://cli.github.com/
   - Used to automatically update GitHub secrets

### One-Command Deployment

```powershell
# Navigate to project root
cd C:\Users\tcham\Wokspace\resulam_royalties

# Run deployment script
.\deploy.ps1
```

The script will automatically:
- ✅ Validate AWS credentials
- ✅ Find an available port on EC2
- ✅ Update GitHub secrets
- ✅ SSH to your EC2 instance
- ✅ Install system dependencies
- ✅ Clone/update your repository
- ✅ Create Python virtual environment
- ✅ Install Python dependencies
- ✅ Configure Nginx reverse proxy
- ✅ Set up systemd service
- ✅ Start the application
- ✅ Update AWS Security Group

## Advanced Usage

### Custom Parameters

```powershell
# Use specific EC2 IP, user, and key
.\deploy.ps1 -EC2_IP "18.208.117.82" -EC2_User "ec2-user" -KeyPath "C:\path\to\key.pem" -StartPort 8050

# Use custom GitHub repository
.\deploy.ps1 -Repository "your-username/your-repo"
```

### Parameter Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `EC2_IP` | `18.208.117.82` | EC2 instance public IP address |
| `EC2_User` | `ec2-user` | SSH username (ec2-user for Amazon Linux 2, ubuntu for Ubuntu) |
| `KeyPath` | `(auto-detect)` | Path to SSH private key (.pem file) |
| `StartPort` | `8050` | Starting port to search for availability |
| `Repository` | `tchamna/resulam_royalties` | GitHub repository (owner/repo) |

## What Gets Deployed

### Directory Structure (on EC2)
```
/home/ec2-user/resulam-royalties/
├── main.py
├── requirements.txt
├── src/
│   ├── dashboard/
│   ├── data/
│   ├── config.py
│   └── ...
└── venv/                    # Python virtual environment
```

### Services Configured

#### 1. Systemd Service: `resulam-royalties`
```bash
# View status
sudo systemctl status resulam-royalties

# View logs
sudo journalctl -u resulam-royalties -f

# Restart service
sudo systemctl restart resulam-royalties

# Stop service
sudo systemctl stop resulam-royalties
```

#### 2. Nginx Reverse Proxy
```
Client -> Port 80 (Nginx) -> Port 8050+ (Application)
```

Configuration file: `/etc/nginx/conf.d/resulam-royalties.conf`

Features:
- ✅ HTTP/1.1 upgrade support (for Dash WebSockets)
- ✅ Large file uploads (50MB limit)
- ✅ Request logging
- ✅ Connection pooling
- ✅ 120s timeout for long operations

## After Deployment

### 1. Verify the Application is Running

```powershell
# From your local machine
curl http://18.208.117.82
# OR
Start-Process "http://18.208.117.82"
```

### 2. Check Application Logs

```bash
# SSH to instance
ssh -i "C:\path\to\key.pem" ec2-user@18.208.117.82

# View application logs
sudo journalctl -u resulam-royalties -n 100 --no-pager

# Follow logs in real-time
sudo journalctl -u resulam-royalties -f
```

### 3. Check Nginx Logs

```bash
# Error logs
sudo tail -f /var/log/nginx/error.log

# Access logs
sudo tail -f /var/log/nginx/access.log
```

### 4. Test Port Connectivity

```bash
# Check if port 80 is listening
netstat -tuln | grep :80

# Check if Dash is running on its port
netstat -tuln | grep :8050
```

## Troubleshooting

### Application won't start

1. **Check service status:**
   ```bash
   sudo systemctl status resulam-royalties
   ```

2. **View last 50 lines of logs:**
   ```bash
   sudo journalctl -u resulam-royalties -n 50
   ```

3. **Check Python errors:**
   ```bash
   sudo su -s /bin/bash ec2-user -c "source /home/ec2-user/resulam-royalties/venv/bin/activate && python -m py_compile /home/ec2-user/resulam-royalties/main.py"
   ```

### Nginx shows 502 Bad Gateway

1. **Verify Dash is running:**
   ```bash
   curl http://127.0.0.1:8050
   ```

2. **Restart Dash service:**
   ```bash
   sudo systemctl restart resulam-royalties
   sleep 5
   sudo systemctl status resulam-royalties
   ```

3. **Check Nginx configuration:**
   ```bash
   sudo nginx -t
   ```

### Port is already in use

The script automatically finds an available port. If manual intervention is needed:

```bash
# Find what's using a port
sudo netstat -tuln | grep :<port_number>

# Kill process using the port
sudo kill -9 <PID>

# Then restart the service
sudo systemctl restart resulam-royalties
```

### SSH connection denied

1. **Verify key permissions:**
   ```powershell
   # On Windows, check NTFS permissions
   icacls "C:\path\to\key.pem"
   ```

2. **Verify EC2 security group allows SSH (port 22)**

3. **Try verbose connection:**
   ```powershell
   ssh -i "key.pem" -vvv ec2-user@18.208.117.82
   ```

## GitHub Secrets

The script automatically sets these secrets in your GitHub repository:

| Secret | Value |
|--------|-------|
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AWS_DEFAULT_REGION` | AWS region (us-east-1) |
| `DEPLOY_PORT` | Assigned application port |
| `EC2_HOST` | EC2 instance IP address |

These secrets can be used in GitHub Actions workflows for automated CI/CD.

## Security Best Practices

### 1. SSH Key Protection
```bash
# Set correct permissions (read-only for owner)
chmod 400 ~/.ssh/ec2-key.pem
```

### 2. Security Group Restrictions
```bash
# Instead of 0.0.0.0/0, restrict to your IP
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxx \
    --protocol tcp \
    --port 80 \
    --cidr YOUR_IP/32
```

### 3. Enable HTTPS with Let's Encrypt
```bash
# SSH to instance
ssh -i "key.pem" ec2-user@18.208.117.82

# Install Certbot
sudo yum install -y certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Certbot auto-renews certificates
```

### 4. Environment Variables
```bash
# SSH to instance
ssh -i "key.pem" ec2-user@18.208.117.82

# Edit systemd service
sudo nano /etc/systemd/system/resulam-royalties.service

# Add under [Service]:
# Environment="VARIABLE_NAME=value"

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart resulam-royalties
```

## Monitoring and Maintenance

### 1. Monitor Application Health
```bash
# Check service is running
ssh -i "key.pem" ec2-user@18.208.117.82 'sudo systemctl status resulam-royalties'

# Check response time
time curl -s http://18.208.117.82/health

# Monitor real-time logs
ssh -i "key.pem" ec2-user@18.208.117.82 'sudo journalctl -u resulam-royalties -f'
```

### 2. Update Application
```bash
# SSH to instance
ssh -i "key.pem" ec2-user@18.208.117.82

# Navigate to app directory
cd /home/ec2-user/resulam-royalties

# Pull latest changes
git pull origin main

# Restart service
sudo systemctl restart resulam-royalties
```

### 3. View System Resources
```bash
# CPU and Memory usage
ssh -i "key.pem" ec2-user@18.208.117.82 'top -bn1 | head -20'

# Disk usage
ssh -i "key.pem" ec2-user@18.208.117.82 'df -h'
```

## Redeployment

To redeploy with updated code:

```powershell
# Pull latest changes locally
git pull origin main

# Run deployment script again
.\deploy.ps1
```

The script will:
1. SSH to EC2
2. Pull latest code from git
3. Reinstall dependencies
4. Restart the service

## Rollback

If deployment causes issues:

```bash
# SSH to instance
ssh -i "key.pem" ec2-user@18.208.117.82

# Check git log to see recent commits
cd /home/ec2-user/resulam-royalties
git log --oneline -10

# Revert to specific commit
git revert <commit-hash>
# OR reset to previous version
git reset --hard HEAD~1

# Restart service
sudo systemctl restart resulam-royalties
```

## Performance Optimization

### 1. Enable Gzip Compression
```bash
# SSH to instance
sudo nano /etc/nginx/conf.d/resulam-royalties.conf

# Add under server block:
# gzip on;
# gzip_types text/plain text/css text/javascript application/json;

sudo nginx -t
sudo systemctl restart nginx
```

### 2. Increase Worker Connections
```bash
sudo nano /etc/nginx/nginx.conf

# Change:
# worker_connections 1024;
# to:
# worker_connections 2048;

sudo nginx -t
sudo systemctl restart nginx
```

### 3. Monitor with CloudWatch
See AWS documentation for setting up CloudWatch monitoring and alarms.

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review logs: `sudo journalctl -u resulam-royalties -n 100`
3. Verify configuration: `sudo nginx -t`
4. Check AWS security groups in console
5. Test connectivity: `curl -v http://18.208.117.82`

## Files Generated/Modified

By running this deployment script:

**Local (on your machine):**
- `./deploy.ps1` - Main deployment script
- `./requirements.txt` - Python dependencies

**On EC2 instance (automatic):**
- `/home/ec2-user/resulam-royalties/` - Application directory
- `/home/ec2-user/resulam-royalties/venv/` - Python virtual environment
- `/etc/systemd/system/resulam-royalties.service` - Systemd service file
- `/etc/nginx/conf.d/resulam-royalties.conf` - Nginx configuration
- `/var/log/nginx/` - Nginx logs
- `/var/log/journal/` - Application logs (via systemd)

---

**Last Updated:** December 10, 2024
**Version:** 1.0.0
