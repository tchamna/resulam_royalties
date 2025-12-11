#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal EC2 Deployment Script
Self-contained deployment for any GitHub repository with automated setup.
Handles: Repository cloning, venv setup, S3 data sync, systemd service, nginx proxy, and HTTPS.

Configuration Parameters:
- EC2_IP: EC2 instance IP address
- EC2_USER: SSH user on EC2 instance
- SSH_KEY: Local path to SSH private key
- GIT_REPO: GitHub repository URL (https://github.com/user/repo.git)
- APP_PORT: Public port (typically 8050)
- APP_DIR: Remote app directory path
- S3_BUCKET: S3 bucket name for data files (optional)
- AWS_REGION: AWS region
- DOMAIN_NAME: Domain name for HTTPS
"""

import subprocess
import sys
import os
import json
from datetime import datetime
from urllib.parse import urlparse

# ============================================================================
# CONFIGURATION - Read from environment variables or defaults
# ============================================================================

def load_env_file(env_file='.env'):
    """Load environment variables from .env file into os.environ"""
    if not os.path.exists(env_file):
        return
    
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value
    except Exception as e:
        print(f"⚠️  Warning: Could not read {env_file}: {e}")

# Load .env file at startup (before reading environment variables)
load_env_file('.env')

def get_env(key, default=None, required=False):
    """Get environment variable with optional default and validation"""
    value = os.getenv(key, default)
    if required and not value:
        print(f"❌ ERROR: Required environment variable '{key}' not set")
        print(f"   Set it with: export {key}=value")
        sys.exit(1)
    return value

# Support both GitHub Secrets naming (EC2_HOST, EC2_SSH_KEY) and custom naming (EC2_IP, SSH_KEY_PATH)
EC2_IP = get_env("EC2_IP") or get_env("EC2_HOST")
EC2_USER = get_env("EC2_USER")
SSH_KEY_PATH = get_env("SSH_KEY_PATH") or get_env("EC2_SSH_KEY")
GIT_REPO_RAW = get_env("GIT_REPO")
# Handle both full URLs and GitHub short format (owner/repo)
if GIT_REPO_RAW and not GIT_REPO_RAW.startswith("http"):
    GIT_REPO = f"https://github.com/{GIT_REPO_RAW}.git"
else:
    GIT_REPO = GIT_REPO_RAW
APP_PORT = int(get_env("APP_PORT") or "8050")
APP_DIR = get_env("APP_DIR")
S3_BUCKET = get_env("S3_BUCKET")
AWS_REGION = get_env("AWS_REGION") or "us-east-1"
DOMAIN_NAME = get_env("DOMAIN_NAME")
AWS_ACCESS_KEY_ID = get_env("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = get_env("AWS_SECRET_ACCESS_KEY")

# Optional: S3 data files to download (pipe-separated)
# Can be set via: export S3_DATA_FILES="file1.csv|file2.xlsx"
S3_DATA_FILES_ENV = get_env("S3_DATA_FILES", "")
if S3_DATA_FILES_ENV:
    S3_DATA_FILES = S3_DATA_FILES_ENV.split("|")
else:
    S3_DATA_FILES = []

# Optional: Python packages (pipe-separated, or leave empty to use requirements.txt)
# Can be set via: export PYTHON_PACKAGES="package1==1.0|package2==2.0"
PYTHON_PACKAGES_ENV = get_env("PYTHON_PACKAGES", "")
if PYTHON_PACKAGES_ENV:
    PYTHON_PACKAGES = PYTHON_PACKAGES_ENV.split("|")
else:
    PYTHON_PACKAGES = []

# ============================================================================
# DERIVED CONFIGURATION
# ============================================================================

CURRENT_YEAR = datetime.now().year
APP_NAME = os.path.basename(urlparse(GIT_REPO).path).replace(".git", "")
SYSTEMD_SERVICE = f"{APP_NAME}.service"
NGINX_CONFIG = f"/etc/nginx/conf.d/{APP_NAME}.conf"

def print_config():
    """Display configuration with sources"""
    print("\n" + "="*70)
    print("DEPLOYMENT CONFIGURATION")
    print("="*70)
    print(f"\n📋 Configuration Sources:")
    print(f"   • Environment variables (if set)")
    print(f"   • Local defaults (fallback)")
    print(f"\n🔧 Active Configuration:")
    print(f"   EC2_IP:              {EC2_IP}")
    print(f"   EC2_USER:            {EC2_USER}")
    print(f"   SSH_KEY_PATH:        {SSH_KEY_PATH}")
    print(f"   GIT_REPO:            {GIT_REPO}")
    print(f"   APP_NAME:            {APP_NAME}")
    print(f"   APP_PORT:            {APP_PORT}")
    print(f"   APP_DIR:             {APP_DIR}")
    print(f"   DOMAIN_NAME:         {DOMAIN_NAME}")
    print(f"   S3_BUCKET:           {S3_BUCKET}")
    print(f"   AWS_REGION:          {AWS_REGION}")
    if S3_DATA_FILES:
        print(f"   S3_DATA_FILES:       {', '.join(S3_DATA_FILES)}")
    else:
        print(f"   S3_DATA_FILES:       (none, will skip S3 download)")
    if PYTHON_PACKAGES:
        print(f"   PYTHON_PACKAGES:     {', '.join(PYTHON_PACKAGES[:2])}...")
    else:
        print(f"   PYTHON_PACKAGES:     (will use requirements.txt)")
    print("\n" + "="*70 + "\n")

def ssh(cmd):
    """Execute command on EC2 via SSH"""
    result = subprocess.run(
        ['ssh', '-i', SSH_KEY_PATH, '-o', 'StrictHostKeyChecking=no', 
         f'{EC2_USER}@{EC2_IP}', cmd],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60
    )
    return result.returncode == 0, result.stdout, result.stderr

def configure_security_group():
    """Configure AWS security group to allow port 8050"""
    try:
        # Try to find instance and security group - use a simpler query
        cmd = f'aws ec2 describe-instances --filters "Name=instance-state-name,Values=running" --region {AWS_REGION} --query "Reservations[0].Instances[0].[InstanceId,SecurityGroups[0].GroupId]" --output text'
        success, result, err = ssh(cmd)
        
        if not success or not result.strip():
            return False
        
        parts = result.strip().split()
        if len(parts) < 2:
            return False
        
        instance_id = parts[0]
        sg_id = parts[1]
        
        # List all rules to check if 8050 exists
        cmd = f'aws ec2 describe-security-groups --group-ids {sg_id} --region {AWS_REGION} --query "SecurityGroups[0].IpPermissions[*].FromPort" --output text'
        success, ports_str, err = ssh(cmd)
        
        ports = ports_str.strip().split() if success and ports_str.strip() else []
        
        # Check if port 8050 is NOT in the list
        if success and '8050' not in ports:
            # Add the rule
            cmd = (f'aws ec2 authorize-security-group-ingress --group-id {sg_id} '
                   f'--protocol tcp --port {APP_PORT} --cidr 0.0.0.0/0 '
                   f'--region {AWS_REGION}')
            auth_success, out, err = ssh(cmd)
            if auth_success:
                print(f"✓ Security group ({sg_id}) - port {APP_PORT} authorized")
                return True
            else:
                if 'Duplicate' in err or 'already exists' in err.lower():
                    print(f"✓ Port {APP_PORT} already authorized")
                    return True
                else:
                    print(f"⚠ Could not authorize port {APP_PORT}: {err[:60]}")
                    return False
        else:
            print(f"✓ Port {APP_PORT} already authorized")
            return True
            
    except Exception as e:
        return False

def configure_https():
    """Configure HTTPS with Let's Encrypt and Certbot"""
    try:
        # Install certbot and nginx plugin
        cmd = "sudo yum install -y certbot python3-certbot-nginx"
        success, out, err = ssh(cmd)
        if not success:
            print(f"⚠ Could not install certbot: {err[:60]}")
            return False
        
        print(f"  Certbot installed.")
        print(f"  To obtain SSL certificate for {DOMAIN_NAME}:")
        print(f"  1. Ensure DNS points {DOMAIN_NAME} → {EC2_IP}")
        print(f"  2. SSH to instance:")
        print(f"     ssh -i {SSH_KEY_PATH} {EC2_USER}@{EC2_IP}")
        print(f"  3. Run Certbot:")
        print(f"     sudo certbot --nginx -d {DOMAIN_NAME}")
        print(f"  4. Follow prompts to set up HTTPS")
        print(f"")
        print(f"  Certbot will auto-renew certificates (runs daily).")
        return True
        
    except Exception as e:
        print(f"⚠ HTTPS configuration warning: {e}")
        return True  # Don't fail deployment

def deploy():
    print("\n" + "="*60)
    print("UNIVERSAL EC2 DEPLOYMENT")
    print("="*60)
    print_config()
    
    # Step 0: Configure AWS Security Group
    print("Step 0: Configuring AWS security group...")
    sg_result = configure_security_group()
    if not sg_result:
        print("⚠ MANUAL STEP REQUIRED:")
        print("  Please add an inbound rule to your EC2 security group:")
        print("  - Type: Custom TCP")
        print("  - Protocol: TCP")
        print("  - Port: 8050")
        print("  - Source: 0.0.0.0/0")
        print("  After adding the rule, the app will be accessible.")
        print("")
    
    # Step 1: Clone/update repository
    print("Step 1: Setting up repository...")
    cmd = (f"mkdir -p /home/{EC2_USER}/apps && cd /home/{EC2_USER}/apps && "
           f"if [ -d {APP_NAME} ]; then cd {APP_NAME} && git pull origin main 2>&1 | grep -v 'Already up'; "
           f"else git clone {GIT_REPO} {APP_NAME}; fi")
    success, out, err = ssh(cmd)
    if not success and APP_NAME not in out:
        print(f"✗ ERROR: {err}")
        return False
    print(f"✓ Repository {APP_NAME} ready")
    
    # Step 2: Setup Python venv and install dependencies
    print("\nStep 2: Setting up Python environment...")
    cmd = (f"cd {APP_DIR} && "
           f"if [ ! -d venv ]; then python3 -m venv venv; fi && "
           f"source venv/bin/activate && "
           f"pip install -q --upgrade pip setuptools wheel && "
           f"pip install -q --no-cache-dir --upgrade numpy pandas")
    
    # Install from requirements.txt if it exists
    cmd += f" && if [ -f requirements.txt ]; then pip install -q --no-cache-dir -r requirements.txt; fi"
    
    # Install additional packages if specified
    if PYTHON_PACKAGES:
        packages_list = " ".join(PYTHON_PACKAGES)
        cmd += f" && pip install -q --no-cache-dir {packages_list}"
    
    success, out, err = ssh(cmd)
    if not success:
        print(f"✗ ERROR: {err}")
        return False
    print("✓ Python environment ready with dependencies")
    
    # Step 3: Download data files from S3 (optional)
    print("\nStep 3: Handling data files...")
    if S3_DATA_FILES:
        print("  Downloading data files from S3...")
        cmd = (f"cd {APP_DIR} && "
               f"mkdir -p data && "
               f"pip install -q boto3 && "
               f"python3 << 'ENDS3'\n"
               f"import boto3\n"
               f"import os\n"
               f"os.makedirs('data', exist_ok=True)\n"
               f"s3 = boto3.client('s3', region_name='{AWS_REGION}')\n"
               f"files_to_download = [\n")
        for file in S3_DATA_FILES:
            cmd += f"    ('{file}', 'data/{file}'),\n"
        cmd += (f"]\n"
               f"for src, dst in files_to_download:\n"
               f"    try:\n"
               f"        s3.download_file('{S3_BUCKET}', src, dst)\n"
               f"        print(f'Downloaded {{src}} to {{dst}}')\n"
               f"    except Exception as e:\n"
               f"        print(f'Warning: Could not download {{src}}: {{e}}')\n"
               f"ENDS3")
        success, out, err = ssh(cmd)
        if not success:
            print(f"  ⚠ Warning: S3 download failed or skipped")
        else:
            print("  ✓ Data files downloaded from S3")
    else:
        print("  ⚠ Skipped: No S3 data files configured")
    
    # Step 4: Create systemd service with S3 environment
    print("\nStep 4: Creating systemd service...")
    service_template = """[Unit]
Description={app_name} Dashboard
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory={app_dir}
Environment="PATH={app_dir}/venv/bin"
Environment="PYTHONPATH={app_dir}"
Environment="USE_S3_DATA=true"
Environment="S3_BUCKET={s3_bucket}"
Environment="AWS_DEFAULT_REGION={aws_region}"
ExecStart={app_dir}/venv/bin/python main.py --host 127.0.0.1 --port 8051
Restart=always
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
""".format(app_name=APP_NAME, app_dir=APP_DIR, s3_bucket=S3_BUCKET, aws_region=AWS_REGION)
    
    # Write service file using heredoc
    cmd = (f"cat > /tmp/{APP_NAME}.service << 'ENDSERVICE'\n"
           f"{service_template}\n"
           f"ENDSERVICE\n"
           f"sudo mv /tmp/{APP_NAME}.service /etc/systemd/system/{SYSTEMD_SERVICE} && "
           f"sudo chmod 644 /etc/systemd/system/{SYSTEMD_SERVICE}")
    success, out, err = ssh(cmd)
    if not success:
        print(f"✗ ERROR: {err}")
        return False
    print(f"✓ Systemd service {SYSTEMD_SERVICE} created")
    
    # Step 5: Create nginx configuration
    print("\nStep 5: Configuring nginx...")
    nginx_template = """upstream {app_name}_upstream {{
    server 127.0.0.1:8051;
}}

# HTTP server block
server {{
    listen 80;
    server_name {domain};
    client_max_body_size 50M;

    # For Let's Encrypt validation
    location /.well-known/acme-challenge/ {{
        root /var/www/certbot;
    }}

    # Serve app over HTTP
    location / {{
        proxy_pass http://{app_name}_upstream;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto http;
        proxy_read_timeout 120s;
    }}
}}

# HTTPS server block (uncomment after running certbot)
# server {{
#     listen 443 ssl http2;
#     server_name {domain};
#     client_max_body_size 50M;
#
#     ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
#     ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
#     ssl_protocols TLSv1.2 TLSv1.3;
#     ssl_ciphers HIGH:!aNULL:!MD5;
#     ssl_prefer_server_ciphers on;
#     ssl_session_cache shared:SSL:10m;
#     ssl_session_timeout 10m;
#
#     location / {{
#         proxy_pass http://{app_name}_upstream;
#         proxy_http_version 1.1;
#         proxy_set_header Host $host;
#         proxy_set_header X-Real-IP $remote_addr;
#         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#         proxy_set_header X-Forwarded-Proto https;
#         proxy_read_timeout 120s;
#     }}
# }}
#
# # Redirect HTTP to HTTPS
# server {{
#     listen 80;
#     server_name {domain};
#     return 301 https://$host$request_uri;
# }}
""".format(app_name=APP_NAME, domain=DOMAIN_NAME)
    
    cmd = (f"cat > /tmp/{APP_NAME}.conf << 'ENDNGINX'\n"
           f"{nginx_template}\n"
           f"ENDNGINX\n"
           f"sudo mv /tmp/{APP_NAME}.conf {NGINX_CONFIG}")
    success, out, err = ssh(cmd)
    if not success:
        print(f"✗ ERROR writing nginx config: {err}")
        return False
    
    # Test nginx config
    cmd = "sudo nginx -t"
    success, out, err = ssh(cmd)
    # Nginx test succeeds if it contains "ok" or "successful", ignore warnings
    print("✓ Nginx configured for port {0}".format(APP_PORT))
    
    # Step 6: Reload systemd and start service
    print("\nStep 6: Starting service...")
    cmd = (f"sudo systemctl daemon-reload && "
           f"sudo systemctl enable {SYSTEMD_SERVICE} && "
           f"sudo systemctl restart {SYSTEMD_SERVICE} && "
           f"sleep 2")
    success, out, err = ssh(cmd)
    
    # Check if service is running
    cmd = f"sudo systemctl is-active {SYSTEMD_SERVICE}"
    success, out, err = ssh(cmd)
    if success:
        print("✓ Service started successfully")
    else:
        print("⚠ Service may not have started. Checking logs...")
        cmd = f"sudo journalctl -u {SYSTEMD_SERVICE} -n 15 --no-pager"
        success, logs, _ = ssh(cmd)
        if logs:
            print(logs[-400:] if len(logs) > 400 else logs)
        else:
            print("(No logs available)")
    
    # Step 7: Restart nginx
    print("\nStep 7: Restarting nginx...")
    cmd = "sudo systemctl restart nginx && sleep 1"
    success, out, err = ssh(cmd)
    if not success:
        print(f"✗ ERROR: {err}")
        return False
    print("✓ Nginx restarted")
    
    # Step 8: Configure HTTPS (optional)
    print("\nStep 8: Setting up HTTPS support...")
    configure_https()
    
    # Step 9: Verify app is responding
    print("\nStep 9: Verifying deployment...")
    cmd = "curl -s http://localhost:{0} 2>&1 | head -1".format(APP_PORT)
    success, out, err = ssh(cmd)
    if success and out.strip():
        print("✓ Application responding on port {0}".format(APP_PORT))
    
    # Summary
    print("\n" + "="*60)
    print("✓ DEPLOYMENT COMPLETE")
    print("="*60)
    print("\n📍 ACCESS YOUR APP:")
    print("   HTTP:  http://{0}".format(DOMAIN_NAME))
    print("   HTTPS: (configure with certbot below)")
    print("\n🔒 SETUP HTTPS (Let's Encrypt):")
    print("   1. Ensure DNS resolves: {0} → {1}".format(DOMAIN_NAME, EC2_IP))
    print("   2. SSH to EC2:")
    print("      ssh -i {0} {1}@{2}".format(SSH_KEY_PATH, EC2_USER, EC2_IP))
    print("   3. Run Certbot:")
    print("      sudo certbot --nginx -d {0}".format(DOMAIN_NAME))
    print("   4. Select redirect HTTP→HTTPS when prompted")
    print("   5. Certificates auto-renew daily")
    print("\n📋 CONFIGURATION:")
    print("   Repository:     {0}".format(GIT_REPO))
    print("   App Name:       {0}".format(APP_NAME))
    print("   Domain:         {0}".format(DOMAIN_NAME))
    print("   App Directory:  {0}".format(APP_DIR))
    print("   Service Name:   {0}".format(SYSTEMD_SERVICE))
    print("   Nginx Config:   {0}".format(NGINX_CONFIG))
    print("   Internal Port:  8051 (127.0.0.1)")
    print("   Public Port:    80/443 (via nginx)")
    print("   PYTHONPATH:     {0}".format(APP_DIR))
    print("   Venv:           {0}/venv".format(APP_DIR))
    print("\n💡 MANAGE SERVICE:")
    print("   ssh -i {0} {1}@{2}".format(SSH_KEY_PATH, EC2_USER, EC2_IP))
    print("   sudo systemctl status {0}".format(SYSTEMD_SERVICE))
    print("   sudo systemctl restart {0}".format(SYSTEMD_SERVICE))
    print("   sudo journalctl -u {0} -f".format(SYSTEMD_SERVICE))
    print("\n📜 CERTBOT COMMANDS:")
    print("   sudo certbot renew --dry-run  # Test auto-renewal")
    print("   sudo certbot certificates     # View installed certs")
    print("   sudo certbot revoke --cert-name {0}  # Revoke cert".format(DOMAIN_NAME))
    print("\n")
    
    return True

def setup_github_secrets(env_file='.env'):
    """Setup GitHub repository secrets from environment variables or .env file"""
    try:
        print("\n🔐 Setting up GitHub Secrets")
        print("=" * 70)
        
        # Environment variables already loaded from .env at startup
        
        # Check if gh CLI is available
        result = subprocess.run(['gh', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ GitHub CLI (gh) not installed. Install from: https://cli.github.com")
            return False
        
        print("✅ GitHub CLI found")
        
        # Get repository info
        result = subprocess.run(['git', 'config', '--get', 'remote.origin.url'], 
                                capture_output=True, text=True, cwd='.')
        if result.returncode != 0:
            print("❌ Not in a git repository")
            return False
        
        repo_url = result.stdout.strip()
        # Extract owner/repo from URL
        if 'github.com' not in repo_url:
            print("❌ Not a GitHub repository")
            return False
        
        repo = repo_url.split('/')[-1].replace('.git', '')
        owner = repo_url.split('/')[-2]
        full_repo = f"{owner}/{repo}"
        
        print(f"📦 Repository: {full_repo}")
        
        # Map environment variables to GitHub secrets
        secrets_map = {
            "EC2_HOST": EC2_IP,
            "EC2_USER": EC2_USER,
            "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
            "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
            "DOMAIN_NAME": DOMAIN_NAME,
            "S3_BUCKET": S3_BUCKET,
            "APP_DIR": APP_DIR,
            "AWS_DEFAULT_REGION": AWS_REGION,
        }
        
        # Handle EC2_SSH_KEY - load from file if path provided
        ssh_key_content = SSH_KEY_PATH
        if SSH_KEY_PATH and os.path.exists(SSH_KEY_PATH):
            try:
                with open(SSH_KEY_PATH, 'r') as f:
                    ssh_key_content = f.read()
                print(f"📁 Loaded SSH key from: {SSH_KEY_PATH}")
            except Exception as e:
                print(f"⚠️  Could not read SSH key from {SSH_KEY_PATH}: {e}")
        
        secrets_map["EC2_SSH_KEY"] = ssh_key_content
        
        print(f"\n📝 Setting up {len(secrets_map)} secrets...\n")
        
        success_count = 0
        fail_count = 0
        
        for secret_name, secret_value in secrets_map.items():
            if not secret_value:
                print(f"⏭️  Skipping {secret_name} (empty)")
                continue
            
            # Set secret using gh CLI
            try:
                # Use echo with pipe to set secret
                process = subprocess.Popen(['gh', 'secret', 'set', secret_name, 
                                           '--repo', full_repo],
                                          stdin=subprocess.PIPE, 
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE,
                                          text=True)
                stdout, stderr = process.communicate(input=str(secret_value), timeout=10)
                
                if process.returncode == 0:
                    print(f"✅ {secret_name}")
                    success_count += 1
                else:
                    print(f"❌ {secret_name}: {stderr.strip()[:80]}")
                    fail_count += 1
            except Exception as e:
                print(f"❌ {secret_name}: {str(e)[:80]}")
                fail_count += 1
        
        print("\n" + "=" * 70)
        print(f"✅ GitHub Secrets Setup Complete")
        print(f"   Successful: {success_count}")
        print(f"   Failed: {fail_count}")
        print(f"\n📋 To verify, run:")
        print(f"   gh secret list --repo {full_repo}")
        
        return fail_count == 0
        
    except Exception as e:
        print(f"❌ Error setting up GitHub secrets: {e}")
        return False

if __name__ == '__main__':
    try:
        # Check for --setup-secrets flag
        if '--setup-secrets' in sys.argv:
            success = setup_github_secrets('.env')
            sys.exit(0 if success else 1)
        
        # Check for --all flag (setup secrets + deploy)
        if '--all' in sys.argv:
            print("\n🚀 Full Setup: GitHub Secrets + Deployment\n")
            secrets_ok = setup_github_secrets('.env')
            if not secrets_ok:
                print("\n⚠️  GitHub secrets setup had issues, but continuing with deployment...")
            print("\n" + "=" * 70)
            success = deploy()
            sys.exit(0 if success else 1)
        
        success = deploy()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n✗ Deployment cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        sys.exit(1)
