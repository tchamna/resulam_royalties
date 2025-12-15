#!/usr/bin/env bash
set -euo pipefail

DOMAIN_NAME="${DOMAIN_NAME:-}"
UPSTREAM_PORT="${UPSTREAM_PORT:-}"
OLD_DOMAIN_NAME="${OLD_DOMAIN_NAME:-}"

if [[ -z "${DOMAIN_NAME}" ]]; then
  echo "ERROR: DOMAIN_NAME is required (e.g. africanlanguagelibrary.tchamna.com)."
  exit 1
fi
if [[ -z "${UPSTREAM_PORT}" ]]; then
  echo "ERROR: UPSTREAM_PORT is required (the localhost port Docker binds to)."
  exit 1
fi

if [[ -d /etc/nginx/conf.d ]]; then
  NGINX_DIR="/etc/nginx/conf.d"
  NGINX_FILE="${NGINX_DIR}/${DOMAIN_NAME}.conf"
elif [[ -d /etc/nginx/sites-available ]]; then
  NGINX_DIR="/etc/nginx/sites-available"
  NGINX_FILE="${NGINX_DIR}/${DOMAIN_NAME}"
else
  echo "ERROR: Could not find an nginx config directory (/etc/nginx/conf.d or /etc/nginx/sites-available)."
  exit 1
fi

echo "Writing nginx config: ${NGINX_FILE}"

TMP="$(mktemp)"
cat > "${TMP}" <<NGXEOF
server {
    listen 80;
    server_name ${DOMAIN_NAME};

    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:${UPSTREAM_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Dash can use long-lived connections; keep this conservative.
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;

        # WebSocket headers (safe even if unused)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGXEOF

# Optional redirect from an old domain to the new one (only if it's not already configured elsewhere).
if [[ -n "${OLD_DOMAIN_NAME}" ]]; then
  if sudo nginx -T 2>/dev/null | grep -E "server_name\\s+.*\\b${OLD_DOMAIN_NAME}\\b" >/dev/null 2>&1; then
    echo "Skipping OLD_DOMAIN_NAME redirect; ${OLD_DOMAIN_NAME} is already configured in nginx."
  else
    cat >> "${TMP}" <<NGXEOF

server {
    listen 80;
    server_name ${OLD_DOMAIN_NAME};
    return 301 http://${DOMAIN_NAME}\$request_uri;
}
NGXEOF
  fi
fi

if [[ -f "${NGINX_FILE}" ]]; then
  sudo cp -f "${NGINX_FILE}" "${NGINX_FILE}.bak.$(date +%Y%m%d%H%M%S)" || true
fi

sudo mkdir -p "${NGINX_DIR}"
sudo cp -f "${TMP}" "${NGINX_FILE}"

if [[ "${NGINX_DIR}" == "/etc/nginx/sites-available" ]]; then
  sudo mkdir -p /etc/nginx/sites-enabled
  sudo ln -sf "${NGINX_FILE}" "/etc/nginx/sites-enabled/${DOMAIN_NAME}"
fi

rm -f "${TMP}"

echo "Testing nginx configuration..."
sudo nginx -t

echo "Reloading nginx..."
sudo systemctl reload nginx || sudo systemctl restart nginx

echo "OK: nginx is proxying http://${DOMAIN_NAME} -> http://127.0.0.1:${UPSTREAM_PORT}"
