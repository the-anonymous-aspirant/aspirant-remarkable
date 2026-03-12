def test_sync_status_empty(client, mock_sync_status):
    mock_sync_status.get_status.return_value = {
        "last_sync": None,
        "last_sync_direction": None,
        "files_synced": None,
        "device_ip": None,
        "battery": None,
        "device_info_updated": None,
    }

    resp = client.get("/sync/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_sync"] is None
    assert data["device_ip"] is None


def test_sync_status_populated(client, mock_sync_status):
    mock_sync_status.get_status.return_value = {
        "last_sync": "2026-03-12T00:00:00+00:00",
        "last_sync_direction": "push",
        "files_synced": 42,
        "device_ip": "192.168.1.50",
        "battery": 85,
        "device_info_updated": "2026-03-12T00:00:05+00:00",
    }

    resp = client.get("/sync/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["last_sync"] == "2026-03-12T00:00:00+00:00"
    assert data["files_synced"] == 42
    assert data["device_ip"] == "192.168.1.50"
    assert data["battery"] == 85


def test_post_device_info(client, mock_sync_status):
    resp = client.post("/sync/device-info", json={"ip": "192.168.1.50", "battery": 72})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_sync_status.update_device_info.assert_called_once_with(
        "192.168.1.50", battery=72, push_files=None, pull_files=None,
    )


def test_post_device_info_no_battery(client, mock_sync_status):
    resp = client.post("/sync/device-info", json={"ip": "10.0.0.5"})
    assert resp.status_code == 200
    mock_sync_status.update_device_info.assert_called_once_with(
        "10.0.0.5", battery=None, push_files=None, pull_files=None,
    )


def test_post_device_info_with_sync_counts(client, mock_sync_status):
    resp = client.post("/sync/device-info", json={
        "ip": "192.168.1.50", "battery": 85, "push_files": 42, "pull_files": 3,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_sync_status.update_device_info.assert_called_once_with(
        "192.168.1.50", battery=85, push_files=42, pull_files=3,
    )


def test_sync_records_status(client, mock_sync, mock_sync_status):
    mock_sync.sync_from_remarkable.return_value = (15, "10.11.99.1")

    resp = client.post("/sync")
    assert resp.status_code == 200
    mock_sync_status.update_sync_result.assert_called_once_with(15, "pull")
