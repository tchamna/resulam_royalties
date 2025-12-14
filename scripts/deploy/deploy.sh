#!/bin/bash
#############################################################################
# RESULAM ROYALTIES DASHBOARD - EC2 DEPLOYMENT SCRIPT (BASH VERSION)
#
# For macOS and Linux users (alternative to PowerShell)
# Usage: ./deploy.sh [EC2_IP] [KEY_PATH] [START_PORT]
#############################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parameters with defaults
EC2_IP="${1:-18.208.117.82}"
EC2_USER="${2:-ec2-user}"
KEY_PATH="${3:-}"
START_PORT="${4:-8050}"
REPOSITORY="tchamna/resulam_royalties"

# Helper functions
print_header() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   RESULAM ROYALTIES - EC2 DEPLOYMENT AUTOMATION SCRIPT              ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}\n"
}

print_step() {
    echo -e "\n${YELLOW}$1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

#############################################################################
# STEP 1: VALIDATE PREREQUISITES
#############################################################################

print_header

print_step "STEP 1: Validating Prerequisites"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI not found. Please install AWS CLI v2"
    echo "Download: https://aws.amazon.com/cli/"
    exit 1
fi
aws_version=$(aws --version)
print_success "AWS CLI found: $aws_version"

# Check Git
if ! command -v git &> /dev/null; then
    print_error "Git not found. Please install Git"
    exit 1
fi
git_version=$(git --version)
print_success "Git found: $git_version"

# Check SSH
if ! command -v ssh &> /dev/null; then
    print_error "SSH not found"
    exit 1
fi
print_success "SSH available"

# Find or validate SSH key
if [ -z "$KEY_PATH" ]; then
    print_info "SSH Key Selection"
    
    # Check common locations
    if [ -f "$HOME/.ssh/id_rsa" ]; then
        KEY_PATH="$HOME/.ssh/id_rsa"
        print_success "Found: $KEY_PATH"
    elif [ -f "$HOME/.ssh/aws-resulam.pem" ]; then
        KEY_PATH="$HOME/.ssh/aws-resulam.pem"
        print_success "Found: $KEY_PATH"
    elif [ -f "$HOME/.ssh/resulam.pem" ]; then
        KEY_PATH="$HOME/.ssh/resulam.pem"
        print_success "Found: $KEY_PATH"
    else
        print_error "No SSH keys found in common locations"
        read -p "Enter path to SSH key (.pem file): " KEY_PATH
    fi
fi

if [ ! -f "$KEY_PATH" ]; then
    print_error "SSH key not found: $KEY_PATH"
    exit 1
fi
print_success "SSH key verified: $KEY_PATH"

# Validate AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials not configured or invalid"
    echo "Run: aws configure"
    exit 1
fi
aws_identity=$(aws sts get-caller-identity --output json)
aws_account=$(echo $aws_identity | grep -o '"Account": "[^"]*' | cut -d'"' -f4)
print_success "AWS credentials valid (Account: $aws_account)"

#############################################################################
# STEP 2: COLLECT AWS ENVIRONMENT VARIABLES
#############################################################################

print_step "STEP 2: Collecting AWS Environment Variables"

AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

if [ -z "$AWS_ACCESS_KEY_ID" ] && [ -f "$HOME/.aws/credentials" ]; then
    AWS_ACCESS_KEY_ID=$(grep -A 1 "\[default\]" "$HOME/.aws/credentials" | grep aws_access_key_id | cut -d'=' -f2 | xargs)
    AWS_SECRET_ACCESS_KEY=$(grep -A 2 "\[default\]" "$HOME/.aws/credentials" | grep aws_secret_access_key | cut -d'=' -f2 | xargs)
fi

print_success "AWS Environment Variables collected:"
echo "  AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:10}..."
echo "  AWS_SECRET_ACCESS_KEY: [hidden]"
echo "  AWS_DEFAULT_REGION: $AWS_DEFAULT_REGION"

#############################################################################
# STEP 3: FIND AVAILABLE PORT
#############################################################################

print_step "STEP 3: Finding Available Port on EC2"

print_info "Connecting to $EC2_IP to find available port..."

port=$START_PORT
max_attempts=20
found=0

for ((i=0; i<max_attempts; i++)); do
    if ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_IP}" \
        "netstat -tuln | grep :$port" &> /dev/null; then
        port=$((port + 1))
    else
        found=1
        break
    fi
done

if [ $found -eq 0 ]; then
    print_error "Could not find available port"
    exit 1
fi

print_success "Available port found: $port"

#############################################################################
# STEP 4: UPDATE GITHUB SECRETS (optional)
#############################################################################

print_step "STEP 4: Updating GitHub Secrets"

