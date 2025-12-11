#!/bin/bash
#############################################################################
# RESULAM ROYALTIES - EC2 CLEANUP & MAINTENANCE SCRIPT
#
# This script helps with:
# 1. Restarting the application
# 2. Viewing logs
# 3. Checking service status
# 4. Stopping/starting services
# 5. Rolling back to previous version
# 6. Cleaning up disk space
#
# Usage: ./ec2-manage.sh [command] [options]
#############################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
EC2_IP="${EC2_IP:-18.208.117.82}"
EC2_USER="${EC2_USER:-ec2-user}"
KEY_PATH="${KEY_PATH:-$HOME/.ssh/ec2-key.pem}"
APP_DIR="/home/$EC2_USER/resulam-royalties"

# Helper functions
print_header() {
    echo -e "\n${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   RESULAM ROYALTIES - EC2 MANAGEMENT TOOL                          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}\n"
}

print_menu() {
    echo -e "${YELLOW}Available Commands:${NC}"
    echo -e "  ${CYAN}status${NC}        - Check application status"
    echo -e "  ${CYAN}logs${NC}          - View application logs (follow mode)"
    echo -e "  ${CYAN}logs-tail${NC}     - View last 50 lines of logs"
    echo -e "  ${CYAN}restart${NC}       - Restart the application"
    echo -e "  ${CYAN}stop${NC}          - Stop the application"
    echo -e "  ${CYAN}start${NC}         - Start the application"
    echo -e "  ${CYAN}health${NC}        - Perform health check"
    echo -e "  ${CYAN}nginx-status${NC}  - Check Nginx status"
    echo -e "  ${CYAN}nginx-logs${NC}    - View Nginx error logs"
    echo -e "  ${CYAN}disk${NC}          - Check disk usage"
    echo -e "  ${CYAN}memory${NC}        - Check memory usage"
    echo -e "  ${CYAN}ports${NC}         - Check port usage"
    echo -e "  ${CYAN}update${NC}        - Pull latest code and restart"
    echo -e "  ${CYAN}rollback${NC}      - Rollback to previous version"
    echo -e "  ${CYAN}cleanup${NC}       - Clean up Python cache files"
    echo -e "  ${CYAN}ssh${NC}           - SSH to instance"
    echo -e "  ${CYAN}help${NC}          - Show this help menu"
    echo ""
}

ssh_command() {
    ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_IP}" "$@"
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
# COMMANDS
#############################################################################

cmd_status() {
    print_info "Checking application status..."
    echo ""
    ssh_command "sudo systemctl status resulam-royalties --no-pager"
}

cmd_logs() {
    print_info "Viewing application logs (Ctrl+C to stop)..."
    echo ""
    ssh_command "sudo journalctl -u resulam-royalties -f"
}

cmd_logs_tail() {
    print_info "Last 50 lines of application logs:"
    echo ""
    ssh_command "sudo journalctl -u resulam-royalties -n 50 --no-pager"
}

cmd_restart() {
    print_info "Restarting application..."
    ssh_command "sudo systemctl restart resulam-royalties"
    sleep 2
    echo ""
    print_success "Application restarted"
    echo "Checking status..."
    ssh_command "sudo systemctl is-active resulam-royalties && echo 'Status: RUNNING' || echo 'Status: FAILED'"
}

cmd_stop() {
    print_warning "Stopping application..."
    ssh_command "sudo systemctl stop resulam-royalties"
    sleep 1
    print_success "Application stopped"
}

cmd_start() {
    print_info "Starting application..."
    ssh_command "sudo systemctl start resulam-royalties"
    sleep 2
    echo ""
    print_success "Application started"
    ssh_command "sudo systemctl is-active resulam-royalties && echo 'Status: RUNNING' || echo 'Status: FAILED'"
}

cmd_health() {
    print_info "Performing health check on http://$EC2_IP..."
    echo ""
    
    max_attempts=10
    for i in $(seq 1 $max_attempts); do
        if curl -sf "http://$EC2_IP" > /dev/null 2>&1; then
            print_success "Application is responding (attempt $i/$max_attempts)"
            echo ""
            response_time=$(curl -w '%{time_total}s' -o /dev/null -s "http://$EC2_IP")
            print_info "Response time: $response_time"
            return 0
        fi
        print_warning "Attempt $i/$max_attempts: Waiting for application..."
        sleep 3
    done
    
    print_error "Health check failed after $max_attempts attempts"
    echo ""
    print_info "Application may be starting. Check logs with: ./ec2-manage.sh logs-tail"
    return 1
}

