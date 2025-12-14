# 🚀 RESULAM ROYALTIES DEPLOYMENT - QUICK REFERENCE

## ONE-LINE DEPLOY
```powershell
cd C:\Users\tcham\Wokspace\resulam_royalties; python scripts/deploy/deploy.py
```

## What the Script Does (Automatic)
- ✅ Validates AWS credentials
- ✅ Finds available port on EC2
- ✅ Updates GitHub secrets
- ✅ SSH to EC2 instance
- ✅ Installs system dependencies (Python, Nginx, etc.)
- ✅ Clones/updates your repository
- ✅ Creates virtual environment
- ✅ Installs Python packages
- ✅ Configures Nginx reverse proxy
- ✅ Sets up systemd service
- ✅ Starts application
- ✅ Updates AWS security group

## Access Your App
```
🌐 http://18.208.117.82
```

## Common Commands

### SSH to EC2
```powershell
ssh -i "C:\path\to\key.pem" ec2-user@18.208.117.82
```

### View Application Logs
```bash
sudo journalctl -u resulam-royalties -f
```

### Restart Application
```bash
sudo systemctl restart resulam-royalties
```

### Check Service Status
```bash
sudo systemctl status resulam-royalties
```

### Update Application (Pull Latest)
```bash
cd /home/ec2-user/resulam-royalties
git pull origin main
sudo systemctl restart resulam-royalties
```

## Troubleshooting

### Application won't load
```bash
# Check logs
sudo journalctl -u resulam-royalties -n 50

# Restart service
sudo systemctl restart resulam-royalties
```

### Page shows "502 Bad Gateway"
```bash
# Verify Dash is running
curl http://127.0.0.1:8050

# Check Nginx error log
sudo tail -f /var/log/nginx/error.log
```

### Port already in use
```bash
# Find what's using the port
sudo netstat -tuln | grep :8050

# Kill process
sudo kill -9 <PID>

# Restart service
sudo systemctl restart resulam-royalties
```

## GitHub Secrets Set
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`
- `DEPLOY_PORT`
- `EC2_HOST`

(These are automatically set by the deployment script)

## Architecture
```
┌─────────────────────────────────────────┐
│  Browser at http://18.208.117.82        │
└────────────────┬────────────────────────┘
                 │ HTTP
                 ▼
┌─────────────────────────────────────────┐
│  Nginx Reverse Proxy (Port 80)          │
│  /etc/nginx/conf.d/resulam-royalties.cf │
└────────────────┬────────────────────────┘
                 │ Proxy Pass
                 ▼
┌─────────────────────────────────────────┐
│  Dash Application (Port 8050+)          │
│  /home/ec2-user/resulam-royalties/      │
│  Systemd: resulam-royalties.service     │
└─────────────────────────────────────────┘
```

## Deploy Variables
| Variable | Default | Location |
|----------|---------|----------|
| EC2 IP | 18.208.117.82 | Parameter or auto-detect |
| SSH User | ec2-user | Parameter |
| SSH Key | Auto-detect | ~/.ssh/ directory |
| App Port | 8050+ | Auto-detect (free port) |
| Repository | tchamna/resulam_royalties | Parameter |

## Notes
- Script requires AWS CLI configured
- SSH key must have correct permissions (chmod 400)
- First deployment takes 2-3 minutes
- Application starts automatically after reboot
- All logs stored in systemd journal

---
For full documentation, see: `DEPLOYMENT.md`
