"""
Home Assistant REST API Client.
Handles communication with the Home Assistant instance for entity states and history.
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import urljoin


class HomeAssistantAPIError(Exception):
    """Exception raised when HA API returns an error."""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class HomeAssistantAPI:
    """Client for Home Assistant REST API."""
    
    def __init__(self, url: str, token: str):
        """
        Initialize the API client.
        
        Args:
            url: Base URL of Home Assistant (e.g., 'http://homeassistant.local:8123')
            token: Long-lived access token
        """
        self.base_url = url.rstrip('/')
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self._states_cache = None
        self._states_cache_time = None
        self._cache_ttl = 60  # Cache states for 60 seconds
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Make a request to the HA API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/api/states')
            **kwargs: Additional arguments for requests
            
        Returns:
            Parsed JSON response
            
        Raises:
            HomeAssistantAPIError: If request fails
        """
        # Helper to join URL parts safely, whether they have slashes or not
        # This is needed because urljoin discards path components of base_url if endpoint starts with /
        # which breaks when using the Supervisor proxy at http://supervisor/core
        base = self.base_url.rstrip('/')
        path = endpoint.lstrip('/')
        url = f"{base}/{path}"
        
        print(f"DEBUG: Requesting {method} {url}")
        try:
            response = requests.request(
                method, 
                url, 
                headers=self.headers,
                timeout=30,
                **kwargs
            )
            
            if response.status_code == 401:
                raise HomeAssistantAPIError(
                    "Authentication failed. Check your API token.", 
                    status_code=401
                )
            
            if response.status_code == 404:
                raise HomeAssistantAPIError(
                    f"Endpoint not found: {endpoint}", 
                    status_code=404
                )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.ConnectionError:
            raise HomeAssistantAPIError(
                f"Cannot connect to Home Assistant at {self.base_url}. "
                "Check the URL and ensure HA is running."
            )
        except requests.exceptions.Timeout:
            raise HomeAssistantAPIError("Request to Home Assistant timed out.")
        except requests.exceptions.RequestException as e:
            raise HomeAssistantAPIError(f"Request failed: {str(e)}")
    
    def test_connection(self) -> bool:
        """
        Test the connection to Home Assistant.
        
        Returns:
            True if connection is successful
            
        Raises:
            HomeAssistantAPIError: If connection fails
        """
        result = self._request("GET", "/api/")
        return result.get("message") == "API running."
    
    def get_states(self, force_refresh: bool = False) -> List[Dict]:
        """
        Get all entity states from Home Assistant.
        Uses caching to avoid excessive API calls.
        
        Args:
            force_refresh: Force refresh even if cache is valid
            
        Returns:
            List of entity state dictionaries
        """
        now = datetime.now()
        
        # Check cache validity
        if (not force_refresh 
            and self._states_cache is not None 
            and self._states_cache_time is not None
            and (now - self._states_cache_time).total_seconds() < self._cache_ttl):
            return self._states_cache
        
        # Fetch fresh data
        states = self._request("GET", "/api/states")
        
        # Update cache
        self._states_cache = states
        self._states_cache_time = now
        
        return states
    
    def get_entity_state(self, entity_id: str) -> Optional[Dict]:
        """
        Get the current state of a specific entity.
        
        Args:
            entity_id: Entity ID (e.g., 'climate.living_room')
            
        Returns:
            Entity state dictionary or None if not found
        """
        try:
            return self._request("GET", f"/api/states/{entity_id}")
        except HomeAssistantAPIError as e:
            if e.status_code == 404:
                return None
            raise
    
    def get_history(
        self, 
        entity_id: str, 
        start_time: datetime,
        end_time: Optional[datetime] = None,
        minimal_response: bool = True,
        significant_changes_only: bool = False
    ) -> List[Dict]:
        """
        Get history for an entity over a time period.
        
        Args:
            entity_id: Entity ID to get history for
            start_time: Start of the time period
            end_time: End of the time period (defaults to now)
            minimal_response: If True, only return last_changed, state, attributes
            significant_changes_only: If True, skip entries with only attribute changes
            
        Returns:
            List of state history entries for the entity
        """
        if end_time is None:
            end_time = datetime.now()
        
        # Format times as ISO strings
        start_str = start_time.isoformat()
        end_str = end_time.isoformat()
        
        # Build endpoint with timestamp
        endpoint = f"/api/history/period/{start_str}"
        
        # Build query parameters
        params = {
            "filter_entity_id": entity_id,
            "end_time": end_str,
            "minimal_response": str(minimal_response).lower(),
            "significant_changes_only": str(significant_changes_only).lower()
        }
        
        result = self._request("GET", endpoint, params=params)
        
        # The API returns a list of lists (one per entity)
        # We requested a single entity, so take the first list
        if result and len(result) > 0:
            return result[0]
        
        return []
    
    def get_available_history_range(self, entity_id: str) -> Tuple[Optional[datetime], datetime]:
        """
        Determine the available date range for an entity's history.
        
        Note: Home Assistant typically keeps history for a configured retention period.
        The exact start depends on the recorder configuration.
        
        Args:
            entity_id: Entity ID to check
            
        Returns:
            Tuple of (earliest_available, now)
            earliest_available may be None if unknown
        """
        now = datetime.now()
        
        # Try to get the oldest available data by querying far back
        # Home Assistant default retention is 10 days
        # We'll try 30 days back and see what we get
        far_back = now - timedelta(days=30)
        
        history = self.get_history(
            entity_id, 
            start_time=far_back,
            end_time=far_back + timedelta(hours=1),
            minimal_response=True
        )
        
        if history:
            # Parse the earliest timestamp we got
            from dateutil import parser as date_parser
            earliest = date_parser.parse(history[0].get("last_changed", history[0].get("last_updated")))
            return (earliest, now)
        
        # If no data from 30 days ago, try progressively shorter periods
        for days in [14, 7, 3, 1]:
            test_time = now - timedelta(days=days)
            history = self.get_history(
                entity_id,
                start_time=test_time,
                end_time=test_time + timedelta(hours=1),
                minimal_response=True
            )
            if history:
                from dateutil import parser as date_parser
                earliest = date_parser.parse(history[0].get("last_changed", history[0].get("last_updated")))
                return (earliest, now)
        
        # No history found
        return (None, now)
    
    def get_entities_summary(self) -> List[Dict]:
        """
        Get a summary of all entities suitable for the entity selector.
        
        Returns:
            List of dicts with entity_id, friendly_name, domain, and state
        """
        states = self.get_states()
        
        entities = []
        for state in states:
            entity_id = state.get("entity_id", "")
            attributes = state.get("attributes", {})
            
            entities.append({
                "entity_id": entity_id,
                "friendly_name": attributes.get("friendly_name", entity_id),
                "domain": entity_id.split(".")[0] if "." in entity_id else "",
                "state": state.get("state", "unknown"),
                "icon": attributes.get("icon", "")
            })
        
        # Sort by friendly_name
        entities.sort(key=lambda x: x["friendly_name"].lower())
        
        return entities