cmd_nginx_status() {
    print_info "Checking Nginx status..."
    echo ""
    ssh_command "sudo systemctl status nginx --no-pager"
}

cmd_nginx_logs() {
    print_info "Viewing Nginx error logs (last 50 lines):"
    echo ""
    ssh_command "sudo tail -50 /var/log/nginx/error.log"
}

cmd_disk() {
    print_info "Disk usage:"
    echo ""
    ssh_command "df -h | grep -E 'Filesystem|/$|/home'"
}

cmd_memory() {
    print_info "Memory usage:"
    echo ""
    ssh_command "free -h"
}

cmd_ports() {
    print_info "Ports in use:"
    echo ""
    ssh_command "sudo netstat -tuln | grep LISTEN"
}

cmd_update() {
    print_info "Updating application..."
    echo ""
    
    echo "1. Pulling latest code from git..."
    ssh_command "cd $APP_DIR && git pull origin main"
    
    echo ""
    echo "2. Installing/updating dependencies..."
    ssh_command "source $APP_DIR/venv/bin/activate && pip install -r $APP_DIR/requirements.txt -q"
    
    echo ""
    echo "3. Restarting service..."
    ssh_command "sudo systemctl restart resulam-royalties"
    
    sleep 3
    echo ""
    print_success "Update complete!"
    cmd_status
}

cmd_rollback() {
    print_warning "Rolling back to previous commit..."
    echo ""
    
    # Show recent commits
    echo "Recent commits:"
    ssh_command "cd $APP_DIR && git log --oneline -5"
    echo ""
    
    read -p "Proceed with rollback? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        print_warning "Rollback cancelled"
        return 1
    fi
    
    echo ""
    echo "Rolling back..."
    ssh_command "cd $APP_DIR && git reset --hard HEAD~1"
    
    echo ""
    echo "Restarting application..."
    ssh_command "sudo systemctl restart resulam-royalties"
    
    sleep 3
    echo ""
    print_success "Rollback complete!"
    cmd_status
}

cmd_cleanup() {
    print_info "Cleaning up Python cache files..."
    echo ""
    
    ssh_command "find $APP_DIR -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
    ssh_command "find $APP_DIR -type f -name '*.pyc' -delete 2>/dev/null || true"
    
    print_success "Cleanup complete"
}

cmd_ssh() {
    print_info "Connecting to EC2 instance..."
    echo ""
    print_info "Command: ssh -i '$KEY_PATH' ${EC2_USER}@${EC2_IP}"
    echo ""
    ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no "${EC2_USER}@${EC2_IP}"
}

cmd_help() {
    print_menu
}

#############################################################################
# MAIN
#############################################################################

# Check if SSH key exists
if [ ! -f "$KEY_PATH" ]; then
    print_error "SSH key not found: $KEY_PATH"
    echo ""
    echo "Please set KEY_PATH environment variable or store key in ~/.ssh/ec2-key.pem"
    exit 1
fi

# Get command
COMMAND="${1:-help}"

# Validate SSH connection before running
case "$COMMAND" in
    help|--help|-h)
        print_header
        cmd_help
        ;;
    status)
        print_header
        cmd_status
        ;;
    logs)
        print_header
        cmd_logs
        ;;
    logs-tail|logs_tail)
        print_header
        cmd_logs_tail
        ;;
    restart)
        print_header
        cmd_restart
        ;;
    stop)
        print_header
        cmd_stop
        ;;
    start)
        print_header
        cmd_start
        ;;
    health)
        print_header
        cmd_health
        ;;
    nginx-status|nginx_status)
        print_header
        cmd_nginx_status
        ;;
    nginx-logs|nginx_logs)
        print_header
        cmd_nginx_logs
        ;;
    disk)
        print_header
        cmd_disk
        ;;
    memory)
        print_header
        cmd_memory
        ;;
    ports)
        print_header
        cmd_ports
        ;;
    update)
        print_header
        cmd_update
        ;;
    rollback)
        print_header
        cmd_rollback
        ;;
    cleanup)
        print_header
        cmd_cleanup
        ;;
    ssh)
        cmd_ssh
        ;;
    *)
        print_header
        print_error "Unknown command: $COMMAND"
        echo ""
        print_menu
        exit 1
        ;;
esac
