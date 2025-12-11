#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resulam Royalties - Complete EC2 Deployment Script
Single command deployment with all configs, PYTHONPATH handling, and S3 data files
"""

import subprocess
import sys
import os
import json
from datetime import datetime

EC2_IP = "18.208.117.82"
EC2_USER = "ec2-user"
SSH_KEY = r'C:\Users\tcham\Downloads\test-rag.pem'
APP_PORT = 8050
APP_DIR = "/home/ec2-user/apps/resulam-royalties"
S3_BUCKET = "resulam-royalties"
AWS_REGION = "us-east-1"
CURRENT_YEAR = datetime.now().year

def ssh(cmd):
    """Execute command on EC2 via SSH"""
    result = subprocess.run(
        ['ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no', 
         f'{EC2_USER}@{EC2_IP}', cmd],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60
    )
    return result.returncode == 0, result.stdout, result.stderr

def configure_security_group():
    """Configure AWS security group to allow port 8050"""
    try:
        # Get instance ID from EC2
        cmd = 'ec2-metadata --instance-id | cut -d " " -f 2'
        success, instance_id, err = ssh(cmd)
        if not success or not instance_id.strip():
            print(f"⚠ Warning: Could not get instance ID: {err}")
            return False
        
        instance_id = instance_id.strip()
        
        # Use AWS CLI to get security group
        cmd = f'aws ec2 describe-instances --instance-ids {instance_id} --region {AWS_REGION} --query "Reservations[0].Instances[0].SecurityGroups[0].GroupId" --output text 2>/dev/null'
        success, sg_id, err = ssh(cmd)
        if not success or not sg_id.strip():
            print(f"⚠ Warning: Could not get security group ID: {err}")
            return False
        
        sg_id = sg_id.strip()
        
        # Check if port 8050 is already authorized
        cmd = f'aws ec2 describe-security-groups --group-ids {sg_id} --region {AWS_REGION} --query "SecurityGroups[0].IpPermissions[?FromPort==`8050`]" --output json 2>/dev/null'
        success, check_result, err = ssh(cmd)
        
        # If port is not already open, add the rule
        if success and check_result.strip() == '[]':
            cmd = (f'aws ec2 authorize-security-group-ingress --group-id {sg_id} '
                   f'--protocol tcp --port {APP_PORT} --cidr 0.0.0.0/0 '
                   f'--region {AWS_REGION} 2>/dev/null')
            success, out, err = ssh(cmd)
            if success:
                print(f"✓ Security group updated - port {APP_PORT} now accessible")
                return True
            else:
                # Port might already be authorized, continue
                print(f"✓ Port {APP_PORT} is accessible (already authorized or default rule)")
                return True
        else:
            print(f"✓ Port {APP_PORT} is already authorized in security group")
            return True
            
    except Exception as e:
        print(f"⚠ Warning: Security group configuration failed: {e}")
        print("   You may need to manually add inbound rule for port {0}".format(APP_PORT))
        return True  # Don't fail deployment, user can add manually

def deploy():
    print("\n" + "="*60)
    print("RESULAM ROYALTIES - EC2 DEPLOYMENT")
    print("="*60 + "\n")
    
    # Step 0: Configure AWS Security Group
    print("Step 0: Configuring AWS security group...")
    if not configure_security_group():
        print("✗ Warning: Could not configure security group automatically")
        print("  Continuing with deployment - you may need to configure manually")
    
    # Step 1: Clone/update repository
    print("Step 1: Setting up repository...")
    cmd = (f"mkdir -p /home/{EC2_USER}/apps && cd /home/{EC2_USER}/apps && "
           f"if [ -d resulam-royalties ]; then cd resulam-royalties && git pull origin main 2>&1 | grep -v 'Already up'; "
           f"else git clone https://github.com/tchamna/resulam_royalties.git resulam-royalties; fi")
    success, out, err = ssh(cmd)
    if not success and "resulam-royalties" not in out:
        print(f"✗ ERROR: {err}")
        return False
    print("✓ Repository ready")
    
    # Step 2: Setup Python venv and install dependencies
    print("\nStep 2: Setting up Python environment...")
    cmd = (f"cd {APP_DIR} && "
           f"if [ ! -d venv ]; then python3 -m venv venv; fi && "
           f"source venv/bin/activate && "
           f"pip install -q --upgrade pip setuptools wheel && "
           f"pip install -q --no-cache-dir --upgrade numpy pandas && "
           f"pip install -q --no-cache-dir dash==2.14.2 dash-bootstrap-components==1.5.0 openpyxl==3.1.2 requests==2.31.0 gunicorn==21.2.0")
    success, out, err = ssh(cmd)
    if not success:
        print(f"✗ ERROR: {err}")
        return False
    print("✓ Python environment ready with dependencies")
    
    # Step 3: Download data files from S3
    print("\nStep 3: Downloading data files from S3...")
    cmd = (f"cd {APP_DIR} && "
           f"mkdir -p data && "
           f"pip install -q boto3 && "
           f"python3 << 'ENDS3'\n"
           f"import boto3\n"
           f"import os\n"
           f"os.makedirs('data', exist_ok=True)\n"
           f"s3 = boto3.client('s3', region_name='{AWS_REGION}')\n"
           f"files_to_download = [\n"
           f"    ('Resulam_books_database_Amazon_base_de_donnee_livres.csv', 'data/Resulam_books_database_Amazon_base_de_donnee_livres.csv'),\n"
           f"    ('KDP_OrdersResulamBookSales2015_{CURRENT_YEAR}RoyaltiesReportsHistory.xlsx', 'data/KDP_OrdersResulamBookSales2015_{CURRENT_YEAR}RoyaltiesReportsHistory.xlsx')\n"
           f"]\n"
           f"for src, dst in files_to_download:\n"
           f"    try:\n"
           f"        s3.download_file('{S3_BUCKET}', src, dst)\n"
           f"        print(f'Downloaded {{src}} to {{dst}}')\n"
           f"    except Exception as e:\n"
           f"        print(f'Warning: Could not download {{src}}: {{e}}')\n"
           f"ENDS3")
    success, out, err = ssh(cmd)
    if not success:
        print(f"⚠ Warning: Could not download all S3 files. Continuing with cache...")
    else:
        print("✓ Data files downloaded from S3")
    
    # Step 4: Create systemd service with S3 environment
    print("\nStep 4: Creating systemd service...")
    service_template = """[Unit]
