import pytest
from unittest.mock import patch, MagicMock
from ha_entity_explorer.server import app


@pytest.mark.parametrize("next_url,should_allow", [
    ("https://evil.com/phish", False),
    ("//evil.com/phish", False),
    ("http://attacker.org/steal-creds", False),
    ("/dashboard", True),
    ("/entities?filter=light", True),
])
def test_login_redirect_rejects_external_urls(next_url, should_allow):
    """Invariant: After login, redirect must only go to local paths, never external URLs."""
    with app.test_client() as client:
        # Attempt login with the 'next' parameter set to potentially malicious URL
        response = client.post(
            f"/login?next={next_url}",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        
        # If there's a redirect response, check the Location header
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location", "")
            # Security invariant: redirect must never point to an external host
            if not should_allow:
                # The location must not contain the external URL
                assert not location.startswith("http://evil.com"), \
                    f"Open redirect to external URL: {location}"
                assert not location.startswith("https://evil.com"), \
                    f"Open redirect to external URL: {location}"
                assert not location.startswith("//evil.com"), \
                    f"Open redirect to external URL: {location}"
                assert not location.startswith("http://attacker.org"), \
                    f"Open redirect to external URL: {location}"
                # General check: if location is absolute, it must be same origin
                if location.startswith("http://") or location.startswith("https://") or location.startswith("//"):
                    parsed_location = location.lstrip("/")
                    assert "localhost" in parsed_location or "127.0.0.1" in parsed_location, \
                        f"Redirect to external domain detected: {location}"