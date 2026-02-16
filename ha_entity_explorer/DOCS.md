<p align="center">
  <img src="icon.png" width="128" height="128" alt="HA Entity Explorer Logo">
</p>

# HA Entity Explorer - Technical Documentation

This document contains detailed information for running **HA Entity Explorer** as a standalone Python application.

## Features

- **Entity Browser**: Search and select any entity from your Home Assistant instance
- **Interactive Charts**: Zoom, pan, and explore entity history with ECharts
- **Attribute Explorer**: Click on chart points to view all entity attributes
- **Custom Date Range**: Select the time period you want to analyze
- **Data Export/Import**: Export and import entity or attribute history as JSON or ZIP files
- **Multi-language**: Available in English and French
- **Entity Filtering**: Whitelist/blacklist entities for security

## Data Export & Import

### Export
You can export entity history or specific attribute history by clicking the export button in the chart toolbox. Data is exported as a ZIP file containing a JSON file by default. You can also choose to export as plain JSON by modifying the URL parameter `zip=false`.

### Import
Click the upload button (⬆️) in the navigation bar to import previously exported data. The application accepts both:
- **JSON files**: Direct JSON export files
- **ZIP files**: ZIP archives containing a single JSON file

> [!IMPORTANT]
> **Ingress File Size Limitation**: When using Home Assistant Ingress, large file uploads may be blocked or fail. If you experience issues importing large JSON files:
> - **Use ZIP format**: ZIP files are smaller and more likely to succeed
> - **Direct access**: Connect directly to the application using its port (e.g., `http://your-server:5000`) instead of through Ingress

<img alt="image" src="https://github.com/user-attachments/assets/867d60c5-401a-46e5-855c-38ec1135cdff" />
<img alt="image" src="https://github.com/user-attachments/assets/eb786fba-ba12-4d98-acd4-8fd0ae89b594" />


## Standalone Installation (Non-Add-on)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

Copy the example configuration file:

```bash
cp config.yaml.example config.yaml
```

Edit `config.yaml` with your Home Assistant details:

```yaml
home_assistant:
  url: "http://homeassistant.local:8123"
  api_token: "your_long_lived_access_token_here"

app:
  language: "en"  # or "fr"
  default_history_days: 4
  host: "0.0.0.0"
  host: "0.0.0.0"
  port: 5000
  secret_key: "change_me_to_random_string" # Required for security

# Security: IPs that will never be banned
safe_ips:
#  - "192.168.1.50" # Example IP


# Optional: Restrict access to specific entities
# whitelist:
#   - climate.living_room
# blacklist:
#   - sensor.private_data
```

### 3. Run

```bash
python server.py
```

Open your browser at: http://localhost:5000

## Requirements

- Python 3.9+
- Home Assistant instance reachable via network
- Long-Lived Access Token from Home Assistant
To generate a long-lived access token:
1. Go to your Home Assistant profile
2. Scroll to "Long-Lived Access Tokens"
3. Click "Create Token"

## Authentication

The application supports authentication:

    Create a `users.yaml` file in the application directory (see `users.yaml.example`):
    ```yaml
    users:
      myuser: mypassword
      admin: admin123
    users:
      myuser: mypassword
      admin: admin123
    ```
    On startup, plain text passwords will be automatically migrated to secure hashes.
    
    If `users.yaml` is not present or contains no users, authentication is **disabled**.

## Security Features

### IP Banning
To protect against brute-force attacks, the application implements rate limiting:
- **Limit**: 5 failed login attempts per IP address.
- **Action**: The IP is strictly banned (403 Forbidden).
- **Storage**: Banned IPs are stored in `ip_bans.yaml` (automatically created if not present).
- **Safe IPs**: Localhost (`127.0.0.1`, `::1`) are always safe. You can add more via `safe_ips` in `config.yaml`.
- **Unban**: To unban an IP, manually remove it from `ip_bans.yaml` (the server reads this file on every request, so no restart is needed).

### Entity Filtering
You can restrict which entities are visible in the explorer:

- **whitelist**: List of entity IDs. If defined, **ONLY** these entities will be accessible.
- **blacklist**: List of entity IDs to exclude.
- **Rules**:
    - If `whitelist` is used, `blacklist` is ignored.
    - If both are empty, all entities are visible.

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `home_assistant.url` | Home Assistant URL | Required |
| `home_assistant.api_token` | Long-lived access token | Required |
| `app.language` | Interface language (fr/en) | fr |
| `app.default_history_days` | Days of history to load | 4 |
| `app.host` | Network interface | 0.0.0.0 |
| `app.port` | Server port | 5000 |
| `app.secret_key` | Secret for sessions | Required |
| `whitelist` | Only show these entities | [] |
| `blacklist` | Hide these entities | [] |
| `safe_ips` | IPs exempt from banning (always includes localhost) | [] |

## Using with pipx (Alternative)

No manual installation needed:

```bash
pipx run server.py
```

## License

MIT
