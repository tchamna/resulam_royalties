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

# Prefer updating the existing vhost file (especially important when SSL is managed by certbot),
# otherwise fall back to a reasonable default location.
EXISTING_NGINX_FILE=""
if sudo nginx -T >/dev/null 2>&1; then
  # nginx -T produces a lot of output; the awk exits early after finding the first match,
  # which can cause nginx to receive SIGPIPE and return non-zero. Ignore that.
  EXISTING_NGINX_FILE="$(sudo nginx -T 2>/dev/null | awk -v domain="${DOMAIN_NAME}" '
    /^# configuration file / {
      file=$4
      sub(":$","",file)
    }
    $0 ~ /server_name/ && index($0, domain) {
      print file
      exit
    }
  ')" || true
fi

if [[ -n "${EXISTING_NGINX_FILE}" ]]; then
  NGINX_DIR="$(dirname "${EXISTING_NGINX_FILE}")"
  NGINX_FILE="${EXISTING_NGINX_FILE}"
elif [[ -d /etc/nginx/sites-available ]]; then
  NGINX_DIR="/etc/nginx/sites-available"
  NGINX_FILE="${NGINX_DIR}/${DOMAIN_NAME}"
elif [[ -d /etc/nginx/conf.d ]]; then
  NGINX_DIR="/etc/nginx/conf.d"
  NGINX_FILE="${NGINX_DIR}/${DOMAIN_NAME}.conf"
else
  echo "ERROR: Could not find an nginx config directory (/etc/nginx/sites-available or /etc/nginx/conf.d)."
  exit 1
fi

echo "Writing nginx config: ${NGINX_FILE}"

SSL_DIR="/etc/letsencrypt/live/${DOMAIN_NAME}"
SSL_FULLCHAIN="${SSL_DIR}/fullchain.pem"
SSL_PRIVKEY="${SSL_DIR}/privkey.pem"
SSL_OPTIONS="/etc/letsencrypt/options-ssl-nginx.conf"
SSL_DHPARAM="/etc/letsencrypt/ssl-dhparams.pem"
HAS_SSL="false"

cert_exists() {
  # /etc/letsencrypt/live is typically 0700 root:root, so checks must run as root.
  sudo test -f "$1"
}

if ! cert_exists "${SSL_FULLCHAIN}" || ! cert_exists "${SSL_PRIVKEY}"; then
  # Certbot commonly creates suffixed directories like "<domain>-0001".
  # IMPORTANT: glob expansion must happen as root (the live dir is not readable by ec2-user).
  CERT_DIRS="$(sudo bash -lc "ls -d /etc/letsencrypt/live/${DOMAIN_NAME}* 2>/dev/null || true")"
  while IFS= read -r d; do
    [[ -z "${d}" ]] && continue
    if cert_exists "${d}/fullchain.pem" && cert_exists "${d}/privkey.pem"; then
      SSL_DIR="${d}"
      SSL_FULLCHAIN="${SSL_DIR}/fullchain.pem"
      SSL_PRIVKEY="${SSL_DIR}/privkey.pem"
      break
    fi
  done <<< "${CERT_DIRS}"
fi

# If still not found, fall back to parsing certbot renewal configs (most reliable).
if [[ (! -f "${SSL_FULLCHAIN}" || ! -f "${SSL_PRIVKEY}") && -d /etc/letsencrypt/renewal ]]; then
  RENEWAL_CONF="$(sudo grep -RslE "^domains\\s*=.*\\b${DOMAIN_NAME//./\\.}\\b" /etc/letsencrypt/renewal 2>/dev/null | head -n 1 || true)"
  if [[ -n "${RENEWAL_CONF}" ]]; then
    RENEWAL_FULLCHAIN="$(sudo awk -F' *= *' '$1==\"fullchain\" {print $2; exit}' \"${RENEWAL_CONF}\" 2>/dev/null || true)"
    RENEWAL_PRIVKEY="$(sudo awk -F' *= *' '$1==\"privkey\" {print $2; exit}' \"${RENEWAL_CONF}\" 2>/dev/null || true)"
    if cert_exists "${RENEWAL_FULLCHAIN}" && cert_exists "${RENEWAL_PRIVKEY}"; then
      SSL_FULLCHAIN="${RENEWAL_FULLCHAIN}"
      SSL_PRIVKEY="${RENEWAL_PRIVKEY}"
    fi
  fi
fi
if cert_exists "${SSL_FULLCHAIN}" && cert_exists "${SSL_PRIVKEY}"; then
  HAS_SSL="true"
fi

TMP="$(mktemp)"
if [[ "${HAS_SSL}" == "true" ]]; then
  # When SSL certs exist, serve the app on 443 and redirect 80 -> 443.
  # This avoids the common situation where HTTPS keeps proxying to an old port (502)
  # after a zero-downtime deployment changes the upstream port.
  cat > "${TMP}" <<NGXEOF
server {
    listen 80;
    server_name ${DOMAIN_NAME};

    client_max_body_size 25m;

    # Allow ACME HTTP-01 challenges (safe even if unused).
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name ${DOMAIN_NAME};

    client_max_body_size 25m;

    ssl_certificate ${SSL_FULLCHAIN};
    ssl_certificate_key ${SSL_PRIVKEY};
NGXEOF

  if [[ -f "${SSL_OPTIONS}" ]]; then
    cat >> "${TMP}" <<NGXEOF
    include ${SSL_OPTIONS};
NGXEOF
  fi
  if [[ -f "${SSL_DHPARAM}" ]]; then
    cat >> "${TMP}" <<NGXEOF
    ssl_dhparam ${SSL_DHPARAM};
NGXEOF
  fi

  cat >> "${TMP}" <<NGXEOF

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
else
  # No SSL certs found: serve the app directly on port 80.
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
fi

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

if [[ "${HAS_SSL}" == "true" ]]; then
  echo "OK: nginx is proxying https://${DOMAIN_NAME} -> http://127.0.0.1:${UPSTREAM_PORT} (and redirecting http -> https)"
else
  echo "OK: nginx is proxying http://${DOMAIN_NAME} -> http://127.0.0.1:${UPSTREAM_PORT}"
fi
