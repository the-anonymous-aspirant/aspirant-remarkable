def test_list_folders_empty(client, mock_parser):
    mock_parser.list_folders.return_value = []

    resp = client.get("/folders")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_folders_populated(client, mock_parser):
    mock_parser.list_folders.return_value = [
        {
            "id": "folder-1",
            "name": "My Folder",
            "type": "CollectionType",
            "parent_id": None,
            "last_modified": "2026-03-12T10:00:00+00:00",
            "page_count": 0,
        }
    ]

    resp = client.get("/folders")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "folder-1"
    assert data[0]["name"] == "My Folder"
    assert data[0]["parent_id"] is None


def test_folder_contents(client, mock_parser):
    mock_parser.list_folder_contents.return_value = [
        {
            "id": "doc-1",
            "name": "A Notebook",
            "type": "DocumentType",
            "parent_id": "folder-1",
            "last_modified": "2026-03-12T10:00:00+00:00",
            "page_count": 3,
        },
        {
            "id": "subfolder-1",
            "name": "Subfolder",
            "type": "CollectionType",
            "parent_id": "folder-1",
            "last_modified": "2026-03-12T09:00:00+00:00",
            "page_count": 0,
        },
    ]

    resp = client.get("/folders/folder-1/contents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["type"] == "DocumentType"
    assert data[1]["type"] == "CollectionType"


def test_folder_contents_empty(client, mock_parser):
    mock_parser.list_folder_contents.return_value = []

    resp = client.get("/folders/nonexistent/contents")
    assert resp.status_code == 200
    assert resp.json() == []


def test_tree(client, mock_parser):
    mock_parser.get_folder_tree.return_value = [
        {
            "id": "folder-1",
            "name": "Root Folder",
            "type": "CollectionType",
            "parent_id": None,
            "last_modified": "2026-03-12T10:00:00+00:00",
            "page_count": 0,
            "children": [
                {
                    "id": "doc-1",
                    "name": "My Notebook",
                    "type": "DocumentType",
                    "parent_id": "folder-1",
                    "last_modified": "2026-03-12T10:00:00+00:00",
                    "page_count": 5,
                    "children": [],
                }
            ],
        },
        {
            "id": "doc-2",
            "name": "Root Notebook",
            "type": "DocumentType",
            "parent_id": None,
            "last_modified": "2026-03-12T09:00:00+00:00",
            "page_count": 2,
            "children": [],
        },
    ]

    resp = client.get("/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["children"][0]["name"] == "My Notebook"


def test_notebooks_with_parent_filter(client, mock_parser):
    mock_parser.list_notebooks.return_value = [
        {
            "id": "doc-1",
            "name": "Notebook in folder",
            "page_count": 3,
            "last_modified": "2026-03-12T10:00:00+00:00",
            "parent_id": "folder-1",
        }
    ]

    resp = client.get("/notebooks?parent_id=folder-1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["parent_id"] == "folder-1"
    mock_parser.list_notebooks.assert_called_once_with(parent_id="folder-1")
