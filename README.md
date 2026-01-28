# HA Entity Explorer

A standalone web application to explore and visualize the history of any Home Assistant entity and its attributes

## Features

- **Entity Browser**: Search and select any entity from your Home Assistant instance
- **Interactive Charts**: Zoom, pan, and explore entity history with ECharts
- **Attribute Explorer**: Click on chart points to view all entity attributes
- **Custom Date Range**: Select the time period you want to analyze
- **Multi-language**: Available in English and French
- **Entity Filtering**: Whitelist/blacklist entities for security

<img width="1889" height="902" alt="image" src="https://github.com/user-attachments/assets/867d60c5-401a-46e5-855c-38ec1135cdff" />
<img width="1884" height="899" alt="image" src="https://github.com/user-attachments/assets/eb786fba-ba12-4d98-acd4-8fd0ae89b594" />


## Quick Start

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
```

To generate a long-lived access token:
1. Go to your Home Assistant profile
2. Scroll to "Long-Lived Access Tokens"
3. Click "Create Token"

### 3. Run

```bash
python server.py
```

Open your browser at: http://localhost:5000

## Authentication

The application supports two methods of authentication:

1.  **Local Authentication**:
    Create a `users.yaml` file in the application directory (see `users.yaml.example`):
    ```yaml
    users:
      myuser: mypassword
      admin: admin123
    ```
    If `users.yaml` is not present or contains no users, authentication is **disabled**.

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `home_assistant.url` | Home Assistant URL | Required |
| `home_assistant.api_token` | Long-lived access token | Required |
| `app.language` | Interface language (fr/en) | fr |
| `app.default_history_days` | Days of history to load | 4 |
| `app.host` | Network interface | 0.0.0.0 |
| `app.port` | Server port | 5000 |
| `whitelist` | Only show these entities | [] |
| `blacklist` | Hide these entities | [] |

## Using with pipx (Alternative)

No manual installation needed:

```bash
pipx run server.py
```

## License

MIT
