# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "flask",
#     "pyyaml",
#     "requests",
#     "python-dateutil",
# ]
# ///

"""
HA Entity Explorer - Home Assistant Entity History Visualization
A web application to explore and visualize history of any Home Assistant entity.
"""

from datetime import datetime, timedelta
import ipaddress
import os
import json
import math
from urllib.parse import urlparse
import uuid
import zipfile
import io
from flask import Flask, render_template, jsonify, request, abort
from dateutil import parser

from config import load_config
from ha_api import HomeAssistantAPI, HomeAssistantAPIError

app = Flask(__name__)

# Load configuration
config = load_config()

# Read addon version from config.yaml for static asset cache-busting
def _get_addon_version():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_yaml_path = os.path.join(base_dir, "config.yaml")
        with open(config_yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return str(data.get('version', '1.0.0'))
    except Exception:
        return '1.0.0'

APP_VERSION = _get_addon_version()

@app.context_processor
def inject_version():
    return {'app_version': APP_VERSION}

# Configuration shortcuts
HOST = config.app.host
PORT = config.app.port

# Initialize Home Assistant API client
ha_api = HomeAssistantAPI(
    url=config.home_assistant.url,
    token=config.home_assistant.api_token
)

# Cache for processed history data
history_cache = {}

# Cache for imported data (session based usually, but here global for simplicity)
# Structure: { import_id: [raw_data_list] }
imported_data_cache = {}

# Authentication setup
import yaml
from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

app.secret_key = config.app.secret_key
if not app.secret_key:
    if os.environ.get('FLASK_DEBUG', 'false').lower() == 'true':
        app.secret_key = 'dev-secret-key-change-me'
        print("WARNING: using dev secret key")
    else:
        raise ValueError("No secret key configured!")

class IngressMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_INGRESS_PATH', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
        return self.app(environ, start_response)

app.wsgi_app = IngressMiddleware(app.wsgi_app)

@app.after_request
def add_security_headers(response):
    # SA-04: Security Headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    # CSP: Allow scripts from self and cdn.jsdelivr.net (used in index.html)
    # Also allow inline scripts/styles as the current app uses them heavily (would require refactor to remove)
    response.headers['Content-Security-Policy'] = "default-src 'self' cdn.jsdelivr.net; script-src 'self' cdn.jsdelivr.net 'unsafe-inline'; style-src 'self' cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data:; font-src 'self' cdn.jsdelivr.net data:;"
    return response

# Apply ProxyFix to handle X-Forwarded headers from Reverse Proxy
# This ensures request.url matches the external URL (HTTPS) and not the internal one (HTTP)
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

# IP Banning state
login_attempts = {}  # {ip: count}
MAX_LOGIN_ATTEMPTS = 5

def load_banned_ips():
    """Load banned IPs from yaml"""
    try:
        with open('ip_bans.yaml', 'r') as f:
            data = yaml.safe_load(f)
            if not data:
                return []
            bans = data.get('banned_ips')
            return bans if bans is not None else []
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Error loading ip_bans.yaml: {e}")
        return []

def is_safe_ip(ip, safe_list):
    """
    Check if an IP is in the safe list (supports CIDR).
    """
    if not ip or not safe_list:
        return False
        
    for safe in safe_list:
        try:
            # Check for CIDR or simple IP match
            if "/" in safe:  # Assume CIDR
                if ipaddress.ip_address(ip) in ipaddress.ip_network(safe, strict=False):
                    return True
            else:
                if ip == safe:
                    return True
        except ValueError:
            # Continue if invalid IP format in config
            continue
            
    return False

def ban_ip(ip):
    """Add IP to ban list"""
    if is_safe_ip(ip, config.safe_ips):
        print(f"Skipping ban for safe IP: {ip}")
        return

    try:
        bans = load_banned_ips()
        if ip not in bans:
            bans.append(ip)
            with open('ip_bans.yaml', 'w') as f:
                yaml.dump({'banned_ips': bans}, f)
            print(f"BANNED IP: {ip}")
    except Exception as e:
        print(f"Error banning IP {ip}: {e}")

def load_users():
    """Load users from users.yaml"""
    try:
        with open('users.yaml', 'r') as f:
            data = yaml.safe_load(f)
            return data.get('users', {}) if data else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"Error loading users.yaml: {e}")
        return {}

