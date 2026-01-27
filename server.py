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
from flask import Flask, render_template, jsonify, request, abort
from dateutil import parser

from config import load_config
from ha_api import HomeAssistantAPI, HomeAssistantAPIError

app = Flask(__name__)

# Load configuration
config = load_config()

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
        ts = entry.get("last_changed") or entry.get("last_updated")
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
        ts = entry.get("last_changed") or entry.get("last_updated")
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

@app.route('/')
def index():
    """Serve the main application page."""
    return render_template('index.html')


@app.route('/api/config')
def get_app_config():
    """Return public configuration for frontend (never expose API token)."""
    return jsonify(config.get_public_config())


@app.route('/api/entities')
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
        return jsonify({"error": e.message}), 500


@app.route('/api/history/<path:entity_id>')
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
            parser.parse(x.get("last_changed", x.get("last_updated", ""))).timestamp() - target_ts
        ))
        
        return jsonify(closest)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/attribute-history/<path:entity_id>')
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
            ts = entry.get("last_changed") or entry.get("last_updated")
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
            
            # Determine if numeric
            if is_numeric is None and val is not None:
                is_numeric = isinstance(val, (int, float))
        
        if is_numeric is None:
            is_numeric = False
        
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


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
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
    
    app.run(debug=True, host=HOST, port=PORT)
