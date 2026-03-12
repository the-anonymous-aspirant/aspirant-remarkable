def test_app_imports():
    from app.main import app
    assert app is not None


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["service"] == "remarkable"
    assert data["version"] == "1.1.0"
    assert "checks" in data
    assert "rmscene" in data["checks"]
    assert "rmc" in data["checks"]
    assert "data_volume" in data["checks"]
    assert "ssh_key" in data["checks"]


def test_setup_ssh_key_returns_public_key(client, mock_ssh):
    mock_ssh.get_public_key.return_value = "ssh-ed25519 AAAA... remarkable-service"

    resp = client.get("/setup/ssh-key")
    assert resp.status_code == 200
    data = resp.json()
    assert data["public_key"] == "ssh-ed25519 AAAA... remarkable-service"
    assert "instructions" in data


def test_setup_ssh_key_not_generated(client, mock_ssh):
    mock_ssh.get_public_key.side_effect = FileNotFoundError("SSH key not found")

    resp = client.get("/setup/ssh-key")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "service_unavailable"
