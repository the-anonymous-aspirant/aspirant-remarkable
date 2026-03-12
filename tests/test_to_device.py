import io


def test_upload_pdf_success(client, mock_to_device):
    mock_to_device.stage_file.return_value = {
        "id": "abc-123",
        "filename": "test.pdf",
        "target_folder_id": None,
        "created_at": "2026-03-12T10:00:00+00:00",
        "size": 1024,
    }
    mock_to_device.is_supported.return_value = True

    resp = client.post(
        "/to-device/upload",
        files={"file": ("test.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "abc-123"
    assert data["filename"] == "test.pdf"
    assert data["size"] == 1024


def test_upload_epub_success(client, mock_to_device):
    mock_to_device.stage_file.return_value = {
        "id": "abc-789",
        "filename": "book.epub",
        "target_folder_id": None,
        "created_at": "2026-03-12T10:00:00+00:00",
        "size": 4096,
    }
    mock_to_device.is_supported.return_value = True

    resp = client.post(
        "/to-device/upload",
        files={"file": ("book.epub", b"PK\x03\x04 fake epub", "application/epub+zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "abc-789"
    assert data["filename"] == "book.epub"
    assert data["size"] == 4096


def test_upload_with_target_folder(client, mock_to_device):
    mock_to_device.stage_file.return_value = {
        "id": "abc-456",
        "filename": "report.pdf",
        "target_folder_id": "folder-1",
        "created_at": "2026-03-12T10:00:00+00:00",
        "size": 2048,
    }
    mock_to_device.is_supported.return_value = True

    resp = client.post(
        "/to-device/upload",
        files={"file": ("report.pdf", b"%PDF-1.4 content", "application/pdf")},
        data={"target_folder_id": "folder-1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_folder_id"] == "folder-1"


def test_upload_rejects_unsupported_type(client, mock_to_device):
    mock_to_device.is_supported.return_value = False
    mock_to_device.supported_extensions.return_value = [".epub", ".pdf"]

    resp = client.post(
        "/to-device/upload",
        files={"file": ("test.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"
    assert "Unsupported" in resp.json()["error"]["message"]


def test_upload_rejects_empty_file(client, mock_to_device):
    mock_to_device.is_supported.return_value = True

    resp = client.post(
        "/to-device/upload",
        files={"file": ("test.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"
    assert "empty" in resp.json()["error"]["message"].lower()


def test_upload_rejects_no_file(client, mock_to_device):
    # Send multipart with only a text field, no file
    resp = client.post(
        "/to-device/upload",
        data={"target_folder_id": "folder-1"},
        files={"not_file": ("dummy", b"", "text/plain")},
    )
    # Should return 400 because no "file" field
    assert resp.status_code == 400


def test_list_pending(client, mock_to_device):
    mock_to_device.list_pending.return_value = [
        {
            "id": "abc-123",
            "filename": "test.pdf",
            "target_folder_id": None,
            "created_at": "2026-03-12T10:00:00+00:00",
            "size": 1024,
        }
    ]

    resp = client.get("/to-device/pending")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "abc-123"


def test_list_pending_empty(client, mock_to_device):
    mock_to_device.list_pending.return_value = []

    resp = client.get("/to-device/pending")
    assert resp.status_code == 200
    assert resp.json() == []


def test_delete_pending_success(client, mock_to_device):
    mock_to_device.remove_pending.return_value = True

    resp = client.delete("/to-device/abc-123")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    mock_to_device.remove_pending.assert_called_once_with("abc-123")


def test_delete_pending_not_found(client, mock_to_device):
    mock_to_device.remove_pending.return_value = False

    resp = client.delete("/to-device/nonexistent")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