if command -v gh &> /dev/null; then
    print_info "Updating GitHub secrets..."
    
    gh secret set AWS_ACCESS_KEY_ID --body "$AWS_ACCESS_KEY_ID" --repo "$REPOSITORY" 2>/dev/null || \
        print_warning "Could not update AWS_ACCESS_KEY_ID secret"
    
    gh secret set AWS_SECRET_ACCESS_KEY --body "$AWS_SECRET_ACCESS_KEY" --repo "$REPOSITORY" 2>/dev/null || \
        print_warning "Could not update AWS_SECRET_ACCESS_KEY secret"
    
    gh secret set AWS_DEFAULT_REGION --body "$AWS_DEFAULT_REGION" --repo "$REPOSITORY" 2>/dev/null || \
        print_warning "Could not update AWS_DEFAULT_REGION secret"
    
    gh secret set DEPLOY_PORT --body "$port" --repo "$REPOSITORY" 2>/dev/null && \
        print_success "Deployment secrets updated"
else
    print_warning "GitHub CLI not found. Install from: https://cli.github.com/"
fi

#############################################################################
# STEP 5: SETUP ON EC2 INSTANCE
#############################################################################

print_step "STEP 5: Setting Up Application on EC2"

print_info "Connecting to EC2: ${EC2_USER}@${EC2_IP}"

# Create EC2 deployment script
EC2_DEPLOY_SCRIPT=$(cat <<'EOF'
#!/bin/bash
set -e

PORT=$PORT_NUMBER
REPO_URL="$REPO_URL_VAR"
APP_DIR="/home/$EC2_USER_VAR/resulam-royalties"
VENV_DIR="$APP_DIR/venv"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   RESULAM ROYALTIES - EC2 SETUP (Running on EC2)               ║"
echo "╚════════════════════════════════════════════════════════════════╝"

# Step 1: Update system packages
echo ""
echo "📦 Step 1: Updating system packages..."
sudo yum update -y -q
sudo yum install -y -q python3 python3-pip python3-venv git nginx gcc python3-devel

# Step 2: Clone or update repository
echo ""
echo "📥 Step 2: Cloning/updating repository..."
if [ -d "$APP_DIR" ]; then
    echo "  Repository already exists. Updating..."
    cd "$APP_DIR"
    git pull origin main
else
    echo "  Cloning repository..."
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
fi

# Step 3: Create Python virtual environment
echo ""
echo "🐍 Step 3: Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Step 4: Install Python dependencies
echo ""
echo "📚 Step 4: Installing Python dependencies..."
pip install --upgrade pip setuptools wheel -q
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt -q
else
    pip install dash dash-bootstrap-components pandas openpyxl requests gunicorn -q
fi

# Step 5: Create systemd service file
echo ""
echo "⚙️  Step 5: Creating systemd service..."
sudo tee /etc/systemd/system/resulam-royalties.service > /dev/null <<SVCEOF
[Unit]
Description=Resulam Royalties Dashboard
After=network.target

[Service]
Type=simple
User=$EC2_USER_VAR
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
Environment="AWS_DEFAULT_REGION=us-east-1"
ExecStart=$VENV_DIR/bin/python main.py --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload

# Step 6: Configure Nginx
echo ""
echo "🌐 Step 6: Configuring Nginx reverse proxy..."
sudo tee /etc/nginx/conf.d/resulam-royalties.conf > /dev/null <<NGXEOF
upstream resulam_app {
    server 127.0.0.1:$PORT;
}

server {
    listen 80;
    server_name _;
    
    client_max_body_size 50M;
    
    location / {
        proxy_pass http://resulam_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
    }
}
NGXEOF

sudo nginx -t
sudo systemctl restart nginx

# Step 7: Start the application
echo ""
echo "🚀 Step 7: Starting Resulam Royalties service..."
sudo systemctl enable resulam-royalties
sudo systemctl restart resulam-royalties

# Step 8: Verify service is running
echo ""
echo "✅ Checking service status..."
sleep 3
if sudo systemctl is-active --quiet resulam-royalties; then
    echo "✓ Service is running!"
    sudo systemctl status resulam-royalties --no-pager
else
    echo "✗ Service failed to start. Checking logs..."
    sudo journalctl -u resulam-royalties -n 50 --no-pager
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║   ✓ DEPLOYMENT COMPLETE!                                      ║"
echo "║                                                                ║"
echo "║   Access your dashboard:                                       ║"
echo "║   → http://$EC2_IP                                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
EOF
)

# Create temporary script
temp_script="/tmp/ec2_deploy_$RANDOM.sh"
echo "$EC2_DEPLOY_SCRIPT" | \
    sed "s|\$PORT_NUMBER|$port|g" | \
    sed "s|\$REPO_URL_VAR|https://github.com/$REPOSITORY.git|g" | \
    sed "s|\$EC2_USER_VAR|$EC2_USER|g" | \
    sed "s|\$EC2_IP|$EC2_IP|g" > "$temp_script"

