# Docker Deployment Guide

## Prerequisites

- Docker installed on your system
- Docker Compose installed
- CSV data files in the `data/` directory

## Local Development

### Build and run locally:

```bash
# Build the Docker image
docker-compose build

# Start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

Access the dashboard at: http://localhost:8050

## EC2 Deployment

### Initial Setup

1. **SSH into your EC2 instance:**
   ```bash
   ssh -i your-key.pem ec2-user@your-ec2-ip
   ```

2. **Run the setup script:**
   ```bash
   curl -fsSL https://raw.githubusercontent.com/tchamna/resulam_royalties/main/setup-docker-ec2.sh | bash
   ```

3. **Clone the repository:**
   ```bash
   mkdir -p ~/apps
   cd ~/apps
   git clone https://github.com/tchamna/resulam_royalties.git
   cd resulam_royalties
   ```

4. **Add your data files:**
   ```bash
   mkdir -p data
   # Copy your CSV files to data/ directory
   ```

5. **Start the application:**
   ```bash
   docker-compose up -d
   ```

### Automated Deployment (GitHub Actions)

The repository includes a GitHub Actions workflow that automatically deploys to EC2 on every push to `main`.

**Required GitHub Secrets:**
- `EC2_HOST` - Your EC2 instance IP or hostname
- `EC2_USER` - SSH user (default: ec2-user)
- `EC2_SSH_KEY` - Your EC2 SSH private key
- `APP_DIR` - Application directory (default: /home/ec2-user/apps/resulam-royalties)
- `S3_BUCKET` - (Optional) S3 bucket for data files
- `S3_DATA_FILES` - (Optional) Pipe-separated list of S3 files
- `AWS_ACCESS_KEY_ID` - (Optional) For S3 access
- `AWS_SECRET_ACCESS_KEY` - (Optional) For S3 access

### Manual Deployment

```bash
# SSH to EC2
ssh -i your-key.pem ec2-user@your-ec2-ip

# Navigate to app directory
cd ~/apps/resulam_royalties

# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose up -d --build

# Check logs
docker-compose logs -f
```

## Container Management

### View running containers:
```bash
docker ps
```

### View all containers (including stopped):
```bash
docker ps -a
```

### View logs:
```bash
docker logs resulam-royalties --tail 50 -f
```

### Restart container:
```bash
docker-compose restart
```

### Stop container:
```bash
docker-compose down
```

### Remove container and images:
```bash
docker-compose down --rmi all
```

## Troubleshooting

### Container won't start:
```bash
# Check logs
docker logs resulam-royalties

# Check container status
docker inspect resulam-royalties
```

### Port already in use:
```bash
# Check what's using port 8050
sudo netstat -tlnp | grep 8050

# Stop conflicting service or change port in docker-compose.yml
```

### Data files not found:
Ensure CSV files are in the `data/` directory and properly mounted in docker-compose.yml

### Health check failing:
```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' resulam-royalties

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' resulam-royalties
```

## Environment Variables

You can customize the deployment by setting environment variables in a `.env` file:

```env
USE_S3_DATA=false
S3_BUCKET=your-bucket-name
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

## Security Notes

- Container runs as non-root user
- Only port 8050 is exposed
- Data directory is mounted read-only
- Health checks ensure application stability
