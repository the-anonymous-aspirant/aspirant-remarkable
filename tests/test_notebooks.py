def test_list_notebooks_empty(client, mock_parser):
    mock_parser.list_notebooks.return_value = []

    resp = client.get("/notebooks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_notebooks_populated(client, mock_parser):
    mock_parser.list_notebooks.return_value = [
        {
            "id": "abc-123",
            "name": "My Notebook",
            "page_count": 5,
            "last_modified": "2026-03-12T10:00:00+00:00",
        }
    ]

    resp = client.get("/notebooks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "abc-123"
    assert data[0]["name"] == "My Notebook"
    assert data[0]["page_count"] == 5


def test_get_notebook_found(client, mock_parser):
    mock_parser.get_notebook.return_value = {
        "id": "abc-123",
        "name": "My Notebook",
        "page_count": 3,
        "last_modified": "2026-03-12T10:00:00+00:00",
        "pages": [0, 1, 2],
    }

    resp = client.get("/notebooks/abc-123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "abc-123"
    assert data["pages"] == [0, 1, 2]


def test_get_notebook_not_found(client, mock_parser):
    from app.parser import NotebookNotFoundError
    mock_parser.get_notebook.side_effect = NotebookNotFoundError("Not found")

    resp = client.get("/notebooks/nonexistent")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
