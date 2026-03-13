import sys
import pytest
from unittest.mock import patch, MagicMock

# Inject mock modules so imports resolve without real packages
_mock_rmscene = MagicMock()
_mock_rmc = MagicMock()
_mock_cairosvg = MagicMock()
_mock_pypdf = MagicMock()
_mock_fitz = MagicMock()

sys.modules.setdefault("rmscene", _mock_rmscene)
sys.modules.setdefault("rmc", _mock_rmc)
sys.modules.setdefault("rmc.exporters", _mock_rmc.exporters)
sys.modules.setdefault("rmc.exporters.writing_tools", _mock_rmc.exporters.writing_tools)
# Provide a real dict for RM_PALETTE so the fallback wrapper works
_mock_rmc.exporters.writing_tools.RM_PALETTE = {}
sys.modules.setdefault("cairosvg", _mock_cairosvg)
sys.modules.setdefault("pypdf", _mock_pypdf)
sys.modules.setdefault("fitz", _mock_fitz)

from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def mock_parser():
    with patch("app.routes.parser") as mock_p:
        yield mock_p


@pytest.fixture()
def mock_sync():
    with patch("app.routes.sync") as mock_s:
        yield mock_s


@pytest.fixture()
def mock_renderer():
    with patch("app.routes.renderer") as mock_r:
        yield mock_r


@pytest.fixture()
def mock_ssh():
    with patch("app.routes.ssh") as mock_s:
        yield mock_s


@pytest.fixture()
def mock_sync_status():
    with patch("app.routes.sync_status") as mock_ss:
        yield mock_ss


@pytest.fixture()
def mock_to_device():
    with patch("app.routes.to_device") as mock_td:
        yield mock_td
