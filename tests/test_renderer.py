from pathlib import Path


def test_render_invalid_dpi(client, mock_parser, mock_renderer):
    mock_parser.get_rm_path.return_value = Path("/fake/path.rm")

    resp = client.get("/notebooks/abc-123/pages/0/render?dpi=999")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"
    assert "DPI" in resp.json()["error"]["message"]


def test_render_page_not_found(client, mock_parser, mock_renderer):
    from app.parser import PageNotFoundError
    mock_parser.get_rm_path.side_effect = PageNotFoundError("Page 99 out of range.")

    resp = client.get("/notebooks/abc-123/pages/99/render")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_render_notebook_not_found(client, mock_parser, mock_renderer):
    from app.parser import NotebookNotFoundError
    mock_parser.get_rm_path.side_effect = NotebookNotFoundError("Not found")

    resp = client.get("/notebooks/nonexistent/pages/0/render")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_render_png_success(client, mock_parser, mock_renderer):
    mock_parser.get_rm_path.return_value = Path("/fake/path.rm")
    mock_renderer.render_page_png.return_value = b"\x89PNG fake"

    resp = client.get("/notebooks/abc-123/pages/0/render?format=png&dpi=300")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == b"\x89PNG fake"


def test_render_pdf_success(client, mock_parser, mock_renderer):
    mock_parser.get_rm_path.return_value = Path("/fake/path.rm")
    mock_renderer.render_page_pdf.return_value = b"%PDF-1.4 fake"

    resp = client.get("/notebooks/abc-123/pages/0/render?format=pdf&dpi=300")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_export_pdf_success(client, mock_parser, mock_renderer):
    mock_parser.get_notebook.return_value = {
        "id": "abc-123",
        "name": "Test",
        "page_count": 2,
        "last_modified": "2026-03-12T10:00:00+00:00",
        "pages": [0, 1],
    }
    mock_parser.get_rm_path.side_effect = [Path("/fake/0.rm"), Path("/fake/1.rm")]
    mock_renderer.export_pdf.return_value = b"%PDF-1.4 merged"

    resp = client.get("/notebooks/abc-123/export?format=pdf&dpi=300")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_export_png_zip_success(client, mock_parser, mock_renderer):
    mock_parser.get_notebook.return_value = {
        "id": "abc-123",
        "name": "Test",
        "page_count": 1,
        "last_modified": "2026-03-12T10:00:00+00:00",
        "pages": [0],
    }
    mock_parser.get_rm_path.return_value = Path("/fake/0.rm")
    mock_renderer.export_pngs_zip.return_value = b"PK zip data"

    resp = client.get("/notebooks/abc-123/export?format=png&dpi=300")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
