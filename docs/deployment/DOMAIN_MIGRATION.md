# Domain Migration (EC2 + Nginx + GitHub Actions)

This repo deploys a Docker container on EC2 and serves it behind Nginx.

## 1) DNS (you already did this)

- Create an `A` record for your new domain/subdomain pointing to your EC2 public IP.
- Wait for DNS propagation.

## 2) Pick a free port on the EC2 host

This workflow binds the container to a *local-only* host port (`127.0.0.1:<HOST_PORT>`), so it won't conflict with other apps exposed on ports 80/443 behind Nginx.

Pick a free port like `8052`, `8060`, etc.

## 3) Update GitHub Secrets

In the GitHub repo: **Settings → Secrets and variables → Actions**

Set (or update) these secrets:

- `DOMAIN_NAME`: e.g. `africanlanguagelibrary.tchamna.com`
- `HOST_PORT`: e.g. `8052` (must be free on the EC2 host)
- `CONTAINER_NAME`: e.g. `africanlanguagelibrary-dashboard` (avoid collisions)
- `CONFIGURE_NGINX`: `true` (lets the workflow create an Nginx vhost for `DOMAIN_NAME`)

Optional:

- `OLD_DOMAIN_NAME`: e.g. `resulam-royalties.tchamna.com` (adds an HTTP 301 redirect if not already configured)

## 4) Run the deployment

Push to `main` or run the workflow manually via **Actions → Deploy to EC2 → Run workflow**.

## 5) HTTPS

The workflow configures Nginx for HTTP. To enable HTTPS:

1. SSH to the EC2 instance
2. Install certbot (Amazon Linux):
   - `sudo yum install -y certbot python3-certbot-nginx`
3. Issue the certificate:
   - `sudo certbot --nginx -d africanlanguagelibrary.tchamna.com`
4. Confirm auto-renew:
   - `sudo certbot renew --dry-run`

If you already have certbot installed and working on this server, step (2) is not needed.

