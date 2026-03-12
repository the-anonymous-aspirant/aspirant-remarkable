def test_sync_success(client, mock_sync):
    mock_sync.sync_from_remarkable.return_value = (42, "10.11.99.1")

    resp = client.post("/sync")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["files_synced"] == 42
    assert data["host"] == "10.11.99.1"


def test_sync_with_custom_host(client, mock_sync):
    mock_sync.sync_from_remarkable.return_value = (10, "192.168.1.95")

    resp = client.post("/sync", json={"host": "192.168.1.95"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["host"] == "192.168.1.95"
    mock_sync.sync_from_remarkable.assert_called_once_with(host="192.168.1.95")


def test_sync_failure(client, mock_sync):
    from app.sync import SyncError
    mock_sync.sync_from_remarkable.side_effect = SyncError("Connection refused")
    mock_sync.SyncError = SyncError

    resp = client.post("/sync")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "service_unavailable"
