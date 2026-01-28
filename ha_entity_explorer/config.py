"""
Configuration loader for HA Entity Explorer.
Handles loading and validation of config.yaml settings.
"""

import os
import sys
import yaml
import fnmatch
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class HomeAssistantConfig:
    """Home Assistant connection configuration."""
    url: str
    api_token: str


@dataclass
class AppConfig:
    """Application settings."""
    language: str = "fr"
    default_history_days: int = 4
    host: str = "0.0.0.0"
    port: int = 5000
    secret_key: str = None


@dataclass
class Config:
    """Main configuration container."""
    home_assistant: HomeAssistantConfig
    app: AppConfig
    whitelist: List[str] = field(default_factory=list)
    blacklist: List[str] = field(default_factory=list)
    safe_ips: List[str] = field(default_factory=list)
    
    def is_entity_allowed(self, entity_id: str) -> bool:
        """
        Check if an entity is allowed based on whitelist/blacklist rules.
        Whitelist takes precedence over blacklist.
        Supports wildcards (e.g. 'climate.*').
        
        Args:
            entity_id: The entity ID to check (e.g., 'climate.living_room')
            
        Returns:
            True if entity is allowed, False otherwise
        """
        # If whitelist is defined and non-empty, only allow those entities
        if self.whitelist:
            for pattern in self.whitelist:
                if fnmatch.fnmatch(entity_id, pattern):
                    return True
            return False
        
        # If blacklist is defined, exclude those entities
        if self.blacklist:
            for pattern in self.blacklist:
                if fnmatch.fnmatch(entity_id, pattern):
                    return False
        
        # No filtering, allow all
        return True
    
    def get_public_config(self) -> dict:
        """
        Return configuration safe to expose to frontend.
        Never expose API token!
        """
        return {
            "language": self.app.language,
            "defaultHistoryDays": self.app.default_history_days,
            "haUrl": self.home_assistant.url  # URL might be useful for display
        }


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file. Defaults to config.yaml in script directory.
        
    Returns:
        Config object with loaded settings.
        
    Raises:
        SystemExit: If config file not found or invalid.
    """
    if config_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "app_config.yaml")
    
    if not os.path.exists(config_path):
        print(f"Error: Configuration file not found: {config_path}")
        print("Please copy app_config.yaml.example to app_config.yaml and fill in your values.")
        sys.exit(1)
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in configuration file: {e}")
        sys.exit(1)
    
    # Validate required sections
    if "home_assistant" not in data:
        print("Error: Missing 'home_assistant' section in config.yaml")
        sys.exit(1)
    
    ha_data = data["home_assistant"]
    if not ha_data.get("url") or not ha_data.get("api_token"):
        print("Error: 'url' and 'api_token' are required in home_assistant section")
        sys.exit(1)
    
    # Build config objects
    ha_config = HomeAssistantConfig(
        url=ha_data["url"].rstrip("/"),  # Remove trailing slash
        api_token=ha_data["api_token"]
    )
    
    app_data = data.get("app", {})
    app_config = AppConfig(
        language=app_data.get("language", "fr"),
        default_history_days=app_data.get("default_history_days", 4),
        host=app_data.get("host", "0.0.0.0"),
        port=app_data.get("port", 5000),
        secret_key=app_data.get("secret_key")
    )
    
    # Validate language
    if app_config.language not in ("fr", "en"):
        print(f"Warning: Unknown language '{app_config.language}', defaulting to 'fr'")
        app_config.language = "fr"
    
    whitelist = data.get("whitelist", []) or []
    blacklist = data.get("blacklist", []) or []
    safe_ips = data.get("safe_ips", []) or []
    
    # Always include localhost in safe_ips
    if "127.0.0.1" not in safe_ips:
        safe_ips.append("127.0.0.1")
    if "::1" not in safe_ips:
        safe_ips.append("::1")
    
    config = Config(
        home_assistant=ha_config,
        app=app_config,
        whitelist=whitelist,
        blacklist=blacklist,
        safe_ips=safe_ips
    )
    
    print(f"Configuration loaded successfully")
    print(f"  Home Assistant URL: {ha_config.url}")
    print(f"  Language: {app_config.language}")
    print(f"  Default history days: {app_config.default_history_days}")
    if whitelist:
        print(f"  Whitelist: {len(whitelist)} entities")
    if blacklist:
        print(f"  Blacklist: {len(blacklist)} entities")
    
    return config
