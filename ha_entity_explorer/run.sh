#!/usr/bin/with-contenv bashio

# Define config path
CONFIG_PATH="/app/app_config.yaml"

bashio::log.info "Starting HA Entity Explorer..."

# Generate app_config.yaml from options.json
bashio::log.info "Generating configuration..."

# Get values from options or use defaults/environment
# HA Add-ons automatically expose SUPERVISOR_TOKEN and HASSIO_URL if mapped?
# Actually, the options.json is at /data/options.json
# But using bashio to read options is easier.

HA_URL=$(bashio::config 'ha_url')
HA_TOKEN=$(bashio::config 'ha_token')
LOG_LEVEL=$(bashio::config 'log_level')
LANGUAGE=$(bashio::config 'language')
DEFAULT_HISTORY_DAYS=$(bashio::config 'default_history_days')
SECRET_KEY=$(bashio::config 'secret_key')

# If HA_URL is empty, try to derive from environment or default internal URL
if bashio::var.true "${HA_URL}"; then
    bashio::log.info "Using configured HA URL: ${HA_URL}"
else
    # Default internal URL
    bashio::log.info "Using default internal HA URL"
    HA_URL="http://supervisor/core"
fi

# If HA_TOKEN is empty, we might need to use the Supervisor token
if bashio::var.true "${HA_TOKEN}"; then
    bashio::log.info "Using configured HA Token"
else
    bashio::log.info "Using Supervisor Token"
    HA_TOKEN="${SUPERVISOR_TOKEN}"
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
  port: 5000
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
exec python3 server.py
