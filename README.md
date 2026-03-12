# aspirant-remarkable

reMarkable notebook rendering and bidirectional sync service for the Aspirant platform.

Parses reMarkable Paper Pro notebooks (xochitl format), renders pages at configurable DPI (150–1200), manages folder hierarchy, and supports bidirectional file sync between the device and server.

## Quick Start

```bash
docker build -t aspirant-remarkable .
docker run -p 8000:8000 -v remarkabledata:/data/remarkable aspirant-remarkable
```

## Testing

```bash
pip install -r requirements-test.txt
pytest tests/ -v
```

## Device Setup

See [device/INSTALL.md](device/INSTALL.md) for instructions on configuring the reMarkable tablet for automatic sync via systemd timer.