# Upload and execute
print_info "Uploading deployment script..."
scp -i "$KEY_PATH" -o StrictHostKeyChecking=no "$temp_script" "${EC2_USER}@${EC2_IP}:/tmp/deploy.sh" > /dev/null 2>&1

print_info "Making script executable and running..."
ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_IP}" "chmod +x /tmp/deploy.sh && /tmp/deploy.sh"

rm -f "$temp_script"

#############################################################################
# STEP 6: UPDATE AWS SECURITY GROUP
#############################################################################

print_step "STEP 6: Updating AWS Security Group"

print_info "Fetching EC2 instance information..."

# Get instance details
instance_info=$(aws ec2 describe-instances \
    --filters "Name=ip-address,Values=$EC2_IP" \
    --query 'Reservations[0].Instances[0]' \
    --output json 2>/dev/null)

if [ -z "$instance_info" ] || [ "$instance_info" == "null" ]; then
    print_warning "Could not find EC2 instance. Security group may need manual update."
else
    sg_id=$(echo "$instance_info" | grep -o '"GroupId": "[^"]*' | head -1 | cut -d'"' -f4)
    instance_id=$(echo "$instance_info" | grep -o '"InstanceId": "[^"]*' | head -1 | cut -d'"' -f4)
    
    if [ -n "$sg_id" ]; then
        print_success "Instance ID: $instance_id"
        print_success "Security Group: $sg_id"
        
        # Add HTTP rule
        if ! aws ec2 describe-security-groups --group-ids "$sg_id" \
            --query 'SecurityGroups[0].IpPermissions[?FromPort==`80`]' \
            --output json 2>/dev/null | grep -q "80"; then
            print_info "Adding port 80 (HTTP) to security group..."
            aws ec2 authorize-security-group-ingress \
                --group-id "$sg_id" \
                --protocol tcp \
                --port 80 \
                --cidr 0.0.0.0/0 2>/dev/null
            print_success "Port 80 added"
        else
            print_success "Port 80 already open"
        fi
        
        # Add HTTPS rule
        if ! aws ec2 describe-security-groups --group-ids "$sg_id" \
            --query 'SecurityGroups[0].IpPermissions[?FromPort==`443`]' \
            --output json 2>/dev/null | grep -q "443"; then
            print_info "Adding port 443 (HTTPS) to security group..."
            aws ec2 authorize-security-group-ingress \
                --group-id "$sg_id" \
                --protocol tcp \
                --port 443 \
                --cidr 0.0.0.0/0 2>/dev/null
            print_success "Port 443 added"
        else
            print_success "Port 443 already open"
        fi
    fi
fi

#############################################################################
# DEPLOYMENT COMPLETE
#############################################################################

echo -e "\n${GREEN}"
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                  ✅ DEPLOYMENT SUCCESSFUL!                         ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "\n${YELLOW}📊 DEPLOYMENT SUMMARY${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${CYAN}EC2 Host:              $EC2_IP${NC}"
echo -e "  ${CYAN}Application Port:      $port${NC}"
echo -e "  ${CYAN}Dashboard URL:         http://$EC2_IP${NC}"
echo -e "  ${CYAN}Reverse Proxy:         Nginx on port 80${NC}"
echo -e "  ${CYAN}Service:               resulam-royalties (systemd)${NC}"

echo -e "\n${YELLOW}🔗 QUICK LINKS${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${GREEN}Access Dashboard:  http://$EC2_IP${NC}"
echo -e "  ${GREEN}SSH to instance:   ssh -i '$KEY_PATH' ${EC2_USER}@${EC2_IP}${NC}"

echo -e "\n${YELLOW}📝 USEFUL COMMANDS${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  View logs:             ${CYAN}ssh -i '$KEY_PATH' ${EC2_USER}@${EC2_IP} 'sudo journalctl -u resulam-royalties -f'${NC}"
echo -e "  Restart service:       ${CYAN}ssh -i '$KEY_PATH' ${EC2_USER}@${EC2_IP} 'sudo systemctl restart resulam-royalties'${NC}"
echo -e "  Check service status:  ${CYAN}ssh -i '$KEY_PATH' ${EC2_USER}@${EC2_IP} 'sudo systemctl status resulam-royalties'${NC}"

echo -e "\n${YELLOW}✨ Next Steps:${NC}"
echo -e "  ${CYAN}1. Wait 10-15 seconds for the application to fully start${NC}"
echo -e "  ${CYAN}2. Visit http://$EC2_IP in your browser${NC}"
echo -e "  ${CYAN}3. If you see a connection error, check the logs using the command above${NC}"
echo -e "\n"