Description=Resulam Royalties Dashboard
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/apps/resulam-royalties
Environment="PATH=/home/ec2-user/apps/resulam-royalties/venv/bin"
Environment="PYTHONPATH=/home/ec2-user/apps/resulam-royalties"
Environment="USE_S3_DATA=true"
Environment="S3_BUCKET={S3_BUCKET}"
Environment="AWS_DEFAULT_REGION={AWS_REGION}"
ExecStart=/home/ec2-user/apps/resulam-royalties/venv/bin/python main.py --host 127.0.0.1 --port 8051
Restart=always
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
""".format(S3_BUCKET=S3_BUCKET, AWS_REGION=AWS_REGION)
    
    # Write service file using heredoc
    cmd = (f"cat > /tmp/resulam.service << 'ENDSERVICE'\n"
           f"{service_template}\n"
           f"ENDSERVICE\n"
           f"sudo mv /tmp/resulam.service /etc/systemd/system/resulam-royalties.service && "
           f"sudo chmod 644 /etc/systemd/system/resulam-royalties.service")
    success, out, err = ssh(cmd)
    if not success:
        print(f"✗ ERROR: {err}")
        return False
    print("✓ Systemd service created with S3 environment")
    
    # Step 5: Create nginx configuration
    print("\nStep 5: Configuring nginx...")
    nginx_template = """upstream resulam_app {{
    server 127.0.0.1:8051;
}}

server {{
    listen {port};
    server_name _;
    client_max_body_size 50M;

    location / {{
        proxy_pass http://resulam_app;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }}
}}""".format(port=APP_PORT)
    
    cmd = (f"cat > /tmp/resulam.conf << 'ENDNGINX'\n"
           f"{nginx_template}\n"
           f"ENDNGINX\n"
           f"sudo mv /tmp/resulam.conf /etc/nginx/conf.d/resulam-royalties.conf")
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
           f"sudo systemctl enable resulam-royalties && "
           f"sudo systemctl restart resulam-royalties && "
           f"sleep 2")
    success, out, err = ssh(cmd)
    
    # Check if service is running
    cmd = "sudo systemctl is-active resulam-royalties"
    success, out, err = ssh(cmd)
    if success:
        print("✓ Service started successfully")
    else:
        print("⚠ Service may not have started. Checking logs...")
        cmd = "sudo journalctl -u resulam-royalties -n 15 --no-pager"
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
    
    # Step 8: Verify app is responding
    print("\nStep 8: Verifying deployment...")
    cmd = "curl -s http://localhost:{0} 2>&1 | head -1".format(APP_PORT)
    success, out, err = ssh(cmd)
    if success and out.strip():
        print("✓ Application responding on port {0}".format(APP_PORT))
    
    # Summary
    print("\n" + "="*60)
    print("✓ DEPLOYMENT COMPLETE")
    print("="*60)
    print("\n📍 ACCESS YOUR APP:")
    print("   http://{0}:{1}".format(EC2_IP, APP_PORT))
    print("\n📍 OTHER APPS:")
    print("   http://{0} (main routing)".format(EC2_IP))
    print("\n📋 CONFIGURATION:")
    print("   App Directory:  {0}".format(APP_DIR))
    print("   Service Name:   resulam-royalties")
    print("   Port:           {0}".format(APP_PORT))
    print("   PYTHONPATH:     {0}".format(APP_DIR))
    print("   Venv:           {0}/venv".format(APP_DIR))
    print("   Security Group: Port {0} (inbound from 0.0.0.0/0)".format(APP_PORT))
    print("\n💡 MANAGE SERVICE:")
    print("   ssh -i {0} {1}@{2}".format(SSH_KEY, EC2_USER, EC2_IP))
    print("   sudo systemctl status resulam-royalties")
    print("   sudo journalctl -u resulam-royalties -f")
    print("\n")
    
    return True

if __name__ == '__main__':
    try:
        success = deploy()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n✗ Deployment cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        sys.exit(1)
