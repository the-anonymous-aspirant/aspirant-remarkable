# aspirant-remarkable

reMarkable notebook rendering and bidirectional sync service for the Aspirant platform.

Parses reMarkable Paper Pro notebooks (xochitl format), renders pages at configurable DPI (150-1200), manages folder hierarchy, and supports bidirectional file sync between the device and server.

## Quick Start

```bash
docker build -t aspirant-remarkable .
docker run -p 8000:8000 -v remarkabledata:/data/remarkable aspirant-remarkable
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| GET | `/notebooks` | List all notebooks |
| GET | `/notebooks/{id}` | Get notebook details |
| GET | `/notebooks/{id}/pages/{page}/render` | Render page as PNG |
| GET | `/notebooks/{id}/export` | Export notebook as PDF/ZIP |
| GET | `/folders` | List all folders |
| GET | `/folders/{id}/contents` | List folder contents |
| GET | `/tree` | Full nested folder hierarchy |
| POST | `/sync` | Trigger sync from device (requires server→device connectivity) |
| GET | `/sync/status` | Last sync status and device info |
| POST | `/sync/device-info` | Accept device info push (IP, battery) |
| POST | `/to-device/upload` | Upload PDF for transfer to device |
| GET | `/to-device/pending` | List pending transfers |
| DELETE | `/to-device/{id}` | Remove pending transfer |

## Testing

```bash
pip install -r requirements-test.txt
pytest tests/ -v
```

## Device Setup

See [device/INSTALL.md](device/INSTALL.md) for complete instructions on configuring the reMarkable Paper Pro for automatic sync.

### Key files in `device/`

| File | Deployed to | Purpose |
|------|-------------|---------|
| `sync-to-server.sh` | reMarkable: `/home/root/sync-to-server.sh` | Sync script (push notebooks, pull to-device, report device info) |
| `remarkable-sync.service` | reMarkable: `/etc/systemd/system/aspirant-sync.service` | systemd oneshot service |
| `remarkable-sync.timer` | reMarkable: `/etc/systemd/system/aspirant-sync.timer` | Daily midnight timer with persistence |
| `remarkable-sync-validate.sh` | Server: `/home/aspirant/remarkable-sync-validate.sh` | Restricts device SSH key to rsync-only |
| `INSTALL.md` | — | Full setup guide with gotchas |
