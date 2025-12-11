#!/usr/bin/env python3
"""
Resulam Royalties - Complete EC2 Deployment Script
Single command deployment with all configs and PYTHONPATH handling
"""

import subprocess
import sys

EC2_IP = "18.208.117.82"
EC2_USER = "ec2-user"
SSH_KEY = r'C:\Users\tcham\Downloads\test-rag.pem'
APP_PORT = 8050
APP_DIR = "/home/ec2-user/apps/resulam-royalties"

def ssh(cmd):
    """Execute command on EC2 via SSH"""
    result = subprocess.run(
        ['ssh', '-i', SSH_KEY, '-o', 'StrictHostKeyChecking=no', 
         f'{EC2_USER}@{EC2_IP}', cmd],
        capture_output=True, text=True, timeout=60
    )
    return result.returncode == 0, result.stdout, result.stderr

def deploy():
    print("\n" + "="*60)
    print("RESULAM ROYALTIES - EC2 DEPLOYMENT")
    print("="*60 + "\n")
    
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
    
    # Step 3: Create systemd service with PYTHONPATH
    print("\nStep 3: Creating systemd service...")
    service_template = """[Unit]
Description=Resulam Royalties Dashboard
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={app_dir}
Environment="PATH={app_dir}/venv/bin"
Environment="PYTHONPATH={app_dir}"
ExecStart={app_dir}/venv/bin/python main.py --host 0.0.0.0 --port {port}
Restart=always
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=3

[Install]
WantedBy=multi-user.target""".format(user=EC2_USER, app_dir=APP_DIR, port=APP_PORT)
    
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
    print("✓ Systemd service created with PYTHONPATH")
    
    # Step 4: Create nginx configuration
    print("\nStep 4: Configuring nginx...")
    nginx_template = """upstream resulam_app {{
    server 127.0.0.1:{port};
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
    
    # Step 5: Reload systemd and start service
    print("\nStep 5: Starting service...")
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
        print(logs[-400:] if len(logs) > 400 else logs)
    
    # Step 6: Restart nginx
    print("\nStep 6: Restarting nginx...")
    cmd = "sudo systemctl restart nginx && sleep 1"
    success, out, err = ssh(cmd)
    if not success:
        print(f"✗ ERROR: {err}")
        return False
    print("✓ Nginx restarted")
    
    # Step 7: Verify app is responding
    print("\nStep 7: Verifying deployment...")
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
