from datetime import datetime, timezone
from pathlib import Path
import re
from unittest.mock import patch

import pytest

from ha_entity_explorer.ha_api import HomeAssistantAPI
from ha_entity_explorer.server import app


APP_DIR = Path(__file__).parents[1] / "ha_entity_explorer"


def test_export_ui_offers_significant_changes_filter_disabled_by_default():
    template = (APP_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    javascript = (APP_DIR / "static" / "js" / "main.js").read_text(
        encoding="utf-8"
    )

    checkbox = re.search(
        r'<input[^>]+id="significant-changes-checkbox"[^>]*>', template
    )
    assert checkbox is not None
    assert "checked" not in checkbox.group(0)
    assert "significant_changes_only:" in javascript
    assert "significantChangesCheckbox?.checked" in javascript


@pytest.mark.parametrize(
    ("minimal_response", "significant_changes_only", "no_attributes", "expected_options"),
    [
        (False, False, False, {"significant_changes_only": "0"}),
        (
            True,
            True,
            True,
            {
                "minimal_response": "1",
                "significant_changes_only": "1",
                "no_attributes": "1",
            },
        ),
    ],
)
def test_get_history_sends_home_assistant_query_options(
    minimal_response, significant_changes_only, no_attributes, expected_options
):
    client = HomeAssistantAPI("http://home-assistant:8123", "token")
    start = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, 4, 5, tzinfo=timezone.utc)

    with patch.object(client, "_request", return_value=[[]]) as request_mock:
        client.get_history(
            "sensor.smartpi",
            start,
            end,
            minimal_response=minimal_response,
            significant_changes_only=significant_changes_only,
            no_attributes=no_attributes,
        )

    _, endpoint = request_mock.call_args.args
    params = request_mock.call_args.kwargs["params"]
    assert endpoint == f"/api/history/period/{start.isoformat()}"
    assert params == {
        "filter_entity_id": "sensor.smartpi",
        "end_time": end.isoformat(),
        **expected_options,
    }


def test_entity_export_defaults_to_full_attribute_history():
    history = [
        {
            "entity_id": "sensor.smartpi",
            "state": "stable",
            "last_changed": "2026-01-02T03:00:00+00:00",
            "last_updated": "2026-01-02T03:01:00+00:00",
            "attributes": {"smart_pi": {"error_integral": 1.25}},
        },
        {
            "entity_id": "sensor.smartpi",
            "state": "stable",
            "last_changed": "2026-01-02T03:00:00+00:00",
            "last_updated": "2026-01-02T03:02:00+00:00",
            "attributes": {"smart_pi": {"error_integral": 1.5}},
        },
    ]

    with (
        patch("ha_entity_explorer.server.load_users", return_value={}),
        patch("ha_entity_explorer.server.ha_api.get_history", return_value=history) as history_mock,
        app.test_client() as client,
    ):
        response = client.get(
            "/api/export/entity/sensor.smartpi",
            query_string={
                "start": "2026-01-02T03:00:00Z",
                "end": "2026-01-02T04:00:00Z",
                "zip": "false",
            },
        )

    assert response.status_code == 200
    assert response.json == [
        {"timestamp": entry["last_updated"], **entry} for entry in history
    ]
    assert history_mock.call_args.kwargs["minimal_response"] is False
    assert history_mock.call_args.kwargs["significant_changes_only"] is False


def test_attribute_export_forwards_significant_changes_choice():
    history = [
        {
            "state": "stable",
            "last_updated": "2026-01-02T03:01:00+00:00",
            "attributes": {"smart_pi": {"error_integral": 1.25}},
        }
    ]

    with (
        patch("ha_entity_explorer.server.load_users", return_value={}),
        patch("ha_entity_explorer.server.ha_api.get_history", return_value=history) as history_mock,
        app.test_client() as client,
    ):
        response = client.get(
            "/api/export/attribute/sensor.smartpi",
            query_string={
                "key": "smart_pi.error_integral",
                "start": "2026-01-02T03:00:00Z",
                "end": "2026-01-02T04:00:00Z",
                "zip": "false",
                "significant_changes_only": "true",
            },
        )

    assert response.status_code == 200
    assert response.json == [
        {"timestamp": "2026-01-02T03:01:00+00:00", "value": 1.25}
    ]
    assert history_mock.call_args.kwargs["minimal_response"] is False
    assert history_mock.call_args.kwargs["significant_changes_only"] is True
