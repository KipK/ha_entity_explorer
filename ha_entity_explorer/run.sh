#!/bin/bash

# Load S6 environment variables (if available)
# This is required because S6 v3 might not export them to the service process by default
if [ -d /var/run/s6/container_environment ]; then
    for var in /var/run/s6/container_environment/*; do
        [ -e "$var" ] || continue
        key=$(basename "$var")
        val=$(cat "$var")
        export "$key"="$val"
    done
fi

# Initialize Bashio
if [ -f /usr/lib/bashio/bashio.sh ]; then
    source /usr/lib/bashio/bashio.sh
else
    # Fallback/Debug if bashio not found
    echo "ERROR: Bashio not found!"
    exit 1
fi

# Define config path
CONFIG_PATH="/app/app_config.yaml"

bashio::log.info "Starting HA Entity Explorer..."

# Generate app_config.yaml from options.json
bashio::log.info "Generating configuration..."

# Get values from options or use defaults/environment
# HA Add-ons automatically expose SUPERVISOR_TOKEN and HASSIO_URL if mapped?
# Actually, the options.json is at /data/options.json
# Get values from options
LOG_LEVEL=$(bashio::config 'log_level')
LANGUAGE=$(bashio::config 'language')
DEFAULT_HISTORY_DAYS=$(bashio::config 'default_history_days')

# Generate a random secret key for Flask sessions
# This ensures security without user intervention
if command -v openssl >/dev/null 2>&1; then
    SECRET_KEY=$(openssl rand -hex 32)
else
    # Fallback if openssl not available
    SECRET_KEY=$(date +%s%N | sha256sum | base64 | head -c 32)
fi
bashio::log.info "Generated session secret key"

# Default internal URL
HA_URL="http://supervisor/core"
bashio::log.info "Using default internal HA URL"

# Supervisor Token
# Check if SUPERVISOR_TOKEN env var is set (safely)
    bashio::log.info "Using Supervisor Token"
    HA_TOKEN="${SUPERVISOR_TOKEN}"
    bashio::log.info "Token length: ${#HA_TOKEN}"
    bashio::log.info "Token start: ${HA_TOKEN:0:10}..."

    # Validating Token and Detecting URL
    bashio::log.info "Testing/Detecting API URL via Curl..."
    
    # Try Standard Proxy (http://supervisor/core)
    curl -v -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${HA_TOKEN}" -H "Content-Type: application/json" http://supervisor/core/api/ > /tmp/curl_status_core
    CORE_STATUS=$(cat /tmp/curl_status_core)
    
    # Try Direct Supervisor (http://supervisor) - User suggestion
    curl -v -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer ${HA_TOKEN}" -H "Content-Type: application/json" http://supervisor/api/ > /tmp/curl_status_direct
    DIRECT_STATUS=$(cat /tmp/curl_status_direct)
    
    bashio::log.info "Status - Core: ${CORE_STATUS}, Direct: ${DIRECT_STATUS}"
    
    if [ "${CORE_STATUS}" == "200" ]; then
        bashio::log.info "Using Standard Proxy: http://supervisor/core"
        HA_URL="http://supervisor/core"
    elif [ "${DIRECT_STATUS}" == "200" ] || [ "${DIRECT_STATUS}" == "405" ]; then
        # 405 Method Not Allowed implies endpoint exists
        bashio::log.info "Using Direct Supervisor: http://supervisor"
        HA_URL="http://supervisor"
    else
        bashio::log.warning "Both endpoints failed authentication or check. Defaulting to http://supervisor/core"
        HA_URL="http://supervisor/core"
    fi

else
    bashio::log.error "SUPERVISOR_TOKEN is not set!"
    HA_TOKEN=""
fi

# Write config yaml
cat > "${CONFIG_PATH}" <<EOF
home_assistant:
  url: "${HA_URL}"
  api_token: "${HA_TOKEN}"

app:
  language: "${LANGUAGE}"
  default_history_days: ${DEFAULT_HISTORY_DAYS}
  host: "0.0.0.0"
  port: 8050
  secret_key: "${SECRET_KEY}"

whitelist: []
blacklist: []
safe_ips:
  - "127.0.0.1"
  - "::1"
  - "172.30.32.1"  # Supervisor
  - "172.30.32.2"  # Home Assistant (usually)
EOF

bashio::log.info "Configuration generated."

# Start application
bashio::log.info "Starting Flask Application..."
exec python3 -u server.py
