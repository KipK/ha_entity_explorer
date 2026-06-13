from ha_entity_explorer.server import imported_data_cache, process_imported_json_data


def test_imports_ha_better_history_multi_series_format():
    payload = {
        "format": "ha-better-history-series-v1",
        "exportedAt": "2026-06-13T16:05:12.255Z",
        "loadedRange": {
            "start": "2026-06-11T15:02:00.000Z",
            "end": "2026-06-12T16:02:00.000Z",
        },
        "viewRange": {
            "start": "2026-06-11T16:00:00.000Z",
            "end": "2026-06-12T15:00:00.000Z",
        },
        "series": [
            {
                "id": "state:climate.living_room",
                "entityId": "climate.living_room",
                "label": "Living room",
                "valueType": "string",
                "lineMode": "stair",
                "color": "#66bb6a",
                "points": [
                    {"timestamp": "invalid", "value": "off"},
                    {"timestamp": "2026-06-12T10:00:00Z", "value": "heat"},
                    {"timestamp": "2026-06-11T16:00:00Z", "value": "off"},
                ],
            },
            {
                "id": "attr:sensor.controller:control.kp",
                "entityId": "sensor.controller",
                "attribute": "control.kp",
                "label": "kp",
                "valueType": "number",
                "unit": "%",
                "scalePreference": "secondary",
                "points": [
                    {"timestamp": "2026-06-11T16:00:00Z", "value": 0.4},
                    {"timestamp": "2026-06-12T10:00:00Z", "value": "not-a-number"},
                ],
            },
        ],
    }

    result, status = process_imported_json_data(payload, "better-history.json")

    assert status == 200
    assert result["type"] == "series"
    assert result["filename"] == "better-history.json"
    assert result["data"]["start"] == payload["viewRange"]["start"]
    assert result["data"]["end"] == payload["viewRange"]["end"]
    assert result["data"]["count"] == 3
    assert [
        point["value"] for point in result["data"]["series"][0]["points"]
    ] == ["off", "heat"]
    assert result["data"]["series"][1]["entityId"] == "sensor.controller"
    assert result["data"]["series"][1]["attribute"] == "control.kp"
    assert result["data"]["series"][1]["scalePreference"] == "secondary"


def test_rejects_invalid_ha_better_history_series():
    payload = {
        "format": "ha-better-history-series-v1",
        "viewRange": {
            "start": "2026-06-11T16:00:00Z",
            "end": "2026-06-12T16:00:00Z",
        },
        "series": [{"id": "state:sensor.test"}],
    }

    result, status = process_imported_json_data(payload, "invalid.json")

    assert status == 400
    assert "entityId" in result["error"]


def test_existing_attribute_import_format_is_unchanged():
    payload = [
        {"timestamp": "2026-06-11T16:00:00Z", "value": 20.5},
        {"timestamp": "2026-06-11T17:00:00Z", "value": 21.0},
    ]

    result, status = process_imported_json_data(payload, "attribute.json")

    assert status == 200
    assert result["type"] == "attribute"
    assert result["data"]["type"] == "numeric"
    assert result["data"]["values"] == [20.5, 21.0]


def test_existing_entity_import_format_is_unchanged():
    payload = [
        {
            "entity_id": "sensor.test",
            "state": "12.5",
            "attributes": {"unit_of_measurement": "°C"},
            "last_updated": "2026-06-11T16:00:00Z",
        }
    ]

    result, status = process_imported_json_data(payload, "entity.json")

    try:
        assert status == 200
        assert result["type"] == "entity"
        assert result["data"]["type"] == "numeric"
        assert result["data"]["states"] == [12.5]
    finally:
        imported_data_cache.pop(result.get("data", {}).get("import_id", ""), None)