def migrate_passwords():
    """
    Check users.yaml for plain text passwords and migrate them to hashes.
    """
    try:
        if not os.path.exists('users.yaml'):
            return

        with open('users.yaml', 'r') as f:
            data = yaml.safe_load(f)
        
        users = data.get('users', {}) if data else {}
        if not users:
            return

        updated = False
        new_users = {}

        for username, password in users.items():
            # Check if password is already hashed (simple heuristic)
            if not password.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
                print(f"Migrating password for user '{username}' to hash...")
                new_users[username] = generate_password_hash(password)
                updated = True
            else:
                new_users[username] = password
        
        if updated:
            with open('users.yaml', 'w') as f:
                yaml.dump({'users': new_users}, f)
            print("Successfully migrated users.yaml to use hashed passwords.")
            
    except Exception as e:
        print(f"Error migrating passwords: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        users = load_users()
        
        # If no users configured, disable auth
        if not users:
            return f(*args, **kwargs)
            
        # 1. Check for Session
        if 'user' in session:
            return f(*args, **kwargs)
            
        # 2. Not authenticated
        return redirect(url_for('login', next=request.url))
    return decorated_function


def validate_entity_access(entity_id: str):
    """
    Validate that the requested entity is allowed by whitelist/blacklist.
    Aborts with 403 if not allowed.
    """
    if not config.is_entity_allowed(entity_id):
        abort(403, description="Access to this entity is not allowed")


def process_climate_history(history_data: list) -> dict:
    """
    Process history data for climate entities.
    Extracts temperature, setpoint, external temp, and heating status.
    
    Args:
        history_data: Raw history from HA API
        
    Returns:
        Processed data dict for chart rendering
    """
    timestamps = []
    current_temp = []
    target_temp = []
    ext_temp = []
    is_heating = []
    
    for entry in history_data:
        ts = entry.get("last_updated") or entry.get("last_changed")
        if not ts:
            continue

        timestamps.append(ts)

        attrs = entry.get("attributes", {})
        specific_states = attrs.get("specific_states", {})
        
        # Current temperature
        current_temp.append(attrs.get("current_temperature"))
        
        # Target/setpoint temperature
        target_temp.append(attrs.get("temperature"))
        
        # External temperature (can be in specific_states or attributes)
        ext = specific_states.get("ext_current_temperature")
        if ext is None:
            ext = attrs.get("ext_current_temperature")
        ext_temp.append(ext)
        
        # Heating status from hvac_action
        hvac_action = attrs.get("hvac_action", "idle")
        is_heating.append(1 if hvac_action == "heating" else 0)
    
    return {
        "type": "climate",
        "timestamps": timestamps,
        "current_temperature": current_temp,
        "temperature": target_temp,
        "ext_current_temperature": ext_temp,
        "is_heating": is_heating
    }


def process_generic_history(history_data: list, entity_id: str) -> dict:
    """
    Process history data for generic entities (sensors, switches, etc.).
    
    Args:
        history_data: Raw history from HA API
        entity_id: The entity ID being processed
        
    Returns:
        Processed data dict for chart rendering
    """
    timestamps = []
    states = []
    is_numeric = None
    
    for entry in history_data:
        ts = entry.get("last_updated") or entry.get("last_changed")
        if not ts:
            continue

        timestamps.append(ts)
        state = entry.get("state")
        
        # Try to convert to numeric if possible
        if state is not None and state not in ("unknown", "unavailable"):
            try:
                state = float(state)
                if is_numeric is None:
                    is_numeric = True
            except (ValueError, TypeError):
                if is_numeric is None:
                    is_numeric = False
        
        states.append(state)
    
    domain = entity_id.split(".")[0] if "." in entity_id else ""
    
    return {
        "type": "numeric" if is_numeric else "text",
        "domain": domain,
        "timestamps": timestamps,
        "states": states
    }


# =============================================================================
# Routes
# =============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    # Check if IP is banned
    client_ip = request.remote_addr
    if not is_safe_ip(client_ip, config.safe_ips) and client_ip in load_banned_ips():
        abort(403, description="Your IP address has been banned due to too many failed login attempts.")

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        users = load_users()
        
        if username in users and check_password_hash(users[username], password):
            # Success: Reset attempts
            if client_ip in login_attempts:
                del login_attempts[client_ip]
                
            session['user'] = username
            next_page = request.args.get('next')
            parsed = urlparse(next_page) if next_page else None
            safe_next = next_page if (parsed and not parsed.netloc and not parsed.scheme) else None
            return redirect(safe_next or url_for('index'))
        else:
            # Failure: Increment attempts
            attempts = login_attempts.get(client_ip, 0) + 1
            login_attempts[client_ip] = attempts
            
            print(f"Failed login from {client_ip} (Attempt {attempts}/{MAX_LOGIN_ATTEMPTS})")
            
            if attempts >= MAX_LOGIN_ATTEMPTS:
                ban_ip(client_ip)
                abort(403, description="Too many failed attempts. Your IP has been banned.")
            
            return render_template('login.html', error="Invalid username or password")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout user."""
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/')
@login_required
def index():
    """Serve the main application page."""
    return render_template('index.html')


@app.route('/api/config')
@login_required
def get_app_config():
    """Return public configuration for frontend (never expose API token)."""
    return jsonify(config.get_public_config())


@app.route('/api/entities')
@login_required
def list_entities():
    """
    List all available entities from Home Assistant.
    Filters by whitelist/blacklist from config.
    """
    try:
        entities = ha_api.get_entities_summary()
        
        # Apply whitelist/blacklist filtering
        filtered = [
            e for e in entities 
            if config.is_entity_allowed(e["entity_id"])
        ]
        
        return jsonify(filtered)
        
    except HomeAssistantAPIError as e:
        print(f"Error listing entities: {e}")
        return jsonify({"error": e.message}), 500
    except Exception as e:
        print(f"Unexpected error listing entities: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/history/<path:entity_id>')
@login_required
def get_entity_history(entity_id: str):
    """
    Get history for a specific entity.
    
    Query parameters:
        start: ISO datetime string for start of period
        end: ISO datetime string for end of period (default: now)
        
    Returns:
        Processed history data suitable for chart rendering
    """
    # Security check
    validate_entity_access(entity_id)
    
    # Parse date range
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    if not start_str:
        # Default to last N days from config
        end_time = datetime.now()
        start_time = end_time - timedelta(days=config.app.default_history_days)
    else:
        try:
            start_time = parser.parse(start_str)
            end_time = parser.parse(end_str) if end_str else datetime.now()
        except Exception as e:
            return jsonify({"error": f"Invalid date format: {e}"}), 400
    
    try:
        # Fetch history from HA
        history = ha_api.get_history(
            entity_id,
            start_time=start_time,
            end_time=end_time,
            minimal_response=False  # We need attributes
        )
        
        if not history:
            return jsonify({
                "error": "No history data available for this period",
                "timestamps": [],
                "states": []
            })
        
        # Determine entity type and process accordingly
        domain = entity_id.split(".")[0] if "." in entity_id else ""
        
        if domain == "climate":
            result = process_climate_history(history)
        else:
            result = process_generic_history(history, entity_id)
        
        # Add metadata
        result["entity_id"] = entity_id
        result["start"] = start_time.isoformat()
        result["end"] = end_time.isoformat()
        result["count"] = len(result.get("timestamps", []))
        
        return jsonify(result)
        
    except HomeAssistantAPIError as e:
        return jsonify({"error": e.message}), 500


@app.route('/api/details/<path:entity_id>')
@login_required
def get_entity_details(entity_id: str):
    """
    Get details (all attributes) for an entity at a specific timestamp.
    
    Query parameters:
        timestamp: ISO datetime string
        
    Returns:
        Full state entry with all attributes
    """
    # Security check
    validate_entity_access(entity_id)
    
    ts_str = request.args.get('timestamp')
    if not ts_str:
        return jsonify({"error": "Missing timestamp parameter"}), 400
    
    try:
        ts = parser.parse(ts_str)
        
        # Get a small window of history around the timestamp
        start_time = ts - timedelta(minutes=5)
        end_time = ts + timedelta(minutes=5)
        
        history = ha_api.get_history(
            entity_id,
            start_time=start_time,
            end_time=end_time,
            minimal_response=False
        )
        
        if not history:
            return jsonify({"error": "No data found for this timestamp"}), 404
        
        # Find the closest entry to the requested timestamp
        target_ts = ts.timestamp()
        closest = min(history, key=lambda x: abs(
            parser.parse(x.get("last_updated", x.get("last_changed", ""))).timestamp() - target_ts
        ))

        return jsonify(closest)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/attribute-history/<path:entity_id>')
@login_required
def get_attribute_history(entity_id: str):
    """
    Get history for a specific attribute of an entity.
    
    Query parameters:
        key: Attribute key path (e.g., 'smart_pi.error_integral' or 'current_temperature')
        start: ISO datetime string for start of period
        end: ISO datetime string for end of period
        
    Returns:
        History data for the specific attribute
    """
    # Security check
    validate_entity_access(entity_id)
    
    key = request.args.get('key')
    if not key:
        return jsonify({"error": "Missing key parameter"}), 400
    
    # Parse date range
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    if not start_str:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=config.app.default_history_days)
    else:
        try:
            start_time = parser.parse(start_str)
            end_time = parser.parse(end_str) if end_str else datetime.now()
        except Exception as e:
            return jsonify({"error": f"Invalid date format: {e}"}), 400
    
    try:
        history = ha_api.get_history(
            entity_id,
            start_time=start_time,
            end_time=end_time,
            minimal_response=False
        )
        
        timestamps = []
        values = []
        is_numeric = None
        
        # Parse the key path (e.g., 'smart_pi.error_integral' or 'specific_states.smart_pi.error')
        key_parts = key.split('.')
        
        for entry in history:
            ts = entry.get("last_updated") or entry.get("last_changed")
            if not ts:
                continue

            timestamps.append(ts)

            # Navigate to the attribute value
            attrs = entry.get("attributes", {})
            val = attrs

            for part in key_parts:
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = None
                    break

            values.append(val)

            # Determine if numeric (check non-null values)
            if is_numeric is None and val is not None:
                is_numeric = isinstance(val, (int, float))

        # If all values are null, assume numeric
        if is_numeric is None:
            is_numeric = True

        return jsonify({
            "key": key,
            "type": "numeric" if is_numeric else "text",
            "timestamps": timestamps,
            "values": values
        })
        
    except HomeAssistantAPIError as e:
        return jsonify({"error": e.message}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/history-range/<path:entity_id>')
@login_required
def get_history_range(entity_id: str):
    """
    Get the available history date range for an entity.
    
    Returns:
        Dict with 'earliest' and 'latest' datetime strings
    """
    # Security check
    validate_entity_access(entity_id)
    
    try:
        earliest, latest = ha_api.get_available_history_range(entity_id)
        
        return jsonify({
            "entity_id": entity_id,
            "earliest": earliest.isoformat() if earliest else None,
            "latest": latest.isoformat()
        })
        
    except HomeAssistantAPIError as e:
        return jsonify({"error": e.message}), 500


@app.route('/api/export/entity/<path:entity_id>')
@login_required
def export_entity_history(entity_id: str):
    """
    Export full history for an entity as JSON or ZIP.

    Query parameters:
    start: ISO datetime string
    end: ISO datetime string
    zip: If 'true', returns a ZIP file containing the JSON
    """
    # Security check
    validate_entity_access(entity_id)

    start_str = request.args.get('start')
    end_str = request.args.get('end')
    as_zip = request.args.get('zip', 'true').lower() == 'true'

    try:
        # Determine time range
        if start_str:
            start_time = parser.parse(start_str)
            end_time = parser.parse(end_str) if end_str else datetime.now()
        else:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=config.app.default_history_days)

        # Fetch full history (minimal_response=False to get attributes)
        history = ha_api.get_history(
            entity_id,
            start_time=start_time,
            end_time=end_time,
            minimal_response=False
        )

        # Add normalized timestamp field for consistency with attribute export
        export_data = []
        for entry in history:
            ts = entry.get("last_updated") or entry.get("last_changed")
            export_entry = {
                "timestamp": ts,
                **entry
            }
            export_data.append(export_entry)

        # Prepare filename
        base_filename = f"history_{entity_id}_{start_time.strftime('%Y%m%d_%H%M')}_{end_time.strftime('%Y%m%d_%H%M')}"
        json_filename = f"{base_filename}.json"

        from flask import Response

        if as_zip:
            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(json_filename, json.dumps(export_data, indent=2, ensure_ascii=False))
            
            zip_buffer.seek(0)
            zip_filename = f"{base_filename}.zip"
            
            response = Response(
                zip_buffer.getvalue(),
                mimetype='application/zip'
            )
            response.headers["Content-Disposition"] = f"attachment; filename={zip_filename}"
            return response
        else:
            response = Response(
                json.dumps(export_data, indent=2, ensure_ascii=False),
                mimetype='application/json'
            )
            response.headers["Content-Disposition"] = f"attachment; filename={json_filename}"
            return response

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/export/attribute/<path:entity_id>')
@login_required
def export_attribute_history(entity_id: str):
    """
    Export specific attribute history as JSON or ZIP.

    Query parameters:
    key: Attribute key path
    start: ISO datetime string
    end: ISO datetime string
    zip: If 'true', returns a ZIP file containing the JSON
    """
    # Security check
    validate_entity_access(entity_id)

    key = request.args.get('key')
    if not key:
        return jsonify({"error": "Missing key parameter"}), 400

    start_str = request.args.get('start')
    end_str = request.args.get('end')
    as_zip = request.args.get('zip', 'true').lower() == 'true'

    try:
        # Determine time range
        if start_str:
            start_time = parser.parse(start_str)
            end_time = parser.parse(end_str) if end_str else datetime.now()
        else:
            end_time = datetime.now()
            start_time = end_time - timedelta(days=config.app.default_history_days)

        # Fetch full history
        history = ha_api.get_history(
            entity_id,
            start_time=start_time,
            end_time=end_time,
            minimal_response=False
        )

        export_data = []
        key_parts = key.split('.')

        for entry in history:
            ts = entry.get("last_updated") or entry.get("last_changed")
            if not ts:
                continue

            # Navigate to value
            attrs = entry.get("attributes", {})
            val = attrs

            for part in key_parts:
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = None
                    break

            if val is not None:
                export_data.append({
                    "timestamp": ts,
                    "value": val
                })

        base_filename = f"history_{entity_id}_{key}_{start_time.strftime('%Y%m%d_%H%M')}_{end_time.strftime('%Y%m%d_%H%M')}"
        json_filename = f"{base_filename}.json"

        from flask import Response

        if as_zip:
            # Create ZIP file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(json_filename, json.dumps(export_data, indent=2, ensure_ascii=False))
            
            zip_buffer.seek(0)
            zip_filename = f"{base_filename}.zip"
            
            response = Response(
                zip_buffer.getvalue(),
                mimetype='application/zip'
            )
            response.headers["Content-Disposition"] = f"attachment; filename={zip_filename}"
            return response
        else:
            response = Response(
                json.dumps(export_data, indent=2, ensure_ascii=False),
                mimetype='application/json'
            )
            response.headers["Content-Disposition"] = f"attachment; filename={json_filename}"
            return response

    except Exception as e:
        return jsonify({"error": str(e)}), 400


BETTER_HISTORY_FORMAT = "ha-better-history-series-v1"


def _parse_import_timestamp(value):
    """Return a Unix timestamp, or None when the value is invalid."""
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return parser.parse(value).timestamp()
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def _normalize_better_history_range(value, field_name):
    """Validate an optional ha-better-history date range."""
    if value is None:
        return None, None
    if not isinstance(value, dict):
        return None, f"Invalid {field_name}: expected an object"

    start = value.get("start")
    end = value.get("end")
    parsed_start = _parse_import_timestamp(start)
    parsed_end = _parse_import_timestamp(end)
    if parsed_start is None or parsed_end is None or parsed_start >= parsed_end:
        return None, f"Invalid {field_name}: expected a valid start and end range"

    return {"start": start, "end": end}, None


def process_better_history_series_data(data, filename):
    """Validate and normalize a ha-better-history-series-v1 export."""
    series_items = data.get("series")
    if not isinstance(series_items, list) or not series_items:
        return {"error": "Invalid ha-better-history format: expected non-empty series"}, 400

    loaded_range, error = _normalize_better_history_range(
        data.get("loadedRange"), "loadedRange"
    )
    if error:
        return {"error": error}, 400

    view_range, error = _normalize_better_history_range(
        data.get("viewRange"), "viewRange"
    )
    if error:
        return {"error": error}, 400

    normalized_series = []
    all_timestamps = []
    allowed_value_types = {"number", "boolean", "string"}
    allowed_line_modes = {"line", "column", "stair"}
    allowed_scale_preferences = {"auto", "primary", "secondary"}

    for index, item in enumerate(series_items):
        if not isinstance(item, dict):
            return {"error": f"Invalid series at index {index}: expected an object"}, 400

        series_id = item.get("id")
        entity_id = item.get("entityId")
        label = item.get("label")
        value_type = item.get("valueType")
        points = item.get("points")

        if not isinstance(series_id, str) or not series_id.strip():
            return {"error": f"Invalid series at index {index}: missing id"}, 400
        if not isinstance(entity_id, str) or not entity_id.strip():
            return {"error": f"Invalid series at index {index}: missing entityId"}, 400
        if not isinstance(label, str) or not label.strip():
            return {"error": f"Invalid series at index {index}: missing label"}, 400
        if value_type not in allowed_value_types:
            return {"error": f"Invalid series at index {index}: unsupported valueType"}, 400
        if not isinstance(points, list):
            return {"error": f"Invalid series at index {index}: expected points list"}, 400

        normalized_points = []
        for point in points:
            if not isinstance(point, dict):
                continue

            timestamp = point.get("timestamp")
            parsed_timestamp = _parse_import_timestamp(timestamp)
            value = point.get("value")
            if parsed_timestamp is None:
                continue

            valid_value = (
                value_type == "number"
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
            ) or (
                value_type == "boolean" and isinstance(value, bool)
            ) or (
                value_type == "string" and isinstance(value, str)
            )
            if not valid_value:
                continue

            normalized_points.append({
                "timestamp": timestamp,
                "value": value,
                "_sort_time": parsed_timestamp,
            })
            all_timestamps.append((parsed_timestamp, timestamp))

        normalized_points.sort(key=lambda point: point["_sort_time"])
        for point in normalized_points:
            del point["_sort_time"]

        normalized_item = {
            "id": series_id,
            "entityId": entity_id,
            "label": label,
            "valueType": value_type,
            "lineMode": item.get("lineMode")
            if item.get("lineMode") in allowed_line_modes else "line",
            "scalePreference": item.get("scalePreference")
            if item.get("scalePreference") in allowed_scale_preferences else "auto",
            "points": normalized_points,
        }

        for optional_key in ("attribute", "unit", "color"):
            optional_value = item.get(optional_key)
            if isinstance(optional_value, str) and optional_value.strip():
                normalized_item[optional_key] = optional_value

        normalized_series.append(normalized_item)

    display_range = view_range or loaded_range
    if display_range:
        start = display_range["start"]
        end = display_range["end"]
    elif all_timestamps:
        all_timestamps.sort(key=lambda item: item[0])
        start = all_timestamps[0][1]
        end = all_timestamps[-1][1]
    else:
        return {"error": "Invalid ha-better-history format: no usable date range"}, 400

    return {
        "type": "series",
        "filename": filename,
        "data": {
            "format": BETTER_HISTORY_FORMAT,
            "exportedAt": data.get("exportedAt"),
            "loadedRange": loaded_range,
            "viewRange": view_range,
            "start": start,
            "end": end,
            "count": sum(len(item["points"]) for item in normalized_series),
            "series": normalized_series,
        },
    }, 200


def process_imported_json_data(data, filename):
    """
    Process imported JSON data and return the appropriate response.
    This is a helper function used by both direct JSON import and ZIP import.
    
    Args:
        data: Parsed JSON data
        filename: Original filename for display
        
    Returns:
        Tuple of (response_dict, status_code)
    """
    if isinstance(data, dict) and data.get("format") == BETTER_HISTORY_FORMAT:
        return process_better_history_series_data(data, filename)

    if not isinstance(data, list) or not data:
        return {"error": "Invalid JSON format: expected a non-empty list"}, 400

    # Determine format based on first entry
    first_entry = data[0]

    # Check if it's an attribute export (has 'value' and 'timestamp')
    if 'value' in first_entry and 'timestamp' in first_entry:
        # Process as attribute history
        timestamps = []
        values = []
        is_numeric = None

        for entry in data:
            ts = entry.get('timestamp')
            val = entry.get('value')

            if not ts:
                continue

            timestamps.append(ts)
            values.append(val)

            if is_numeric is None and val is not None:
                is_numeric = isinstance(val, (int, float))

        if is_numeric is None:
            is_numeric = True

        return {
            "type": "attribute",
            "filename": filename,
            "data": {
                "key": "Imported Attribute", # We don't have the original key, just filename
                "type": "numeric" if is_numeric else "text",
                "timestamps": timestamps,
                "values": values
            }
        }, 200

    # Check if it's an entity export (has 'attributes', 'state', 'entity_id')
    elif 'attributes' in first_entry and 'entity_id' in first_entry:
        entity_id = first_entry.get('entity_id')
        import_id = str(uuid.uuid4())

        # Cache the raw data for details lookup
        imported_data_cache[import_id] = data

        # Determine processing method
        domain = entity_id.split(".")[0] if "." in entity_id else ""

        if domain == "climate":
            result = process_climate_history(data)
        else:
            result = process_generic_history(data, entity_id)

        # Add metadata
        result["entity_id"] = entity_id
        result["import_id"] = import_id # Pass back ID for details lookup
        if data:
            # Use data timestamps since we don't have request params
            # Sort by timestamp to be sure (assuming ISO format)
            sorted_ts = sorted([
                e.get("last_updated") or e.get("last_changed")
                for e in data
                if e.get("last_updated") or e.get("last_changed")
            ])
            if sorted_ts:
                result["start"] = sorted_ts[0]
                result["end"] = sorted_ts[-1]

        result["count"] = len(result.get("timestamps", []))

        return {
            "type": "entity",
            "filename": filename,
            "data": result
        }, 200

    else:
        return {
            "error": (
                "Unrecognized JSON format. Must be an Entity export, Attribute export, "
                "or ha-better-history-series-v1 export."
            )
        }, 400


@app.route('/api/import', methods=['POST'])
@login_required
def import_history():
    """
    Import history data from a JSON file or ZIP file containing a JSON file.
    Detects if it is a full entity export or an attribute export.
    Returns the processed data for visualization.
    
    For ZIP files:
    - Only accepts ZIP containing exactly one .json file
    - Ignores non-JSON files and shows error if multiple JSON files found
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    filename = file.filename.lower()
    
    # Check if it's a ZIP file
    if filename.endswith('.zip'):
        try:
            # Read the file into memory since it's a file-like object
            file_content = file.read()
            
            with zipfile.ZipFile(io.BytesIO(file_content), 'r') as zf:
                # List all files in the ZIP
                all_files = zf.namelist()
                
                # Filter for .json files (excluding directories)
                json_files = [f for f in all_files if f.lower().endswith('.json') and not f.endswith('/')]
                
                if len(json_files) == 0:
                    return jsonify({"error": "No .json file found in the ZIP archive"}), 400
                
                if len(json_files) > 1:
                    return jsonify({
                        "error": f"Multiple .json files found in ZIP ({len(json_files)}). Please include only one JSON file."
                    }), 400
                
                # Extract and process the single JSON file
                json_filename = json_files[0]
                
                # Security check: prevent path traversal
                if '..' in json_filename or json_filename.startswith('/'):
                    return jsonify({"error": "Invalid file path in ZIP archive"}), 400
                
                with zf.open(json_filename) as json_file:
                    try:
                        data = json.load(json_file)
                    except json.JSONDecodeError:
                        return jsonify({"error": f"Invalid JSON file in ZIP: {json_filename}"}), 400
                
                # Process the JSON data
                result, status = process_imported_json_data(data, json_filename)
                return jsonify(result), status
                
        except zipfile.BadZipFile:
            return jsonify({"error": "Invalid or corrupted ZIP file"}), 400
        except Exception as e:
            print(f"ZIP Import error: {e}")
            return jsonify({"error": str(e)}), 500
    
    # Regular JSON file import
    try:
        data = json.load(file)
        result, status = process_imported_json_data(data, file.filename)
        return jsonify(result), status

    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file"}), 400
    except Exception as e:
        print(f"Import error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/import/<import_id>', methods=['DELETE'])
@login_required
def delete_import(import_id: str):
    """
    Remove imported data from cache to free up memory.
    """
    if import_id in imported_data_cache:
        del imported_data_cache[import_id]
        print(f"Memory freed for import session: {import_id}")
        return jsonify({"success": True})
    return jsonify({"error": "Import session not found"}), 404

@app.route('/api/details/imported/<import_id>')
@login_required
def get_imported_details(import_id: str):
    """
    Get details for an imported entity at a specific timestamp.
    """
    if import_id not in imported_data_cache:
        return jsonify({"error": "Import session expired or not found"}), 404
        
    data = imported_data_cache[import_id]
    
    ts_str = request.args.get('timestamp')
    if not ts_str:
        return jsonify({"error": "Missing timestamp parameter"}), 400
        
    try:
        ts = parser.parse(ts_str)
        target_ts = ts.timestamp()
        
        # Find closest entry in the cached data
        # Only check entries that have a timestamp
        valid_entries = [
            x for x in data
            if x.get("last_updated") or x.get("last_changed")
        ]

        if not valid_entries:
            return jsonify({"error": "No valid timestamps in imported data"}), 404

        closest = min(valid_entries, key=lambda x: abs(
            parser.parse(x.get("last_updated", x.get("last_changed"))).timestamp() - target_ts
        ))
        
        # We assume the imported data is already full structure
        return jsonify(closest)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/imported/attribute-history/<import_id>')
@login_required
def get_imported_attribute_history(import_id: str):
    """
    Get history for a specific attribute from imported data.
    """
    if import_id not in imported_data_cache:
        return jsonify({"error": "Import session expired or not found"}), 404
        
    data = imported_data_cache[import_id]
    
    key = request.args.get('key')
    if not key:
        return jsonify({"error": "Missing key parameter"}), 400
        
    try:
        timestamps = []
        values = []
        is_numeric = None
        
        # Parse the key path
        key_parts = key.split('.')
        
        for entry in data:
            ts = entry.get("last_updated") or entry.get("last_changed")
            if not ts:
                continue

            timestamps.append(ts)

            # Navigate to the attribute value
            attrs = entry.get("attributes", {})
            val = attrs

            for part in key_parts:
                if isinstance(val, dict):
                    val = val.get(part)
                else:
                    val = None
                    break

            values.append(val)

            # Determine if numeric (check non-null values)
            if is_numeric is None and val is not None:
                is_numeric = isinstance(val, (int, float))

        # If all values are null, assume numeric
        if is_numeric is None:
            is_numeric = True

        return jsonify({
            "key": key,
            "type": "numeric" if is_numeric else "text",
            "timestamps": timestamps,
            "values": values
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Auto-migrate passwords if needed
    migrate_passwords()

    # Test HA connection on startup
    print("Testing Home Assistant connection...")
    try:
        if ha_api.test_connection():
            print("✓ Successfully connected to Home Assistant")
    except HomeAssistantAPIError as e:
        print(f"✗ Failed to connect to Home Assistant: {e.message}")
        print("  The server will start anyway, but API calls will fail.")
    
    print(f"\nStarting HA Entity Explorer on {HOST}:{PORT}")
    print(f"Open: http://{HOST if HOST != '0.0.0.0' else 'localhost'}:{PORT}")
    if HOST == "0.0.0.0":
        print("Also accessible from other machines using your IP address")
    
    # SA-02: Disable debug mode in production
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, host=HOST, port=PORT)
